import httpx
import asyncio

async def test_api():
    headers = {
        'Authorization': 'Bearer sk-al1u1RuVdywRjbggXRF9GqgwBMcS4BRSavVUefOLgjbxh6rI',
        'Accept': 'image/*',
        'Content-Type': 'application/json',
    }

    payload = {
        'prompt': 'A beautiful sunset over mountains. Mood: peaceful. Style: cinematic.',
        'model': 'sd3.5-large',
        'aspect_ratio': '1:1',
        'output_format': 'png',
    }

    url = 'https://api.stability.ai/v2beta/stable-image/generate/sd3'

    print(f'Testing API call to: {url}')
    print(f'Payload: {payload}')

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f'Status: {response.status_code}')
            print(f'Content-Type: {response.headers.get("content-type")}')
            print(f'Content-Length: {len(response.content)}')

            if response.status_code == 200:
                if response.headers.get('content-type', '').startswith('image/'):
                    print('✅ API returned valid image!')
                    # Save the image to check it
                    with open('test_image.png', 'wb') as f:
                        f.write(response.content)
                    print('Image saved as test_image.png')
                else:
                    print('❌ API returned non-image content')
                    print(f'Response: {response.text[:500]}')
            else:
                print(f'❌ API Error: {response.text[:500]}')

        except Exception as e:
            print(f'❌ Connection Error: {e}')

if __name__ == '__main__':
    asyncio.run(test_api())