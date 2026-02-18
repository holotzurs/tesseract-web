Here are sample JSON input and output for each of the endpoints, reflecting the latest changes:

### 1. `/api/ocr` (Synchronous file upload via multipart/form-data)

**Purpose**: Upload a single image or PDF file directly and get an immediate OCR result.

**Input (multipart/form-data)**:
*   `file`: The actual image or PDF file (e.g., `image.png`, `document.pdf`).
*   `language`: The language code for OCR (e.g., `en`, `fr`).

**Example `curl` command to call it (assuming an `image.png` file in the current directory):**
```bash
curl -X POST 
  -F "file=@image.png" 
  -F "language=en" 
  http://127.0.0.1:5000/api/ocr
```

**Output (JSON - Success):**
```json
{
  "duration": "123.45ms",
  "end_time": "2026-02-17T10:30:05.123456",
  "start_time": "2026-02-17T10:30:04.000000",
  "tesseract_version": "5.5.0",
  "text": "This is the OCR'd text from the image.",
  "error": null
}
```

**Output (JSON - Error: File format not supported):**
```json
{
  "duration": "10.15ms",
  "end_time": "2026-02-17T10:30:06.789012",
  "error": "File format not supported",
  "start_time": "2026-02-17T10:30:06.778862",
  "tesseract_version": "5.5.0",
  "text": null
}
```

---

### 2. `/api/v2/ocr` (Synchronous URL-based OCR via JSON)

**Purpose**: Provide a URL to an image or PDF file, and get an immediate OCR result.

**Input (JSON)**:
```json
{
  "url": "https://example.com/some_document.pdf",
  "language": "en"
}
```

**Output (JSON - Success):**
```json
{
  "duration": "456.78ms",
  "end_time": "2026-02-17T10:31:10.987654",
  "start_time": "2026-02-17T10:31:10.530876",
  "tesseract_version": "5.5.0",
  "text": "Text from the PDF at the given URL.",
  "url": "https://example.com/some_document.pdf",
  "error": null
}
```

**Output (JSON - Error: URL is required):**
```json
{
  "duration": "0.10ms",
  "end_time": "2026-02-17T10:31:11.000100",
  "error": "URL is required",
  "start_time": "2026-02-17T10:31:10.999900",
  "tesseract_version": "5.5.0"
}
```

---

### 3. `/api/async_ocr` (Asynchronous Multi-file OCR via JSON)

**Purpose**: Submit multiple files (via URL or Base64) for OCR processing in the background. Returns a job ID immediately.

**Input (JSON)**:
```json
{
  "files": [
    {
      "url": "https://example.com/image_one.png",
      "language": "en"
    },
    {
      "base64": "JVBERi0xLjQKJ...",
      "filename": "document.pdf",
      "language": "fr"
    },
    {
      "url": "https://example.com/image_two.jpg",
      "language": "de"
    }
  ]
}
```
*Note: The `base64` string would be the actual Base64 encoded content of the file.*

**Output (JSON - Success):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "message": "OCR job submitted. Query /api/ocr_status/a1b2c3d4-e5f6-7890-1234-567890abcdef for results.",
  "status": "pending",
  "tesseract_version": "5.5.0"
}
```

---

### 4. `/api/ocr_status/<job_id>` (Synchronous Job Status Query via GET)

**Purpose**: Retrieve the current status and results of an asynchronous OCR job using its `job_id`.

**Input**: GET request to `/api/ocr_status/<job_id>` (e.g., `http://127.0.0.1:5000/api/ocr_status/a1b2c3d4-e5f6-7890-1234-567890abcdef`)

**Output (JSON - Pending):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "pending",
  "results": [],
  "overall_start_time": "2026-02-17T10:35:00.123456",
  "overall_end_time": null,
  "overall_duration": null,
  "error": null
}
```

**Output (JSON - In Progress):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "in_progress",
  "results": [
    {
      "text": "First file processed.",
      "error": null,
      "filename": "image_one.png",
      "source": "https://example.com/image_one.png",
      "language": "en",
      "start_time": "2026-02-17T10:35:01.000000",
      "end_time": "2026-02-17T10:35:01.500000",
      "duration": "500.00ms",
      "tesseract_version": "5.5.0"
    }
  ],
  "overall_start_time": "2026-02-17T10:35:00.123456",
  "overall_end_time": null,
  "overall_duration": null,
  "error": null
}
```

**Output (JSON - Completed):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "completed",
  "results": [
    {
      "text": "Text from image one.",
      "error": null,
      "filename": "image_one.png",
      "source": "https://example.com/image_one.png",
      "language": "en",
      "start_time": "2026-02-17T10:35:01.000000",
      "end_time": "2026-02-17T10:35:01.500000",
      "duration": "500.00ms",
      "tesseract_version": "5.5.0"
    },
    {
      "text": "Text from document two.",
      "error": null,
      "filename": "document.pdf",
      "source": "base64_data",
      "language": "fr",
      "start_time": "2026-02-17T10:35:01.600000",
      "end_time": "2026-02-17T10:35:02.800000",
      "duration": "1200.00ms",
      "tesseract_version": "5.5.0"
    },
    {
      "text": null,
      "error": "File format not supported",
      "filename": "image_two.jpg",
      "source": "https://example.com/image_two.jpg",
      "language": "de",
      "start_time": "2026-02-17T10:35:02.900000",
      "end_time": "2026-02-17T10:35:03.000000",
      "duration": "100.00ms",
      "tesseract_version": "5.5.0"
    }
  ],
  "overall_start_time": "2026-02-17T10:35:00.123456",
  "overall_end_time": "2026-02-17T10:35:03.100000",
  "overall_duration": "2976.54ms",
  "error": null
}
```

**Output (JSON - Failed Job):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "failed",
  "results": [],
  "overall_start_time": "2026-02-17T10:35:00.123456",
  "overall_end_time": "2026-02-17T10:35:00.200000",
  "overall_duration": "76.54ms",
  "error": "Job processing failed: An unexpected error occurred during setup."
}
```

**Output (JSON - Not Found):**
```json
{
  "message": "Job non-existent-job-id not found.",
  "status": "not_found"
}
```