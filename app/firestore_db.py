"""Firestore persistence for projects — Firebase Admin SDK."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
from firebase_admin.exceptions import FirebaseError

from app.core.config import BACKEND_ROOT, settings
from app.schemas import ProjectCreate, ProjectOut


def _resolve_credentials_path() -> Path | None:
    raw = (settings.firebase_credentials_path or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path.resolve()


def init_firestore() -> None:
    """Initialize Firebase Admin from JSON env (Render) or service-account file (local)."""
    if firebase_admin._apps:
        return

    json_raw = (settings.firebase_credentials_json or "").strip()
    if json_raw:
        try:
            cred = credentials.Certificate(json.loads(json_raw))
            initialize_app(cred)
            print("Firebase initialized successfully from FIREBASE_CREDENTIALS_JSON")
            return
        except Exception as e:
            print(f"WARNING: Failed to parse FIREBASE_CREDENTIALS_JSON: {e}. Firebase disabled.")
            return

    path = _resolve_credentials_path()
    if path is None:
        print(
            "WARNING: Set FIREBASE_CREDENTIALS_JSON (Render) or FIREBASE_CREDENTIALS_PATH (local). "
            "Firebase disabled."
        )
        return
    if not path.is_file():
        print(f"WARNING: Firebase credentials file not found: {path}. Firebase disabled.")
        return
    try:
        cred = credentials.Certificate(str(path))
        initialize_app(cred)
        print(f"Firebase initialized successfully from {path}")
    except Exception as e:
        print(f"WARNING: Failed to initialize Firebase: {e}. Firebase disabled.")


def _collection():
    if not firebase_admin._apps:
        raise RuntimeError(
            "Firebase/Firestore is not initialized. "
            "Configure FIREBASE_CREDENTIALS_PATH and ensure the credentials file exists."
        )
    return firestore.client().collection(settings.firestore_projects_collection)


def _created_sort_value(data: dict | None) -> float:
    if not data:
        return 0.0
    if isinstance(data.get("createdAt"), (int, float)):
        return float(data["createdAt"]) / 1000.0
    c = data.get("created_at")
    if c is None:
        return 0.0
    if hasattr(c, "timestamp"):
        try:
            return float(c.timestamp())
        except Exception:
            return 0.0
    if isinstance(c, str):
        try:
            return datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _doc_to_project(doc_id: str, data: dict | None) -> ProjectOut:
    if data is None:
        raise ValueError("Missing document data")
    created = data.get("created_at")
    if created is not None and hasattr(created, "isoformat"):
        created_str = created.isoformat()
    elif isinstance(created, str):
        created_str = created
    elif isinstance(data.get("createdAt"), (int, float)):
        created_str = datetime.fromtimestamp(float(data["createdAt"]) / 1000.0, tz=timezone.utc).isoformat()
    else:
        created_str = datetime.now(timezone.utc).isoformat()

    scenes_raw = data.get("scenes") or []
    scenes = [str(s) for s in scenes_raw] if isinstance(scenes_raw, list) else []

    return ProjectOut(
        id=doc_id,
        user_id=str(data.get("user_id") or data.get("userId") or ""),
        title=str(data.get("title") or ""),
        style=str(data.get("style") or ""),
        video_url=str(data.get("video_url") or data.get("videoUrl") or ""),
        thumbnail_url=str(data.get("thumbnail_url") or data.get("thumbnailUrl") or ""),
        scenes=scenes,
        created_at=created_str,
    )


def create_project(payload: ProjectCreate) -> ProjectOut:
    col = _collection()
    doc_ref = col.document()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    scenes = payload.scenes or []
    video_url = payload.video_url
    thumb = payload.thumbnail_url or ""

    # Android app reads camelCase fields (userId, videoUrl, createdAt).
    doc_ref.set(
        {
            "userId": payload.user_id,
            "user_id": payload.user_id,
            "title": payload.title,
            "style": payload.style,
            "videoUrl": video_url,
            "video_url": video_url,
            "thumbnailUrl": thumb,
            "thumbnail_url": thumb,
            "scenes": scenes,
            "createdAt": now_ms,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    snap = doc_ref.get()
    return _doc_to_project(doc_ref.id, snap.to_dict())


def list_projects(user_id: str | None = None) -> list[ProjectOut]:
    col = _collection()
    try:
        if user_id:
            snaps = list(col.where("userId", "==", user_id).stream())
            if not snaps:
                snaps = list(col.where("user_id", "==", user_id).stream())
        else:
            snaps = list(col.stream())
    except FirebaseError as exc:
        raise RuntimeError(f"Firestore query failed: {exc}") from exc

    snaps.sort(key=lambda s: _created_sort_value(s.to_dict()), reverse=True)
    return [_doc_to_project(s.id, s.to_dict()) for s in snaps]


def get_project(project_id: str) -> ProjectOut | None:
    snap = _collection().document(project_id).get()
    if not snap.exists:
        return None
    return _doc_to_project(snap.id, snap.to_dict())


def delete_project(project_id: str) -> bool:
    doc_ref = _collection().document(project_id)
    snap = doc_ref.get()
    if not snap.exists:
        return False
    doc_ref.delete()
    return True
