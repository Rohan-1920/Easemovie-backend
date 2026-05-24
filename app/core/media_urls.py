"""Resolve /media URLs for Replicate (public URL or local file upload)."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.services.storage import MEDIA_ROOT


def is_local_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    h = hostname.lower()
    if h in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        return True
    return is_private_or_lan_host(h)


def is_private_or_lan_host(hostname: str | None) -> bool:
    """True for LAN/private IPs — Replicate cannot fetch these URLs from the internet."""
    if not hostname:
        return True
    host = hostname.strip().lower()
    if host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def local_media_path_from_url(image_url: str) -> Path | None:
    """Map http://host/media/images/x.png → filesystem path under MEDIA_ROOT."""
    parsed = urlparse(image_url.strip())
    path = parsed.path or ""
    prefix = "/media/"
    if not path.startswith(prefix):
        return None
    rel = path[len(prefix) :].lstrip("/").replace("\\", "/")
    local = (MEDIA_ROOT / rel).resolve()
    root = MEDIA_ROOT.resolve()
    try:
        local.relative_to(root)
    except ValueError:
        return None
    return local if local.is_file() else None


def to_public_media_url(image_url: str, request_base: str = "") -> str:
    """
    Replace localhost with PUBLIC_BASE_URL so Replicate can download the image.
  """
    parsed = urlparse(image_url.strip())
    if not parsed.path.startswith("/media/"):
        return image_url.strip()

    base = settings.api_base_url(request_base)
    if not base:
        return image_url.strip()

    if is_local_host(parsed.hostname):
        return f"{base}{parsed.path}"

    return image_url.strip()
