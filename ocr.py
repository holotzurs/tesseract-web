import os
import pathlib
import requests
import datetime
import re
import uuid         # NEW
import threading    # NEW
import base64       # NEW
import tempfile     # NEW
import shutil       # NEW

import pdf2image
import pytesseract
from flask import Flask, jsonify, render_template, request
from langcodes import Language
from PIL import Image
from werkzeug.utils import secure_filename

__author__ = "Santhosh Thottingal <santhosh.thottingal@gmail.com>"
__source__ = "https://github.com/santhoshtr/tesseract-web"

app = Flask(__name__)
UPLOAD_FOLDER = "./static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SUPPORTED_FORMATS"] = ["png", "jpeg", "jpg", "bmp", "pnm", "gif", "tiff", "webp", "pdf"]

# NEW: Global job storage and status constants
OCR_JOBS = {}
JOB_STATUS = {
    "PENDING": "pending",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "FAILED": "failed"
}

# Ensure the UPLOAD_FOLDER exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_tesseract_version_string() -> str:
    """Determines the Tesseract version string."""
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError:
        return "Not Installed"
    except Exception as e:
        return f"Error: {e}"


def pdf_to_img(pdf_file):
    return pdf2image.convert_from_path(pdf_file)


def ocr_core(image: Image, language="en"):
    text = pytesseract.image_to_string(image, lang=Language.get(language).to_alpha3())
    return text


def pdf_to_text(pdf_file_path: str, language="en") -> str:
    texts = []
    images = pdf_to_img(pdf_file_path)
    for _pg, img in enumerate(images):
        texts.append(ocr_core(img, language))

    return "\n".join(texts)


def get_languages() -> dict:
    languages = {}
    alpha3codes = pytesseract.get_languages()
    for code in alpha3codes:
        language = Language.get(code)

        languages[language.language] = language.autonym()
    return languages


# NEW: Helper function to process a single OCR task (used by both sync and async)
def _process_single_ocr_task(file_input: dict, job_id: str = None) -> dict:
    result = {
        "text": None,
        "error": None,
        "filename": file_input.get("filename", "unknown_file"),
        "source": file_input.get("url", "base64_data"), # Will be updated if filepath is used directly
        "language": file_input.get("language", "en"),
    }
    temp_filepath = None
    start_time = datetime.datetime.now()

    try:
        language = file_input.get("language", "en")

        # Handle direct filepath if provided (for internal sync calls)
        if "filepath" in file_input:
            temp_filepath = file_input["filepath"]
            result["source"] = f"filepath://{temp_filepath}"
            result["filename"] = file_input.get("filename", pathlib.Path(temp_filepath).name)

        elif "url" in file_input:
            url = file_input["url"]
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            suffix = pathlib.Path(url).suffix.lower()
            if not suffix: # try to guess from content type if no suffix
                content_type = response.headers.get('Content-Type')
                if content_type and 'pdf' in content_type:
                    suffix = '.pdf'
                elif content_type and 'image' in content_type:
                    suffix = '.png' # Default to png if image
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=app.config["UPLOAD_FOLDER"]) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_filepath = temp_file.name
            result["filename"] = secure_filename(pathlib.Path(url).name) # Use URL's name for result
            result["source"] = url
            
        elif "base64" in file_input and "filename" in file_input:
            encoded_data = file_input["base64"]
            decoded_data = base64.b64decode(encoded_data)
            
            filename = secure_filename(file_input["filename"])
            suffix = pathlib.Path(filename).suffix.lower()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=app.config["UPLOAD_FOLDER"]) as temp_file:
                temp_file.write(decoded_data)
                temp_filepath = temp_file.name
            result["filename"] = filename
            result["source"] = "base64_data"
        else:
            raise ValueError("Invalid file input: must contain 'filepath', 'url', or 'base64' with 'filename'")

        if not temp_filepath:
            raise ValueError("No file path determined for OCR processing.")

        file_extension = pathlib.Path(temp_filepath).suffix.lower().lstrip('.')
        if file_extension not in app.config["SUPPORTED_FORMATS"]:
            raise ValueError("File format not supported")

        if file_extension == "pdf":
            result["text"] = pdf_to_text(temp_filepath, language)
        else:
            result["text"] = ocr_core(Image.open(temp_filepath), language)

    except pytesseract.TesseractNotFoundError:
        result["error"] = "Tesseract is not installed or not found in PATH."
    except requests.exceptions.RequestException as e:
        result["error"] = f"Failed to download URL: {e}"
    except ValueError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"An unexpected error occurred: {e}"
    finally:
        if temp_filepath and os.path.exists(temp_filepath) and "filepath" not in file_input: # Only delete if we created it
            os.remove(temp_filepath)
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds() * 1000
        result["start_time"] = start_time.isoformat()
        result["end_time"] = end_time.isoformat()
        result["duration"] = f"{duration:.2f}ms"
        result["tesseract_version"] = get_tesseract_version_string()
    
    return result

# NEW: Background worker function
def _process_ocr_job(job_id, files_payload):
    OCR_JOBS[job_id]["status"] = JOB_STATUS["IN_PROGRESS"]
    all_results = []
    job_overall_start_time = datetime.datetime.now()

    try:
        for file_input in files_payload:
            single_file_result = _process_single_ocr_task(file_input, job_id)
            all_results.append(single_file_result)
        
        OCR_JOBS[job_id]["results"] = all_results
        OCR_JOBS[job_id]["status"] = JOB_STATUS["COMPLETED"]
    except Exception as e:
        OCR_JOBS[job_id]["status"] = JOB_STATUS["FAILED"]
        OCR_JOBS[job_id]["error"] = f"Job processing failed: {e}"
    finally:
        job_overall_end_time = datetime.datetime.now()
        job_overall_duration = (job_overall_end_time - job_overall_start_time).total_seconds() * 1000
        OCR_JOBS[job_id]["overall_start_time"] = job_overall_start_time.isoformat()
        OCR_JOBS[job_id]["overall_end_time"] = job_overall_end_time.isoformat()
        OCR_JOBS[job_id]["overall_duration"] = f"{job_overall_duration:.2f}ms"


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", languages=get_languages(), tesseract_version=get_tesseract_version_string())


@app.route("/api/languages", methods=["GET"])
def listSupportedLanguages():
    return jsonify(languages=get_languages())


@app.route("/api/ocr", methods=["POST"])
def ocr():
    start_time_overall = datetime.datetime.now() # Renamed to avoid conflict
    file_input_obj = request.files["file"]
    language = request.form.get("language", default="en")
    
    temp_filepath = None
    try:
        filename = secure_filename(file_input_obj.filename)
        file_extension = pathlib.Path(filename).suffix.lower().lstrip('.')

        if file_extension not in app.config["SUPPORTED_FORMATS"]:
            raise ValueError("File format not supported")

        # Save uploaded FileStorage to a temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}", dir=app.config["UPLOAD_FOLDER"]) as temp_file:
            file_input_obj.save(temp_file.name)
            temp_filepath = temp_file.name
        
        # Prepare input for _process_single_ocr_task
        processed_file_input = {
            "filepath": temp_filepath,
            "filename": filename,
            "language": language
        }
        
        single_result = _process_single_ocr_task(processed_file_input) # Use the unified helper
        
        response_data = {
            "text": single_result["text"],
            "error": single_result["error"],
            "tesseract_version": single_result["tesseract_version"],
            "start_time": single_result["start_time"],
            "end_time": single_result["end_time"],
            "duration": single_result["duration"]
        }
        status_code = 200 if not single_result["error"] else 400
        return jsonify(response_data), status_code
    except ValueError as e:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(
            error=str(e),
            tesseract_version=get_tesseract_version_string(),
            start_time=start_time_overall.isoformat(),
            end_time=end_time_overall.isoformat(),
            duration=f"{duration_overall:.2f}ms"
        ), 400
    except Exception as e:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(
            error=f"An unexpected error occurred: {e}",
            tesseract_version=get_tesseract_version_string(),
            start_time=start_time_overall.isoformat(),
            end_time=end_time_overall.isoformat(),
            duration=f"{duration_overall:.2f}ms"
        ), 500
    finally:
        if temp_filepath and os.path.exists(temp_filepath):
            os.remove(temp_filepath)


@app.route("/api/v2/ocr", methods=["POST"])
def ocr_v2():
    start_time_overall = datetime.datetime.now() # Renamed to avoid conflict
    if not request.json or 'url' not in request.json:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(error="URL is required", tesseract_version=get_tesseract_version_string(),
                       start_time=start_time_overall.isoformat(),
                       end_time=end_time_overall.isoformat(),
                       duration=f"{duration_overall:.2f}ms"), 400
    
    file_input = {
        "url": request.json['url'],
        "language": request.json.get('language', 'en')
    }

    try:
        single_result = _process_single_ocr_task(file_input) # Use the unified helper
        response_data = {
            "url": single_result["source"],
            "text": single_result["text"],
            "error": single_result["error"],
            "tesseract_version": single_result["tesseract_version"],
            "start_time": single_result["start_time"],
            "end_time": single_result["end_time"],
            "duration": single_result["duration"]
        }
        status_code = 200 if not single_result["error"] else 400
        return jsonify(response_data), status_code

    except ValueError as e:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(
            error=str(e),
            tesseract_version=get_tesseract_version_string(),
            start_time=start_time_overall.isoformat(),
            end_time=end_time_overall.isoformat(),
            duration=f"{duration_overall:.2f}ms"
        ), 400
    except Exception as e:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(
            error=f"An unexpected error occurred: {e}",
            tesseract_version=get_tesseract_version_string(),
            start_time=start_time_overall.isoformat(),
            end_time=end_time_overall.isoformat(),
            duration=f"{duration_overall:.2f}ms"
        ), 500


# NEW: Async Multi-File OCR Endpoint
@app.route("/api/async_ocr", methods=["POST"])
def async_ocr():
    if not request.json or 'files' not in request.json or not isinstance(request.json['files'], list):
        return jsonify(error="Invalid request: 'files' list is required in JSON body"), 400
    
    files_payload = request.json['files']
    job_id = str(uuid.uuid4())
    
    OCR_JOBS[job_id] = {
        "job_id": job_id,
        "status": JOB_STATUS["PENDING"],
        "results": [],
        "overall_start_time": None,
        "overall_end_time": None,
        "overall_duration": None,
        "error": None
    }
    
    thread = threading.Thread(target=_process_ocr_job, args=(job_id, files_payload))
    thread.daemon = True # Allow main program to exit even if thread is running
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "status": JOB_STATUS["PENDING"],
        "message": "OCR job submitted. Query /api/ocr_status/{} for results.".format(job_id),
        "tesseract_version": get_tesseract_version_string()
    }), 202 # 202 Accepted

# NEW: Job Status Endpoint
@app.route("/api/ocr_status/<job_id>", methods=["GET"])
def ocr_status(job_id):
    job_data = OCR_JOBS.get(job_id)
    if job_data:
        return jsonify(job_data), 200
    return jsonify({"status": "not_found", "message": f"Job {job_id} not found."}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
