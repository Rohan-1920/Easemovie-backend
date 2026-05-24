import requests

BASE = "http://127.0.0.1:8000"

payload = {
    "image_urls": [
        "http://127.0.0.1:8000/media/images/cf09ef00053245afabb45890db7258c6.png",
        "http://127.0.0.1:8000/media/images/4da3e14e479b4952b8f1175999ad2c3b.png",
    ],
    "seconds_per_scene": 3.0,
    "scene_narrations": [
        "A fairy enters the forest.",
        "A bird is rescued and comforted.",
    ],
    "voice": "en-US-JennyNeural",
    "user_id": "test_user",
    "title": "Firestore Save Test",
    "style": "Whimsical 3D",
    "thumbnail_url": "http://127.0.0.1:8000/media/images/cf09ef00053245afabb45890db7258c6.png",
    "scenes": [
        "A fairy enters the forest.",
        "A rescued bird flies away.",
    ],
    "save_project": True,
}

print("Sending compose_film with save_project=True...")
resp = requests.post(f"{BASE}/compose_film", json=payload, timeout=300)
print("status", resp.status_code)
print(resp.text)
