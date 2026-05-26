from __future__ import annotations

from app.services.generation_jobs import complete_job, create_job, fail_job, get_job, job_to_dict
from app.schemas import VideoResponse


def test_create_and_complete_job():
    job = create_job("compose_film")
    assert job.status == "queued"
    complete_job(
        job.id,
        VideoResponse(video_url="http://example.com/v.mp4", source="svd_multi"),
    )
    stored = get_job(job.id)
    assert stored is not None
    assert stored.status == "completed"
    assert stored.result is not None
    assert stored.result["video_url"].endswith("v.mp4")


def test_fail_job():
    job = create_job("video_from_images")
    fail_job(job.id, "timeout")
    stored = get_job(job.id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error == "timeout"


def test_job_to_dict_shape():
    job = create_job("compose_film")
    data = job_to_dict(job)
    assert data["job_id"] == job.id
    assert data["status"] == "queued"
    assert "progress" in data
