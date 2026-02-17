# Entrypoint OCR Service

Supports scanning images and pdfs.

Checkout this repository:
```
docker build -t tesseract-ocr-entrypoint .
docker run -dp 3001:80 tesseract-ocr-entrypoint:latest
```
then
Open http://0.0.0.0:3001/ using browser

## REST API

This service provides a REST API endpoint for OCR at `/api/v2/ocr`.

### Usage

You can send a POST request with a JSON payload containing the URL of the file to be processed.

**Example using `curl`:**

1.  Create a `sample.json` file:

    ```json
    {
        "url": "https://www.mathworks.com/help/vision/ref/stop-sign-english.png",
        "language": "en"
    }
    ```

2.  Run the following `curl` command:

    ```bash
    curl -X POST \
    -H "Content-Type: application/json" \
    -d @sample.json \
    http://127.0.0.1:5000/api/v2/ocr
    ```

### Automated Testing

To run the automated tests for this project (without Docker):

1.  **Set up a Virtual Environment**:
    It's highly recommended to use a virtual environment to manage project dependencies. You can use `uv` for this:
    ```bash
    uv venv
    ```

2.  **Activate the Virtual Environment**:
    *   On Unix/macOS:
        ```bash
        source .venv/bin/activate
        ```
    *   On Windows:
        ```bash
        .venv\\Scripts\\activate
        ```

3.  **Install All Dependencies**:
    Once the virtual environment is active, install all project dependencies (including development and test dependencies, as your `requirements.txt` is already set up for this):
    ```bash
    uv pip install -r requirements.txt
    ```

4.  **Run Tests**:
    Execute the tests using `pytest`.
    ```bash
    PYTHONPATH=. pytest tests/test_app.py
    ```

    You should see a report indicating that all tests have passed.

### Testing with a Local PDF File

To test with a local PDF file, you can run a simple Python HTTP server.

1.  Place your `sample.pdf` in a directory.
2.  Navigate to that directory and run the following command to start an HTTP server on port 8000:

    ```bash
    python3 -m http.server 8000 --bind 0.0.0.0
    ```

3.  Update your `sample.json` to point to the local file. If you are running the OCR service in a Docker container, you can use `host.docker.internal` to access the host machine's localhost.

    ```json
    {
        "url": "http://host.docker.internal:8000/sample.pdf",
        "language": "en"
    }
    ```

4.  Now you can use the same `curl` command as before to test the endpoint.
