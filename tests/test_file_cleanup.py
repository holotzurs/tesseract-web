
import pytest
import os
import io
import time
from ocr import flask_app as app

TEMP_DIR = "static/temp"

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Ensure our new temp dir exists for the test
    os.makedirs(TEMP_DIR, exist_ok=True)
    with app.test_client() as client:
        yield client

def test_temporary_file_cleanup(client):
    """Test that temporary files are deleted after sync OCR."""
    # 1. Count files before
    initial_files = os.listdir(TEMP_DIR)
    
    # 2. Perform OCR using a real image
    sample_path = "static/samples/82092117.png"
    with open(sample_path, "rb") as f:
        img_data = f.read()

    data = {
        'file': (io.BytesIO(img_data), '82092117.png'),
        'language': 'en',
        'job_id': 'test-job-id',
        'include_ocr_bounding_boxes': 'false'
    }
    response = client.post('/api/ocr', data=data, content_type='multipart/form-data')
    if response.status_code != 200:
        print(f"DEBUG: Response Data: {response.get_data(as_text=True)}")
    assert response.status_code == 200
    
    # 3. Count files after
    # We might need a tiny sleep if it's very fast, but sync should be done
    final_files = os.listdir(TEMP_DIR)
    
    # Assertion: The number of files should be the same as before
    # This will FAIL now because we currently don't delete them.
    assert len(final_files) == len(initial_files), f"Files leaked in {TEMP_DIR}: {set(final_files) - set(initial_files)}"
