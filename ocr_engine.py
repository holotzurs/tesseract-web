
import os
import pathlib
import requests
import datetime
import uuid
import threading
import base64
import tempfile
import shutil
import pandas as pd
import pdf2image
import pytesseract
from langcodes import Language
from PIL import Image
from werkzeug.utils import secure_filename

# Global job storage and status constants
OCR_JOBS = {}
JOB_STATUS = {
    "PENDING": "pending",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "FAILED": "failed"
}

def get_tesseract_version_string() -> str:
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError:
        return "Not Installed"
    except Exception as e:
        return f"Error: {e}"

def pdf_to_img(pdf_file):
    return pdf2image.convert_from_path(pdf_file)

def _get_ocr_data(image: Image, language: str):
    lang_code = Language.get(language).to_alpha3()
    text = pytesseract.image_to_string(image, lang=lang_code)
    data = pytesseract.image_to_data(image, lang=lang_code, output_type=pytesseract.Output.DATAFRAME)
    width, height = image.size
    
    ocr_data = data.dropna(subset=['text']) 
    ocr_data = ocr_data[ocr_data['text'].str.strip() != ''] 
    
    required_cols = ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']
    for col in required_cols:
        if col not in ocr_data.columns:
            ocr_data[col] = None
            
    json_ready_data = ocr_data[required_cols].to_dict(orient='records')
    
    return {
        "text": text, 
        "ocr_data": json_ready_data,
        "image_width": width,
        "image_height": height
    }

def pdf_to_text(pdf_file_path: str, language="en"):
    all_page_results = []
    images = pdf_to_img(pdf_file_path)
    for _pg, img in enumerate(images):
        page_ocr_results = _get_ocr_data(img, language)
        all_page_results.append({
            "page_num": _pg + 1,
            "text": page_ocr_results["text"],
            "ocr_data": page_ocr_results["ocr_data"],
            "image_width": page_ocr_results["image_width"],
            "image_height": page_ocr_results["image_height"]
        })
    return all_page_results

def _process_single_ocr_task(file_input: dict, upload_folder: str, supported_formats: list) -> dict:
    result = {
        "filename": file_input.get("filename", "unknown_file"),
        "source": file_input.get("url", "base64_data"),
        "language": file_input.get("language", "en"),
        "text": None,
        "error": None,
        "image_base64": None,
        "ocr_data": []
    }
    temp_filepath = None
    start_time = datetime.datetime.now()

    try:
        language = file_input.get("language", "en")

        if "filepath" in file_input:
            temp_filepath = file_input["filepath"]
            result["source"] = f"filepath://{temp_filepath}"
            result["filename"] = file_input.get("filename", pathlib.Path(temp_filepath).name)
        elif "url" in file_input:
            url = file_input["url"]
            response = requests.get(url, stream=True)
            response.raise_for_status()
            suffix = pathlib.Path(url).suffix.lower()
            if not suffix:
                content_type = response.headers.get('Content-Type')
                if content_type and 'pdf' in content_type: suffix = '.pdf'
                elif content_type and 'image' in content_type: suffix = '.png'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_folder) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_filepath = temp_file.name
            result["filename"] = secure_filename(pathlib.Path(url).name)
            result["source"] = url
        elif "base64" in file_input and "filename" in file_input:
            encoded_data = file_input["base64"]
            decoded_data = base64.b64decode(encoded_data)
            filename = secure_filename(file_input["filename"])
            suffix = pathlib.Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_folder) as temp_file:
                temp_file.write(decoded_data)
                temp_filepath = temp_file.name
            result["filename"] = filename
            result["source"] = "base64_data"
        else:
            raise ValueError("Invalid file input")

        file_extension = pathlib.Path(temp_filepath).suffix.lower().lstrip('.')
        if file_extension not in supported_formats:
            raise ValueError("File format not supported")

        if file_extension == "pdf":
            page_results = pdf_to_text(temp_filepath, language) 
            full_text = []
            all_ocr_data = []
            for page_res in page_results:
                full_text.append(page_res["text"])
                all_ocr_data.append({
                    "page_num": page_res["page_num"], 
                    "ocr_data": page_res["ocr_data"],
                    "image_width": page_res["image_width"],
                    "image_height": page_res["image_height"]
                })
            result["text"] = "\n".join(full_text)
            result["ocr_data"] = all_ocr_data
            unique_filename = f"ocr_{uuid.uuid4().hex}_{result['filename']}"
            permanent_filepath = os.path.join(upload_folder, unique_filename)
            shutil.copy(temp_filepath, permanent_filepath)
            result["source"] = f"/static/uploads/{unique_filename}"
        else:
            image_obj = Image.open(temp_filepath)
            image_ocr_results = _get_ocr_data(image_obj, language)
            result["text"] = image_ocr_results["text"]
            result["ocr_data"] = [{
                "page_num": 1, 
                "ocr_data": image_ocr_results["ocr_data"],
                "image_width": image_ocr_results["image_width"],
                "image_height": image_ocr_results["image_height"]
            }]
            with open(temp_filepath, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                result["image_base64"] = f"data:image/{file_extension};base64,{encoded_image}"

    except Exception as e:
        result["error"] = str(e)
    
    result["tesseract_version"] = get_tesseract_version_string()
    return result

def _process_ocr_job(job_id, files_payload, upload_folder, supported_formats):
    OCR_JOBS[job_id]["status"] = JOB_STATUS["IN_PROGRESS"]
    all_results = []
    job_overall_start_time = datetime.datetime.now()

    try:
        for file_input in files_payload:
            single_file_result = _process_single_ocr_task(file_input, upload_folder, supported_formats)
            all_results.append(single_file_result)
        OCR_JOBS[job_id]["results"] = all_results
        OCR_JOBS[job_id]["status"] = JOB_STATUS["COMPLETED"]
    except Exception as e:
        OCR_JOBS[job_id]["status"] = JOB_STATUS["FAILED"]
        OCR_JOBS[job_id]["error"] = f"Job processing failed: {e}"
    finally:
        job_overall_end_time = datetime.datetime.now()
        job_overall_duration = (job_overall_end_time - job_overall_start_time).total_seconds() * 1000
        OCR_JOBS[job_id]["overall_end_time"] = job_overall_end_time.isoformat()
        OCR_JOBS[job_id]["overall_duration"] = f"{job_overall_duration:.2f}ms"

def submit_async_ocr_job(files_payload, upload_folder, supported_formats):
    job_id = str(uuid.uuid4())
    OCR_JOBS[job_id] = {
        "job_id": job_id,
        "status": JOB_STATUS["PENDING"],
        "results": [],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": None,
        "overall_duration": None,
        "error": None
    }
    thread = threading.Thread(target=_process_ocr_job, args=(job_id, files_payload, upload_folder, supported_formats))
    thread.daemon = True
    thread.start()
    return job_id
