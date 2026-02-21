import os
import pathlib
import requests
import datetime
import re
import uuid
import threading
import base64
import tempfile
import shutil

import pandas as pd
import pdf2image
import pytesseract
from flask import Flask, jsonify, render_template, request
from langcodes import Language
from PIL import Image
from werkzeug.utils import secure_filename

__author__ = "Santhosh Thottingal <santhosh.thottingal@gmail.com>"
__source__ = "https://github.com/santhoshtr/tesseract-web"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
UPLOAD_FOLDER = "./static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SUPPORTED_FORMATS"] = ["png", "jpeg", "jpg", "bmp", "pnm", "gif", "tiff", "webp", "pdf"]

OCR_JOBS = {}
JOB_STATUS = {
    "PENDING": "pending",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "FAILED": "failed"
}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_tesseract_version_string() -> str:
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError:
        return "Not Installed"
    except Exception as e:
        return f"Error: {e}"


def pdf_to_img(pdf_file):
    return pdf2image.convert_from_path(pdf_file)


# NEW: Helper to get text and bounding box data
def _get_ocr_data(image: Image, language: str):
    lang_code = Language.get(language).to_alpha3()
    text = pytesseract.image_to_string(image, lang=lang_code)
    
    # Get bounding box data
    data = pytesseract.image_to_data(image, lang=lang_code, output_type=pytesseract.Output.DATAFRAME)
    
    # Filter out empty rows and format as a list of dicts
    # Keeping only relevant columns: level, text, conf, left, top, width, height
    ocr_data = data.dropna(subset=['text']) # Drop rows where text is NaN (no word found)
    ocr_data = ocr_data[ocr_data['text'].str.strip() != ''] # Drop rows where text is empty/whitespace
    
    # Ensure all required columns are present, fill with default if not (shouldn't happen with image_to_data)
    required_cols = ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']
    for col in required_cols:
        if col not in ocr_data.columns:
            ocr_data[col] = None # Or appropriate default
            
    # Convert to list of dictionaries for JSON serialization
    # Filter out columns that are not directly related to bounding boxes or text value
    json_ready_data = ocr_data[['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']].to_dict(orient='records')
    
    return {"text": text, "ocr_data": json_ready_data}


def ocr_core(image: Image, language="en"):
    # This function will now be a wrapper or can be removed if _get_ocr_data is used directly
    # For now, let's keep it to return only text for compatibility if needed.
    # The actual data extraction will happen in _process_single_ocr_task using _get_ocr_data
    return pytesseract.image_to_string(image, lang=Language.get(language).to_alpha3())


def pdf_to_text(pdf_file_path: str, language="en") -> str:
    # This function now needs to return a list of {"text": ..., "ocr_data": ...} per page
    all_page_results = []
    images = pdf_to_img(pdf_file_path)
    for _pg, img in enumerate(images):
        page_ocr_results = _get_ocr_data(img, language)
        all_page_results.append({
            "page_num": _pg + 1,
            "text": page_ocr_results["text"],
            "ocr_data": page_ocr_results["ocr_data"]
        })
    return all_page_results # Returns a list of dictionaries per page


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
        "filename": file_input.get("filename", "unknown_file"),
        "source": file_input.get("url", "base64_data"),
        "language": file_input.get("language", "en"),
        "text": None,
        "error": None,
        "image_base64": None,
        "ocr_data": [] # Moved to end
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
            # pdf_to_text now returns list of dicts per page
            page_results = pdf_to_text(temp_filepath, language) 
            full_text = []
            all_ocr_data = []
            for page_res in page_results:
                full_text.append(page_res["text"])
                all_ocr_data.append({"page_num": page_res["page_num"], "ocr_data": page_res["ocr_data"]})
            result["text"] = "\n".join(full_text)
            result["ocr_data"] = all_ocr_data
            
            # For PDF, move the temporary file to a permanent name in static/uploads for frontend display
            # We use a unique prefix to avoid collisions
            unique_filename = f"ocr_{uuid.uuid4().hex}_{result['filename']}"
            permanent_filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            shutil.copy(temp_filepath, permanent_filepath)
            result["source"] = f"/static/uploads/{unique_filename}"
            
        else:
            image_obj = Image.open(temp_filepath)
            image_ocr_results = _get_ocr_data(image_obj, language)
            result["text"] = image_ocr_results["text"]
            result["ocr_data"] = [{"page_num": 1, "ocr_data": image_ocr_results["ocr_data"]}] # Wrap in list for consistency

            # Convert image to base64 for frontend display
            with open(temp_filepath, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                result["image_base64"] = f"data:image/{file_extension};base64,{encoded_image}"

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
    start_time_overall = datetime.datetime.now()
    file_input_obj = request.files["file"]
    language = request.form.get("language", default="en")
    
    temp_filepath = None
    try:
        filename = secure_filename(file_input_obj.filename)
        file_extension = pathlib.Path(filename).suffix.lower().lstrip('.')

        if file_extension not in app.config["SUPPORTED_FORMATS"]:
            raise ValueError("File format not supported")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}", dir=app.config["UPLOAD_FOLDER"]) as temp_file:
            file_input_obj.save(temp_file.name)
            temp_filepath = temp_file.name
        
        processed_file_input = {
            "filepath": temp_filepath,
            "filename": filename,
            "language": language
        }
        
        single_result = _process_single_ocr_task(processed_file_input)
        
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        
        # Ensure timing fields are in the result for consistency, at the top
        response_payload = {
            "start_time": start_time_overall.isoformat(),
            "end_time": end_time_overall.isoformat(),
            "duration": f"{duration_overall:.2f}ms",
            **single_result
        }
        
        status_code = 200 if not single_result["error"] else 400
        return jsonify(response_payload), status_code
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
    start_time_overall = datetime.datetime.now()
    if not request.json or 'url' not in request.json:
        end_time_overall = datetime.datetime.now()
        duration_overall = (end_time_overall - start_time_overall).total_seconds() * 1000
        return jsonify(error="URL is required", tesseract_version=get_tesseract_version_string(),
                       start_time=start_time_overall.isoformat(),
                       end_time=end_time_overall.isoformat(),
                       duration=f"{duration_overall:.2f}ms"
        ), 400
    
    file_input = {
        "url": request.json['url'],
        "language": request.json.get('language', 'en')
    }

    try:
        single_result = _process_single_ocr_task(file_input)
        status_code = 200 if not single_result["error"] else 400
        return jsonify(single_result), status_code

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


@app.errorhandler(400)
def bad_request(error):
    response = jsonify({
        "error": "Bad Request",
        "message": error.description,
        "tesseract_version": get_tesseract_version_string()
    })
    response.status_code = 400
    return response

@app.errorhandler(500)
def internal_server_error(error):
    response = jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected server error occurred.",
        "tesseract_version": get_tesseract_version_string()
    })
    response.status_code = 500
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
