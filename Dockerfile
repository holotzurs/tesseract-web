FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TESSERACT_CMD=/usr/bin/tesseract

RUN apt-get update \
  && apt-get -y install tesseract-ocr tesseract-ocr-all poppler-utils\
  && pip3 --no-cache-dir install --upgrade pip \
  && rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt

EXPOSE 80

CMD ["uvicorn", "ocr:starlette_app", "--host", "0.0.0.0", "--port", "80"]