import os
import json
import mcp.types as types
from ocr_engine import _process_single_ocr_task, OCR_JOBS, submit_async_ocr_job

# We need access to configuration, but we want to avoid circular imports.
# In a real app, these would come from a shared config module.
UPLOAD_FOLDER = "./static/uploads"
SUPPORTED_FORMATS = ["png", "jpeg", "jpg", "bmp", "pnm", "gif", "tiff", "webp", "pdf"]

def register_ocr_tools(server):
    """Registers OCR tools to an MCP server instance."""
    
    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="ocr_file",
                description="Perform OCR on a local image or PDF file. Returns JSON with text and bounding boxes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Local path to the file"},
                        "language": {"type": "string", "description": "Language code (e.g., 'en')", "default": "en"},
                    },
                    "required": ["path"],
                },
            ),
            types.Tool(
                name="ocr_url",
                description="Perform OCR on an image or PDF from a URL. Returns JSON with text and bounding boxes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL of the file"},
                        "language": {"type": "string", "description": "Language code (e.g., 'en')", "default": "en"},
                    },
                    "required": ["url"],
                },
            ),
            types.Tool(
                name="submit_async_ocr",
                description="Submit multiple files for asynchronous OCR processing. Returns a job_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "url": {"type": "string"},
                                    "base64": {"type": "string"},
                                    "filename": {"type": "string"},
                                    "language": {"type": "string"}
                                }
                            }
                        },
                    },
                    "required": ["files"],
                },
            ),
            types.Tool(
                name="get_job_status",
                description="Get the status and results of an asynchronous OCR job.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "The unique job ID"},
                    },
                    "required": ["job_id"],
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        if not arguments:
            raise ValueError("Missing arguments")

        if name == "ocr_file":
            path = arguments.get("path")
            if not os.path.exists(path):
                return [types.TextContent(type="text", text=json.dumps({"error": f"File not found at {path}"}))]
            
            file_input = {"filepath": path, "filename": os.path.basename(path), "language": arguments.get("language", "en")}
            result = _process_single_ocr_task(file_input, UPLOAD_FOLDER, SUPPORTED_FORMATS)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "ocr_url":
            file_input = {"url": arguments.get("url"), "language": arguments.get("language", "en")}
            result = _process_single_ocr_task(file_input, UPLOAD_FOLDER, SUPPORTED_FORMATS)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "submit_async_ocr":
            job_id = submit_async_ocr_job(arguments.get("files"), UPLOAD_FOLDER, SUPPORTED_FORMATS)
            return [types.TextContent(type="text", text=json.dumps({"job_id": job_id, "status": "pending"}, indent=2))]

        elif name == "get_job_status":
            job_id = arguments.get("job_id")
            job_data = OCR_JOBS.get(job_id)
            if not job_data:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Job {job_id} not found"}))]
            return [types.TextContent(type="text", text=json.dumps(job_data, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")
