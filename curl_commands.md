Okay, here are the exact `curl` commands you'll need for testing, along with instructions for setting up the local HTTP server if you're testing with `sample.pdf`.

---

### **First, ensure your Docker container is running:**
If it's not, run:
```bash
docker run -dp 3001:80 tesseract-ocr-entrypoint:latest
```
And make sure you have `sample.pdf` and `async_job_input.json` (for async test) in your current directory.

---

### **1. Setup for Local PDF Testing (if using `sample.pdf` for `/api/v2/ocr` or `/api/async_ocr` URL):**

If you want to use a local `sample.pdf` file with the `/api/v2/ocr` or `/api/async_ocr` endpoints, you need to serve it via a simple HTTP server on your host machine.

1.  **Ensure `sample.pdf` is in your current directory.**
2.  **Start a Python HTTP server on your host machine (in a *separate* terminal):**
    ```bash
    python3 -m http.server 8000 --bind 0.0.0.0
    ```
    Keep this terminal open while testing.

---

### **2. Test the Synchronous API Endpoints with `curl`:**

#### **2.1. `/api/ocr` (Synchronous File Upload - `multipart/form-data`)**
This endpoint expects a file directly. Make sure you have a `test_image.png` or `sample.pdf` file in the directory where you run this `curl` command.

**Command:**
```bash
curl -X POST 
  -F "file=@sample.pdf" 
  -F "language=en" 
  http://127.0.0.1:3001/api/ocr
```
**(Replace `sample.pdf` with `test_image.png` if you want to test an image.)**

#### **2.2. `/api/v2/ocr` (Synchronous URL-based OCR - JSON)**
This endpoint expects a URL to a file. You can use a public URL or a local file served by the Python HTTP server (`http://host.docker.internal:8000/sample.pdf`).

**`sample.json` content:**
```json
{
    "url": "http://host.docker.internal:8000/sample.pdf",
    "language": "en"
}
```
**(Make sure `sample.json` is in the same directory as you run `curl`.)**

**Command:**
```bash
curl -X POST 
  -H "Content-Type: application/json" 
  -d @sample.json 
  http://127.0.0.1:3001/api/v2/ocr
```

---

### **3. Test the Asynchronous Multi-File OCR Endpoint (`/api/async_ocr`)**

#### **3.1. Submit a Job:**
This endpoint accepts multiple files via URL or Base64 in a JSON payload.

**`async_job_input.json` content:**
```json
{
  "files": [
    {
      "url": "http://host.docker.internal:8000/sample.pdf",
      "language": "en"
    },
    {
      "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
      "language": "en"
    }
    // You can also add base64 encoded files like:
    // {
    //   "base64": "JVBERi0xLjQKJ...", // Replace with actual base64 of an image/pdf
    //   "filename": "some_file.png",
    //   "language": "fr"
    // }
  ]
}
```
**(Make sure `async_job_input.json` is in the same directory as you run `curl`.)**

**Command:**
```bash
curl -X POST 
  -H "Content-Type: application/json" 
  -d @async_job_input.json 
  http://127.0.0.1:3001/api/async_ocr
```
**Important**: Copy the `job_id` from the response of this command!

#### **3.2. Query Job Status (`/api/ocr_status/<job_id>`)**
Use the `job_id` you copied from the previous step.

**Command:**
```bash
curl http://127.0.0.1:3001/api/ocr_status/<YOUR_JOB_ID_HERE>
```
**(Replace `<YOUR_JOB_ID_HERE>` with the actual `job_id`.)**

You can run this multiple times to see the status change from `pending` to `in_progress` to `completed`.

---

Please execute these commands and let me know the results.