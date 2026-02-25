
import os
import pathlib
import datetime
import tempfile
import uuid
import json
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

# OCR Engine Imports
from ocr_engine import (
    get_tesseract_version_string,
    _process_single_ocr_task,
    OCR_JOBS,
    submit_async_ocr_job
)

# MCP Imports
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# --- Flask App (Web UI & REST API) ---
flask_app = Flask(__name__)
flask_app.config["JSON_SORT_KEYS"] = False
UPLOAD_FOLDER = "./static/uploads"
flask_app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
flask_app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
flask_app.config["SUPPORTED_FORMATS"] = ["png", "jpeg", "jpg", "bmp", "pnm", "gif", "tiff", "webp", "pdf"]

os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)

def get_languages() -> dict:
    import pytesseract
    from langcodes import Language
    languages = {}
    alpha3codes = pytesseract.get_languages()
    for code in alpha3codes:
        language = Language.get(code)
        languages[language.language] = language.autonym()
    return languages

@flask_app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(flask_app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@flask_app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", languages=get_languages(), tesseract_version=get_tesseract_version_string())

@flask_app.route("/api/languages", methods=["GET"])
def listSupportedLanguages():
    return jsonify(languages=get_languages())

@flask_app.route("/api/ocr", methods=["POST"])
def ocr():
    start_time_overall = datetime.datetime.now()
    file_input_obj = request.files["file"]
    language = request.form.get("language", default="en")
    job_id = request.form.get("job_id")
    try:
        filename = secure_filename(file_input_obj.filename)
        file_extension = pathlib.Path(filename).suffix.lower().lstrip('.')
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}", dir=flask_app.config["UPLOAD_FOLDER"]) as temp_file:
            file_input_obj.save(temp_file.name)
            temp_filepath = temp_file.name
        file_input = {"filepath": temp_filepath, "filename": filename, "language": language}
        single_result = _process_single_ocr_task(file_input, flask_app.config["UPLOAD_FOLDER"], flask_app.config["SUPPORTED_FORMATS"])
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        response_payload = {"job_id": job_id, "start_time": start_time_overall.isoformat(), "end_time": end_time_overall.isoformat(), "duration": f"{duration_overall:.2f}ms", **single_result}
        return jsonify(response_payload), 200 if not single_result["error"] else 400
    except Exception as e:
        return jsonify(error=str(e)), 500

@flask_app.route("/api/ocr_status/<job_id>", methods=["GET"])
def ocr_status(job_id):
    job_data = OCR_JOBS.get(job_id)
    if job_data: return jsonify(job_data), 200
    return jsonify({"status": "not_found", "message": f"Job {job_id} not found."}), 404

# --- MCP Server (using FastMCP) ---
mcp = FastMCP("ocr-service")

@mcp.tool()
async def ocr_file(path: str, language: str = "en") -> str:
    """Perform OCR on a local image or PDF file."""
    if not os.path.exists(path): return json.dumps({"error": f"File not found at {path}"})
    file_input = {"filepath": path, "filename": os.path.basename(path), "language": language}
    return json.dumps(_process_single_ocr_task(file_input, flask_app.config["UPLOAD_FOLDER"], flask_app.config["SUPPORTED_FORMATS"]), indent=2)

@mcp.tool()
async def ocr_url(url: str, language: str = "en") -> str:
    """Perform OCR on a URL."""
    file_input = {"url": url, "language": language}
    return json.dumps(_process_single_ocr_task(file_input, flask_app.config["UPLOAD_FOLDER"], flask_app.config["SUPPORTED_FORMATS"]), indent=2)

@mcp.tool()
async def submit_async_ocr(files: list[dict]) -> str:
    """Submit async job."""
    return submit_async_ocr_job(files, flask_app.config["UPLOAD_FOLDER"], flask_app.config["SUPPORTED_FORMATS"])

@mcp.tool()
async def get_job_status(job_id: str) -> str:
    """Check job status."""
    return json.dumps(OCR_JOBS.get(job_id, {"error": "not found"}), indent=2)

# SSE Transport
sse_transport = SseServerTransport("/mcp/messages")

async def handle_sse(request):
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        # We access the internal low-level server of FastMCP for the manual run
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options()
        )

async def handle_messages(request):
    return await sse_transport.handle_post_message(request.scope, request.receive)

# --- Combined ASGI Application ---
# The order of routes matters: more specific routes should come first.
starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/mcp/sse", endpoint=handle_sse),
        Route("/mcp/messages", endpoint=handle_messages, methods=["POST"]),
        Mount("/", app=WsgiToAsgi(flask_app))
    ]
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
