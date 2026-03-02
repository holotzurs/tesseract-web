# Entrypoint OCR Service

A powerful OCR service supporting images and PDFs, featuring asynchronous multi-file processing, real-time job tracking, and native Model Context Protocol (MCP) support.

## Architecture

The project is designed with a modular architecture to support multiple interfaces:
- **`ocr_engine.py`**: Core OCR logic using Tesseract, PDF processing, and job management.
- **`ocr.py`**: Unified entry point using a Starlette ASGI wrapper. It serves:
    - The Flask-based **Web UI** and **REST API**.
    - The **MCP SSE** (HTTP) server.
- **`mcp_server.py`**: Standalone **MCP Stdio** server for local CLI tool integration.
- **`mcp_tools.py`**: Shared tool definitions used by both MCP transports.

## Getting Started

### Local Development (without Docker)

1.  **System Dependencies**: Ensure you have Tesseract OCR and Poppler installed.
    *   **macOS**: `brew install tesseract poppler`
    *   **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr poppler-utils`

2.  **Set up Virtual Environment**:
    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

3.  **Run the Server**:
    ```bash
    python ocr.py
    ```
    This starts the unified server on `http://localhost:5000/`.
    - **Web UI**: Access via your browser at the root.
    - **MCP SSE**: Endpoint available at `/mcp/sse`.

## MCP Server Support

This application acts as a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server, allowing AI assistants to perform OCR directly on your files.

### Tools and Parameters

All OCR tools (`ocr_file`, `ocr_url`, `submit_async_ocr`) now support an optional parameter:
- **`include_ocr_data`** (boolean, default: `true`): If set to `false`, the server will skip generating detailed bounding box data, returning only the extracted text. This reduces processing time and response size.

### 1. Adding to Gemini CLI

You can add the OCR service to your Gemini session using either transport:

**Option A: HTTP (Recommended if server is already running)**
```javascript
mcp-add({
  name: "ocr-service",
  config: {
    url: "http://localhost:5000/mcp/sse"
  }
})
```

**Option B: Local Stdio (Standalone)**
```javascript
mcp-add({
  name: "ocr-service",
  config: {
    command: "/path/to/your/venv/bin/python",
    args: ["/path/to/your/tesseract-web/mcp_server.py"],
    env: { "PYTHONPATH": "/path/to/your/tesseract-web" }
  }
})
```

### 2. Testing the Integration

**Example Prompt:**
> "Perform OCR on `static/uploads/test_uploads/82092117.png` using the `ocr-service` and check if it contains any names of people."

## Automated Testing

Run the full suite of UI, REST API, and MCP tests:
```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/
```

## API Endpoints

### 1. `/api/ocr` (Synchronous File Upload) - POST
**Input**: `file`, `language` (optional), `include_ocr_data` (optional string "true" or "false").

### 2. `/api/async_ocr` (Asynchronous Multi-file OCR) - POST
**Input (JSON)**: `files` array. Each file object can include `"include_ocr_data": bool`.

### 3. `/api/ocr_status/<job_id>` (Job Status Query) - GET
Retrieve results for an asynchronous job.
