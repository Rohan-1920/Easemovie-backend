from __future__ import annotations


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "time" in body


def test_segment_splits_story(client):
    response = client.post(
        "/segment",
        json={"text": "Ali walks into the forest. He sees a glowing door. He steps through."},
    )
    assert response.status_code == 200
    data = response.json()
    assert "scenes" in data
    assert len(data["scenes"]) >= 2
    for scene in data["scenes"]:
        assert "index" in scene
        assert "text" in scene
        assert "mood" in scene
        assert "camera" in scene
