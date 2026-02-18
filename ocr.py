import os
import pathlib
import requests
import datetime
import re # Added for regex

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


def get_tesseract_version_string() -> str:
    """Determines the Tesseract version string."""
    try:
        # Assuming pytesseract.get_tesseract_version() returns the cleaned version number
        # based on user's debugging output.
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


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", languages=get_languages(), tesseract_version=get_tesseract_version_string())


@app.route("/api/languages", methods=["GET"])
def listSupportedLanguages():
    return jsonify(languages=get_languages())


@app.route("/api/ocr", methods=["POST"])
def ocr():
    start_time = datetime.datetime.now()
    f = request.files["file"]
    language = request.form.get("language", default="en")
    # create a secure filename
    filename = secure_filename(f.filename)
    file_extension = pathlib.Path(filename).suffix.split(".")[1]
    if file_extension not in app.config["SUPPORTED_FORMATS"]:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds() * 1000
        return jsonify(
            error="File format not supported",
            tesseract_version=get_tesseract_version_string(),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration=f"{duration:.2f}ms"
        )

    # save file to /static/uploads
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    f.save(filepath)

    if file_extension == "pdf":
        # perform OCR on PDF
        text = pdf_to_text(filepath, language)
    else:
        # perform OCR on the processed image
        text = ocr_core(Image.open(filepath), language)

    # remove the processed image
    os.remove(filepath)
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds() * 1000

    return jsonify(
        text=text,
        tesseract_version=get_tesseract_version_string(),
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration=f"{duration:.2f}ms"
    )


@app.route("/api/v2/ocr", methods=["POST"])
def ocr_v2():
    start_time = datetime.datetime.now()
    if not request.json or 'url' not in request.json:
        return jsonify(error="URL is required", tesseract_version=get_tesseract_version_string()), 400
    
    url = request.json['url']
    language = request.json.get('language', 'en')

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify(error=str(e), tesseract_version=get_tesseract_version_string()), 400

    filename = secure_filename(url.split('/')[-1])
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    file_extension = pathlib.Path(filename).suffix.split(".")[-1].lower()
    if file_extension not in app.config["SUPPORTED_FORMATS"]:
        os.remove(filepath)
        return jsonify(error="File format not supported", tesseract_version=get_tesseract_version_string())
        
    if file_extension == "pdf":
        text = pdf_to_text(filepath, language)
    else:
        text = ocr_core(Image.open(filepath), language)
    
    os.remove(filepath)
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds() * 1000

    return jsonify(
        url=url,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration=f"{duration:.2f}ms",
        text=text,
        tesseract_version=get_tesseract_version_string()
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
