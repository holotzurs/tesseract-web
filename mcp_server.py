
import asyncio
from mcp.server.fastmcp import FastMCP
from mcp_tools import register_ocr_tools

# Create an MCP server instance using FastMCP
# This is much simpler and handles most boilerplate
mcp = FastMCP("ocr-service")

# Note: register_ocr_tools was designed for low-level Server
# Let's adjust it or just define tools here directly using FastMCP decorators
# for maximum compatibility with the current SDK.

import os
import json
from ocr_engine import _process_single_ocr_task, OCR_JOBS, submit_async_ocr_job

UPLOAD_FOLDER = "./static/uploads"
SUPPORTED_FORMATS = ["png", "jpeg", "jpg", "bmp", "pnm", "gif", "tiff", "webp", "pdf"]

@mcp.tool()
async def ocr_file(path: str, language: str = "en") -> str:
    """Perform OCR on a local image or PDF file."""
    if not os.path.exists(path):
        return json.dumps({"error": f"File not found at {path}"})
    file_input = {"filepath": path, "filename": os.path.basename(path), "language": language}
    result = _process_single_ocr_task(file_input, UPLOAD_FOLDER, SUPPORTED_FORMATS)
    return json.dumps(result, indent=2)

@mcp.tool()
async def ocr_url(url: str, language: str = "en") -> str:
    """Perform OCR on an image or PDF from a URL."""
    file_input = {"url": url, "language": language}
    result = _process_single_ocr_task(file_input, UPLOAD_FOLDER, SUPPORTED_FORMATS)
    return json.dumps(result, indent=2)

@mcp.tool()
async def submit_async_ocr(files: list[dict]) -> str:
    """Submit multiple files for asynchronous OCR processing."""
    job_id = submit_async_ocr_job(files, UPLOAD_FOLDER, SUPPORTED_FORMATS)
    return json.dumps({"job_id": job_id, "status": "pending"}, indent=2)

@mcp.tool()
async def get_job_status(job_id: str) -> str:
    """Get the status and results of an asynchronous OCR job."""
    job_data = OCR_JOBS.get(job_id)
    if not job_data:
        return json.dumps({"error": f"Job {job_id} not found"})
    return json.dumps(job_data, indent=2)

if __name__ == "__main__":
    mcp.run()
