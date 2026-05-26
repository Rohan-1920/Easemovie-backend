"""In-memory async generation jobs (avoids Render/proxy HTTP timeouts)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.schemas import VideoResponse


@dataclass
class GenerationJob:
    id: str
    kind: str
    status: str = "queued"  # queued | processing | completed | failed
    progress: float = 0.0
    message: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


_jobs: dict[str, GenerationJob] = {}


def create_job(kind: str) -> GenerationJob:
    job = GenerationJob(id=uuid.uuid4().hex, kind=kind)
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> GenerationJob | None:
    return _jobs.get(job_id)


def _touch(job: GenerationJob) -> None:
    job.updated_at = time.time()


def set_job_processing(job_id: str, message: str = "Processing") -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = "processing"
    job.message = message
    _touch(job)


def update_job_progress(job_id: str, progress: float, message: str) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.progress = max(0.0, min(progress, 1.0))
    job.message = message
    if job.status == "queued":
        job.status = "processing"
    _touch(job)


def complete_job(job_id: str, result: VideoResponse) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = "completed"
    job.progress = 1.0
    job.message = "Completed"
    job.result = result.model_dump()
    job.error = None
    _touch(job)


def fail_job(job_id: str, error: str) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = "failed"
    job.message = "Failed"
    job.error = error
    _touch(job)


def job_to_dict(job: GenerationJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


async def run_in_background(coro, *, job_id: str) -> None:
    try:
        set_job_processing(job_id)
        result = await coro
        complete_job(job_id, result)
    except Exception as exc:
        fail_job(job_id, str(exc))
