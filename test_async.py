
import requests
import base64
import time
import os

# Helper to read file as base64
def get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

# 1. Submit async job
img_path = "static/uploads/test_uploads/82092117.png"
payload = {
    "files": [
        {
            "filename": "82092117.png",
            "base64": get_base64(img_path),
            "language": "en"
        }
    ]
}

print("Submitting async job...")
resp = requests.post("http://127.0.0.1:5000/api/async_ocr", json=payload)
print(f"Status Code: {resp.status_code}")
job_data = resp.json()
print(f"Response: {job_data}")

if resp.status_code == 202:
    job_id = job_data["job_id"]
    # 2. Poll for results
    for i in range(10):
        print(f"Polling attempt {i+1} for job {job_id}...")
        status_resp = requests.get(f"http://127.0.0.1:5000/api/ocr_status/{job_id}")
        status_data = status_resp.json()
        print(f"Status: {status_data['status']}")
        if status_data['status'] in ['completed', 'failed']:
            print("Job finished!")
            print(f"Results keys: {status_data.keys()}")
            if 'results' in status_data:
                print(f"Number of results: {len(status_data['results'])}")
                if len(status_data['results']) > 0:
                    print(f"First result keys: {status_data['results'][0].keys()}")
            else:
                print("MISSING 'results' key in response!")
            break
        time.sleep(2)
else:
    print("Failed to submit job")
