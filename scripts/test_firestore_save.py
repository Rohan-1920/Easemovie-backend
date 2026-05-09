import requests

BASE = "http://127.0.0.1:8000"

print('Checking backend health...')
r = requests.get(f"{BASE}/health", timeout=5)
print('health', r.status_code, r.text)

payload = {
    'user_id': 'test_user',
    'title': 'Fairy Tale Test Video',
    'style': 'Whimsical 3D',
    'video_url': 'http://127.0.0.1:8000/media/videos/c9b2a4f6e94e4db1a4fcf37281b741a9.mp4',
    'thumbnail_url': 'http://127.0.0.1:8000/media/images/cf09ef00053245afabb45890db7258c6.png',
    'scenes': [
        'Once upon a time, in a magical forest, there lived a little fairy named Lila.',
        'She had sparkling wings and a heart full of kindness.',
        'One sunny morning, Lila found a lost baby bird crying on the ground.'
    ]
}

print('Creating project...')
r = requests.post(f"{BASE}/projects", json=payload, timeout=10)
print('post', r.status_code, r.text)

print('Listing projects...')
r = requests.get(f"{BASE}/projects", timeout=10)
print('list', r.status_code, r.text)
