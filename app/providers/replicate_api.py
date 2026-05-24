"""Replicate API client — separate tokens for image and video models."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("easemovie.replicate")

REPLICATE_API = "https://api.replicate.com/v1"

# Cache latest version ids (sunfjun and some community models need /predictions + version).
_version_cache: dict[str, str] = {}


def parse_model_slug(slug: str) -> tuple[str, str]:
    """Split 'owner/name' into (owner, name)."""
    cleaned = (slug or "").strip().strip("/")
    if "/" not in cleaned:
        raise ValueError(f"Invalid model slug (expected owner/name): {slug!r}")
    owner, name = cleaned.split("/", 1)
    if not owner or not name:
        raise ValueError(f"Invalid model slug: {slug!r}")
    return owner, name


def _headers(token: str) -> dict[str, str]:
    if not token:
        raise RuntimeError("Replicate API token is not set.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }


async def get_latest_version_id(model_slug: str, api_token: str, client: httpx.AsyncClient) -> str:
    cached = _version_cache.get(model_slug)
    if cached:
        return cached
    owner, name = parse_model_slug(model_slug)
    response = await client.get(
        f"{REPLICATE_API}/models/{owner}/{name}",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Could not load model version for {model_slug}: {response.status_code} {response.text[:300]}"
        )
    data = response.json()
    version = (data.get("latest_version") or {}).get("id")
    if not version:
        raise RuntimeError(f"No latest_version found for Replicate model {model_slug}.")
    _version_cache[model_slug] = str(version)
    return str(version)


def _retry_after_seconds(response: httpx.Response, default: float = 10.0) -> float:
    try:
        body = response.json()
        if isinstance(body, dict) and body.get("retry_after") is not None:
            return max(float(body["retry_after"]), 1.0)
    except Exception:
        pass
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(float(header), 1.0)
        except ValueError:
            pass
    return default


async def _post_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any],
    context: str,
    max_attempts: int = 8,
) -> httpx.Response:
    """Retry on Replicate 429 (common when account credit is under $5)."""
    last_response: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        response = await client.post(url, headers=headers, json=json_body)
        last_response = response
        if response.status_code != 429:
            return response
        wait = _retry_after_seconds(response)
        if attempt >= max_attempts:
            break
        logger.warning(
            "Replicate throttled (%s), waiting %.0fs (attempt %s/%s)...",
            context,
            wait,
            attempt,
            max_attempts,
        )
        await asyncio.sleep(wait + 1.0)

    assert last_response is not None
    raise RuntimeError(
        "Replicate rate limit (429). Low credit accounts (< $5) are limited to ~1 request at a time. "
        "Wait 15 seconds and try again, or add credit: https://replicate.com/account/billing — "
        f"{last_response.text[:220]}"
    )


def _uses_version_predictions_endpoint(model_slug: str) -> bool:
    """Community SVD models (sunfjun, christophy) need POST /predictions + version id."""
    slug = (model_slug or "").lower()
    return "sunfjun/" in slug or "christophy/" in slug or "stable-video-diffusion" in slug


async def _create_prediction(
    client: httpx.AsyncClient,
    model_slug: str,
    input_data: dict[str, Any],
    api_token: str,
) -> httpx.Response:
    headers = _headers(api_token)

    if _uses_version_predictions_endpoint(model_slug):
        version_id = await get_latest_version_id(model_slug, api_token, client)
        return await _post_json_with_retry(
            client,
            f"{REPLICATE_API}/predictions",
            headers=headers,
            json_body={"version": version_id, "input": input_data},
            context=f"{model_slug} (version)",
        )

    owner, name = parse_model_slug(model_slug)
    models_url = f"{REPLICATE_API}/models/{owner}/{name}/predictions"

    create = await _post_json_with_retry(
        client,
        models_url,
        headers=headers,
        json_body={"input": input_data},
        context=model_slug,
    )
    if create.status_code == 404:
        version_id = await get_latest_version_id(model_slug, api_token, client)
        create = await _post_json_with_retry(
            client,
            f"{REPLICATE_API}/predictions",
            headers=headers,
            json_body={"version": version_id, "input": input_data},
            context=f"{model_slug} (version)",
        )
    return create


async def run_model_prediction(
    model_slug: str,
    input_data: dict[str, Any],
    *,
    api_token: str,
) -> dict[str, Any]:
    """Run prediction on latest version. Falls back to version id for community models (e.g. sunfjun)."""
    timeout = httpx.Timeout(connect=30.0, read=900.0, write=120.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        create = await _create_prediction(client, model_slug, input_data, api_token)
        if create.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"Replicate create failed ({model_slug}): {create.status_code} {create.text[:400]}"
            )

        prediction = create.json()
        pred_id = prediction.get("id")
        if not pred_id:
            raise RuntimeError("Replicate returned no prediction id.")

        status = prediction.get("status")
        deadline = time.monotonic() + settings.replicate_poll_timeout_seconds

        while status in ("starting", "processing", "queued"):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Replicate prediction timed out ({model_slug}).")
            await asyncio.sleep(settings.replicate_poll_interval_seconds)
            poll = await client.get(
                f"{REPLICATE_API}/predictions/{pred_id}",
                headers={"Authorization": f"Bearer {api_token}"},
            )
            if poll.status_code != 200:
                raise RuntimeError(f"Replicate poll failed: {poll.status_code}")
            prediction = poll.json()
            status = prediction.get("status")

        if status == "failed":
            raise RuntimeError(prediction.get("error") or f"Replicate failed ({model_slug}).")
        if status != "succeeded":
            raise RuntimeError(f"Replicate ended with status {status} ({model_slug}).")
        return prediction


async def download_url(url: str) -> bytes:
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def extract_output_url(output: Any) -> str:
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str) and first.startswith("http"):
            return first
    raise RuntimeError(f"Unexpected Replicate output format: {type(output)}")


async def upload_local_file(file_path: Path, api_token: str) -> str:
    """
    Upload a local image to Replicate Files API so SVD can read it
    when PUBLIC_BASE_URL is not reachable from the internet.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Image file not found: {file_path}")

    suffix = file_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in (".jpg", ".jpeg") else "application/octet-stream"

    timeout = httpx.Timeout(connect=30.0, read=120.0, write=120.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with file_path.open("rb") as handle:
            response = await client.post(
                f"{REPLICATE_API}/files",
                headers={"Authorization": f"Bearer {api_token}"},
                files={"content": (file_path.name, handle, mime)},
            )
        if response.status_code == 429:
            wait = _retry_after_seconds(response)
            await asyncio.sleep(wait + 1.0)
            with file_path.open("rb") as handle:
                response = await client.post(
                    f"{REPLICATE_API}/files",
                    headers={"Authorization": f"Bearer {api_token}"},
                    files={"content": (file_path.name, handle, mime)},
                )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Replicate file upload failed: {response.status_code} {response.text[:300]}")

        data = response.json()
        urls = data.get("urls") or {}
        get_url = urls.get("get") if isinstance(urls, dict) else None
        if get_url and str(get_url).startswith("http"):
            return str(get_url)
        raise RuntimeError("Replicate file upload did not return a download URL.")
