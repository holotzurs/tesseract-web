# Entrypoint OCR Service

Supports scanning images and pdfs, now with asynchronous multi-file processing and real-time job status tracking.

## Getting Started

Checkout this repository:
```
docker build -t tesseract-ocr-entrypoint .
docker run -dp 3001:80 tesseract-ocr-entrypoint:latest
```
Then open `http://localhost:3001/` using your browser.

## API Endpoints

This service provides several REST API endpoints for OCR processing. All endpoints now include the Tesseract OCR version, `start_time`, `end_time`, and `duration` in their responses.

### 1. `/api/ocr` (Synchronous File Upload) - POST

**Purpose**: Upload a single image or PDF file directly and get an immediate OCR result. This is used by the web UI for "Submit Single File (Sync)".

**Input (multipart/form-data)**:
*   `file`: The actual image or PDF file.
*   `language`: The language code for OCR (e.g., `en`, `fr`).

**Example `curl` command (assuming `sample.pdf` is in the current directory):**
```bash
curl -X POST \
  -F "file=@sample.pdf" \
  -F "language=en" \
  http://127.0.0.1:3001/api/ocr
```

**Output (JSON - Success Example):**
```json
{
  "duration": "123.45ms",
  "end_time": "2026-02-17T10:30:05.123456",
  "start_time": "2026-02-17T10:30:04.000000",
  "tesseract_version": "4.1.1",
  "text": "This is the OCR'd text from the document.",
  "error": null
}
```

### 2. `/api/v2/ocr` (Synchronous URL-based OCR) - POST

**Purpose**: Provide a URL to an image or PDF file, and get an immediate OCR result.

**Input (JSON)**:
```json
{
  "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
  "language": "en"
}
```

**Example `curl` command (using `sample.json`):**
```bash
# sample.json content:
# { "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png", "language": "en" }
curl -X POST \
  -H "Content-Type: application/json" \
  -d @sample.json \
  http://127.0.0.1:3001/api/v2/ocr
```

**Output (JSON - Success Example):**
```json
{
  "duration": "456.78ms",
  "end_time": "2026-02-17T10:31:10.987654",
  "start_time": "2026-02-17T10:31:10.530876",
  "tesseract_version": "4.1.1",
  "text": "Text from the image at the given URL.",
  "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
  "error": null
}
```

### 3. `/api/async_ocr` (Asynchronous Multi-file OCR) - POST

**Purpose**: Submit multiple files (via URL or Base64) for OCR processing in the background. Returns a `job_id` immediately. The web UI uses this for "Submit Multiple Files (Async)".

**Input (JSON)**:
```json
{
  "files": [
    {
      "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
      "language": "en"
    },
    {
      "base64": "JVBERi0xLjQKJ...",
      "filename": "document.pdf",
      "language": "fr"
    }
  ]
}
```
*Note: The `base64` string should be the actual Base64 encoded content of the file.*

**Example `curl` command (using `async_job_input.json`):**
```bash
# async_job_input.json content:
# {
#   "files": [
#     { "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png", "language": "en" },
#     { "url": "https://www.africau.edu/images/default/sample.pdf", "language": "en" }
#   ]
# }
curl -X POST \
  -H "Content-Type: application/json" \
  -d @async_job_input.json \
  http://127.0.0.1:3001/api/async_ocr
```
**Important**: Copy the `job_id` from the response of this command!

**Output (JSON - Success Example):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "message": "OCR job submitted. Query /api/ocr_status/a1b2c3d4-e5f6-7890-1234-567890abcdef for results.",
  "status": "pending",
  "tesseract_version": "4.1.1"
}
```

### 4. `/api/ocr_status/<job_id>` (Job Status Query) - GET

**Purpose**: Retrieve the current status and results of an asynchronous OCR job using its `job_id`.

**Example `curl` command (replace with your `job_id`):**
```bash
curl http://127.0.0.1:3001/api/ocr_status/a1b2c3d4-e5f6-7890-1234-567890abcdef
```

**Output (JSON - Completed Example):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "completed",
  "results": [
    {
      "text": "Text from image one.",
      "error": null,
      "filename": "stop-sign-english.png",
      "source": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
      "language": "en",
      "start_time": "2026-02-17T10:35:01.000000",
      "end_time": "2026-02-17T10:35:01.500000",
      "duration": "500.00ms",
      "tesseract_version": "4.1.1"
    },
    {
      "text": "Text from document two.",
      "error": null,
      "filename": "sample.pdf",
      "source": "https://www.africau.edu/images/default/sample.pdf",
      "language": "en",
      "start_time": "2026-02-17T10:35:01.600000",
      "end_time": "2026-02-17T10:35:02.800000",
      "duration": "1200.00ms",
      "tesseract_version": "4.1.1"
    }
  ],
  "overall_start_time": "2026-02-17T10:35:00.123456",
  "overall_end_time": "2026-02-17T10:35:03.100000",
  "overall_duration": "2976.54ms",
  "error": null
}
```

## Automated Testing

To run the automated tests for this project (without Docker):

1.  **Set up a Virtual Environment**:
    It's highly recommended to use a virtual environment to manage project dependencies. You can use `uv` for this:
    ```bash
    uv venv
    ```

2.  **Activate the Virtual Environment**:
    *   On Unix/macOS:
        ```bash
        source .venv/bin/activate
        ```
    *   On Windows:
        ```bash
        .venv\\Scripts\\activate
        ```

3.  **Install All Dependencies**:
    Once the virtual environment is active, install all project dependencies (including development and test dependencies, as your `requirements.txt` is already set up for this):
    ```bash
    uv pip install -r requirements.txt
    ```

4.  **Run Tests**:
    Execute the tests using `pytest`.
    ```bash
    PYTHONPATH=. pytest tests/test_app.py
    ```

    You should see a report indicating that all tests have passed.

## Testing with Local Files

To test with local files (e.g., `sample.pdf`) from your host machine with the Dockerized service, you need to serve them via a simple HTTP server on your host.

1.  **Place your `sample.pdf` (and any other local test files) in your current directory.**
2.  **Start a Python HTTP server on your host machine (in a *separate* terminal):**
    ```bash
    python3 -m http.server 8000 --bind 0.0.0.0
    ```
    Keep this terminal open while testing.
3.  **In your `sample.json` or `async_job_input.json`, use `http://host.docker.internal:8000/<your_file.pdf>`** as the URL to access files served by your host's HTTP server.

---
