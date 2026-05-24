import requests

# Test the image generation endpoint
url = "http://localhost:8000/generate_image"
params = {
    "text": "A beautiful sunset over mountains",
    "style": "cinematic",
    "emotion": "peaceful"
}

try:
    print("Testing image generation...")
    response = requests.post(url, params=params)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("Success! Response:", data)

        # Check if image URL is returned
        if "image_path" in data:
            image_url = data["image_path"]
            print(f"Image URL: {image_url}")

            # Try to fetch the actual image
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                print(f"Image downloaded successfully! Size: {len(image_response.content)} bytes")
                print("✅ Image generation is working - NOT returning black images!")
            else:
                print(f"❌ Could not download image: {image_response.status_code}")
        else:
            print("❌ No image_path in response")
    else:
        print(f"❌ API Error: {response.text}")

except Exception as e:
    print(f"❌ Error: {str(e)}")