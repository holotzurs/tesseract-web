# Entrypoint OCR Service

Supports scanning images and pdfs.

Checkout this repository:
```
docker build -t tesseract-ocr .
docker run -dp 3000:80 tesseract-ocr:latest
```
then
Open http://0.0.0.0:3000/ using browser
