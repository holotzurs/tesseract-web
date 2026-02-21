import os
import io
import json
from unittest.mock import patch, MagicMock
import pytest
import time # NEW: For potential sleep in async tests
import datetime # NEW: For simulating times in async job results

# Import the Flask app instance from your main application file
from ocr import app, UPLOAD_FOLDER, OCR_JOBS, JOB_STATUS, _process_single_ocr_task, _process_ocr_job # NEW IMPORTS

# Define a consistent mocked Tesseract version
MOCKED_TESSERACT_VERSION = "5.5.0-mock"

@pytest.fixture
def client():
    # Set the app to testing mode
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = os.path.join(UPLOAD_FOLDER, 'test_uploads')
    # Ensure the test upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.test_client() as client:
        yield client
    # Clean up after tests (if os.rmdir needs to be used, ensure dir is empty)
    # import shutil
    # shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)


# Test the home page
@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_home_page(mock_get_tesseract_version_string, client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Tesseract OCR" in response.data # Existing assertion for the title
    assert f"Tesseract OCR Version: {MOCKED_TESSERACT_VERSION}".encode() in response.data


# Test the /api/languages endpoint - no change needed, as it doesn't return tesseract_version
def test_api_languages(client):
    response = client.get('/api/languages')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'languages' in data
    assert isinstance(data['languages'], dict)


# Refactored sync OCR tests to use the new _process_single_ocr_task mock
@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr._process_single_ocr_task')
def test_api_ocr_image_upload(mock_process_single_ocr_task, mock_get_tesseract_version_string, client):
    mock_process_single_ocr_task.return_value = {
        "text": "Mocked OCR Text",
        "ocr_data": [{"page_num": 1, "ocr_data": [{"level": 5, "text": "Mock", "conf": 90, "left": 10, "top": 10, "width": 50, "height": 20}]}], # NEW
        "error": None,
        "filename": "test_image.png",
        "source": "filepath://...",
        "language": "en",
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": datetime.datetime.now().isoformat(),
        "duration": "100.00ms",
        "tesseract_version": MOCKED_TESSERACT_VERSION,
        "image_base64": "data:image/png;base64,mocked_base64_image_content" # NEW
    }
    
    # Mocking FileStorage object
    mock_file = MagicMock()
    mock_file.filename = 'test_image.png'
    mock_file.save.return_value = None # Ensure save method doesn't raise error

    data = {
        'file': (io.BytesIO(b"dummy image content"), 'test_image.png'),
        'language': 'en'
    }
    response = client.post('/api/ocr', data=data, content_type='multipart/form-data')
    
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert 'text' in json_data
    assert json_data['text'] == "Mocked OCR Text"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION
    assert 'start_time' in json_data
    assert 'end_time' in json_data
    assert 'duration' in json_data
    
    # NEW: Assertions for ocr_data and image_base64
    assert 'ocr_data' in json_data
    assert isinstance(json_data['ocr_data'], list)
    assert len(json_data['ocr_data']) > 0
    assert 'page_num' in json_data['ocr_data'][0]
    assert 'ocr_data' in json_data['ocr_data'][0]
    assert isinstance(json_data['ocr_data'][0]['ocr_data'], list)
    assert len(json_data['ocr_data'][0]['ocr_data']) > 0
    assert 'text' in json_data['ocr_data'][0]['ocr_data'][0]
    assert 'left' in json_data['ocr_data'][0]['ocr_data'][0]
    assert 'top' in json_data['ocr_data'][0]['ocr_data'][0]
    assert 'width' in json_data['ocr_data'][0]['ocr_data'][0]
    assert 'height' in json_data['ocr_data'][0]['ocr_data'][0]
    
    assert 'image_base64' in json_data
    assert isinstance(json_data['image_base64'], str)
    assert json_data['image_base64'].startswith("data:image/png;base64,")
    
    # Assert that _process_single_ocr_task was called with appropriate arguments
    assert mock_process_single_ocr_task.called

@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr._process_single_ocr_task')
def test_api_ocr_pdf_upload(mock_process_single_ocr_task, mock_get_tesseract_version_string, client):
    mock_process_single_ocr_task.return_value = {
        "text": "Mocked PDF OCR Text",
        "ocr_data": [{"page_num": 1, "ocr_data": [{"level": 5, "text": "Mock PDF", "conf": 90, "left": 10, "top": 10, "width": 60, "height": 20}]}], # NEW
        "error": None,
        "filename": "test_document.pdf",
        "source": "filepath://...",
        "language": "en",
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": datetime.datetime.now().isoformat(),
        "duration": "200.00ms",
        "tesseract_version": MOCKED_TESSERACT_VERSION
        # No image_base64 for PDF mocks
    }
    
    # Mocking FileStorage object
    mock_file = MagicMock()
    mock_file.filename = 'test_document.pdf'
    mock_file.save.return_value = None # Ensure save method doesn't raise error

    data = {
        'file': (io.BytesIO(b"dummy pdf content"), 'test_document.pdf'),
        'language': 'en'
    }
    response = client.post('/api/ocr', data=data, content_type='multipart/form-data')
    
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert 'text' in json_data
    assert json_data['text'] == "Mocked PDF OCR Text"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION
    assert 'start_time' in json_data
    assert 'end_time' in json_data
    assert 'duration' in json_data

    # NEW: Assertions for ocr_data for PDF
    assert 'ocr_data' in json_data
    assert isinstance(json_data['ocr_data'], list)
    assert len(json_data['ocr_data']) > 0
    assert 'page_num' in json_data['ocr_data'][0]
    assert 'ocr_data' in json_data['ocr_data'][0] # This nested ocr_data is the list of boxes
    assert isinstance(json_data['ocr_data'][0]['ocr_data'], list)
    assert len(json_data['ocr_data'][0]['ocr_data']) > 0
    assert 'text' in json_data['ocr_data'][0]['ocr_data'][0]
    
    # NEW: Assert image_base64 is NOT present for PDF
    assert 'image_base64' not in json_data or json_data['image_base64'] is None
    
    assert mock_process_single_ocr_task.called


# Refactored sync OCR v2 tests to use the new _process_single_ocr_task mock
@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr._process_single_ocr_task')
def test_api_v2_ocr_url(mock_process_single_ocr_task, mock_get_tesseract_version_string, client):
    mock_process_single_ocr_task.return_value = {
        "text": "Mocked OCR from URL",
        "ocr_data": [{"page_num": 1, "ocr_data": [{"level": 5, "text": "Mock URL", "conf": 90, "left": 10, "top": 10, "width": 60, "height": 20}]}], # NEW
        "error": None,
        "filename": "image.png",
        "source": "http://example.com/image.png",
        "language": "en",
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": datetime.datetime.now().isoformat(),
        "duration": "150.00ms",
        "tesseract_version": MOCKED_TESSERACT_VERSION,
        "image_base64": "data:image/png;base64,mocked_base64_image_content_url" # NEW
    }

    data = {
        'url': 'http://example.com/image.png',
        'language': 'en'
    }
    response = client.post('/api/v2/ocr', json=data)

    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert 'text' in json_data
    assert json_data['text'] == "Mocked OCR from URL"
    assert 'duration' in json_data
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION
    assert 'start_time' in json_data
    assert 'end_time' in json_data
    assert 'source' in json_data
    assert json_data['source'] == "http://example.com/image.png"

    # NEW: Assertions for ocr_data and image_base64 for URL
    assert 'ocr_data' in json_data
    assert isinstance(json_data['ocr_data'], list)
    assert len(json_data['ocr_data']) > 0
    assert 'page_num' in json_data['ocr_data'][0]
    assert 'ocr_data' in json_data['ocr_data'][0]
    assert isinstance(json_data['ocr_data'][0]['ocr_data'], list)
    assert len(json_data['ocr_data'][0]['ocr_data']) > 0
    assert 'text' in json_data['ocr_data'][0]['ocr_data'][0]
    
    assert 'image_base64' in json_data
    assert isinstance(json_data['image_base64'], str)
    assert json_data['image_base64'].startswith("data:image/png;base64,")

    mock_process_single_ocr_task.assert_called_once()


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_api_v2_ocr_missing_url(mock_get_tesseract_version_string, client):
    response = client.post('/api/v2/ocr', json={})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "URL is required"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr._process_single_ocr_task')
def test_api_v2_ocr_unsupported_format(mock_process_single_ocr_task, mock_get_tesseract_version_string, client):
    mock_process_single_ocr_task.return_value = {
        "text": None,
        "error": "File format not supported",
        "filename": "document.docx",
        "source": "http://example.com/document.docx",
        "language": "en",
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": datetime.datetime.now().isoformat(),
        "duration": "50.00ms",
        "tesseract_version": MOCKED_TESSERACT_VERSION
    }

    data = {
        'url': 'http://example.com/document.docx',
        'language': 'en'
    }
    response = client.post('/api/v2/ocr', json=data)

    assert response.status_code == 400 # Now returns 400 for errors
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "File format not supported"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION
    
    mock_process_single_ocr_task.assert_called_once()

# NEW: Tests for async multi-file OCR endpoint

@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr.threading.Thread')
@patch('ocr.OCR_JOBS') # Mock the global OCR_JOBS to control its state
def test_async_ocr_submit_success(mock_ocr_jobs, mock_thread, mock_get_tesseract_version_string, client):
    # Setup mock for _process_ocr_job to be passed to thread
    mock_ocr_jobs.__setitem__ = MagicMock() # Allow setting items on the mock dict

    # Prepare a dummy response for _process_single_ocr_task if it were called by _process_ocr_job
    # However, for this test, we are only verifying thread creation, not its execution
    
    files_payload = [
        {"url": "http://example.com/image1.png", "language": "en"},
        {"base64": "JVBERi0x...", "filename": "image2.pdf", "language": "fr"},
    ]
    response = client.post('/api/async_ocr', json={"files": files_payload})

    assert response.status_code == 202
    json_data = json.loads(response.data)
    assert 'job_id' in json_data
    assert json_data['status'] == 'pending'
    assert 'message' in json_data
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION

    # Verify that a thread was started with the correct target and arguments
    mock_thread.assert_called_once()
    args, kwargs = mock_thread.call_args
    mock_thread_instance = mock_thread.return_value # Get the mock instance returned by the constructor
    assert kwargs['target'] == _process_ocr_job
    assert kwargs['args'][0] == json_data['job_id']
    assert kwargs['args'][1] == files_payload
    assert mock_thread_instance.daemon is True # Check the daemon attribute on the instance

@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_async_ocr_invalid_payload(mock_get_tesseract_version_string, client):
    # Test missing 'files' key
    response = client.post('/api/async_ocr', json={})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "Invalid request: 'files' list is required in JSON body"

    # Test 'files' is not a list
    response = client.post('/api/async_ocr', json={"files": "not_a_list"})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "Invalid request: 'files' list is required in JSON body"


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_pending(mock_get_tesseract_version_string, client):
    test_job_id = "test-pending-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["PENDING"],
        "results": [],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": None,
        "overall_duration": None,
        "error": None
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["PENDING"]
    assert 'results' in json_data
    assert len(json_data['results']) == 0
    del OCR_JOBS[test_job_id] # Clean up


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_completed(mock_get_tesseract_version_string, client):
    test_job_id = "test-completed-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["COMPLETED"],
        "results": [{"text": "Hello", "source": "url", "tesseract_version": MOCKED_TESSERACT_VERSION}],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": datetime.datetime.now().isoformat(),
        "overall_duration": "300.00ms",
        "error": None
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["COMPLETED"]
    assert len(json_data['results']) == 1
    assert json_data['results'][0]['text'] == "Hello"
    del OCR_JOBS[test_job_id] # Clean up


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_failed(mock_get_tesseract_version_string, client):
    test_job_id = "test-failed-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["FAILED"],
        "results": [],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": datetime.datetime.now().isoformat(),
        "overall_duration": "50.00ms",
        "error": "Some processing error"
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["FAILED"]
    assert json_data['error'] == "Some processing error"
    del OCR_JOBS[test_job_id] # Clean up


# Helper function to stop patches. This fixture is included for completeness,
# though direct patching in tests often handles cleanup implicitly.
@pytest.fixture(autouse=True)
def cleanup_patches():
    yield
    patch.stopall()



@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_api_v2_ocr_missing_url(mock_get_tesseract_version_string, client):
    response = client.post('/api/v2/ocr', json={})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "URL is required"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr._process_single_ocr_task')
def test_api_v2_ocr_unsupported_format(mock_process_single_ocr_task, mock_get_tesseract_version_string, client):
    mock_process_single_ocr_task.return_value = {
        "text": None,
        "error": "File format not supported",
        "filename": "document.docx",
        "source": "http://example.com/document.docx",
        "language": "en",
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": datetime.datetime.now().isoformat(),
        "duration": "50.00ms",
        "tesseract_version": MOCKED_TESSERACT_VERSION
    }

    data = {
        'url': 'http://example.com/document.docx',
        'language': 'en'
    }
    response = client.post('/api/v2/ocr', json=data)

    assert response.status_code == 400 # Now returns 400 for errors
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "File format not supported"
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION
    
    mock_process_single_ocr_task.assert_called_once()

# NEW: Tests for async multi-file OCR endpoint

@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
@patch('ocr.threading.Thread')
@patch('ocr.OCR_JOBS') # Mock the global OCR_JOBS to control its state
def test_async_ocr_submit_success(mock_ocr_jobs, mock_thread, mock_get_tesseract_version_string, client):
    # Setup mock for _process_ocr_job to be passed to thread
    mock_ocr_jobs.__setitem__ = MagicMock() # Allow setting items on the mock dict

    # Prepare a dummy response for _process_single_ocr_task if it were called by _process_ocr_job
    # However, for this test, we are only verifying thread creation, not its execution
    
    files_payload = [
        {"url": "http://example.com/image1.png", "language": "en"},
        {"base64": "JVBERi0x...", "filename": "image2.pdf", "language": "fr"},
    ]
    response = client.post('/api/async_ocr', json={"files": files_payload})

    assert response.status_code == 202
    json_data = json.loads(response.data)
    assert 'job_id' in json_data
    assert json_data['status'] == 'pending'
    assert 'message' in json_data
    assert 'tesseract_version' in json_data
    assert json_data['tesseract_version'] == MOCKED_TESSERACT_VERSION

    # Verify that a thread was started with the correct target and arguments
    mock_thread.assert_called_once()
    args, kwargs = mock_thread.call_args
    mock_thread_instance = mock_thread.return_value # Get the mock instance returned by the constructor
    assert kwargs['target'] == _process_ocr_job
    assert kwargs['args'][0] == json_data['job_id']
    assert kwargs['args'][1] == files_payload
    assert mock_thread_instance.daemon is True # Check the daemon attribute on the instance

@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_async_ocr_invalid_payload(mock_get_tesseract_version_string, client):
    # Test missing 'files' key
    response = client.post('/api/async_ocr', json={})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "Invalid request: 'files' list is required in JSON body"

    # Test 'files' is not a list
    response = client.post('/api/async_ocr', json={"files": "not_a_list"})
    assert response.status_code == 400
    json_data = json.loads(response.data)
    assert 'error' in json_data
    assert json_data['error'] == "Invalid request: 'files' list is required in JSON body"


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_pending(mock_get_tesseract_version_string, client):
    test_job_id = "test-pending-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["PENDING"],
        "results": [],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": None,
        "overall_duration": None,
        "error": None
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["PENDING"]
    assert 'results' in json_data
    assert len(json_data['results']) == 0
    del OCR_JOBS[test_job_id] # Clean up


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_completed(mock_get_tesseract_version_string, client):
    test_job_id = "test-completed-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["COMPLETED"],
        "results": [{"text": "Hello", "source": "url", "tesseract_version": MOCKED_TESSERACT_VERSION}],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": datetime.datetime.now().isoformat(),
        "overall_duration": "300.00ms",
        "error": None
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["COMPLETED"]
    assert len(json_data['results']) == 1
    assert json_data['results'][0]['text'] == "Hello"
    del OCR_JOBS[test_job_id] # Clean up


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_failed(mock_get_tesseract_version_string, client):
    test_job_id = "test-failed-job-id"
    OCR_JOBS[test_job_id] = {
        "job_id": test_job_id,
        "status": JOB_STATUS["FAILED"],
        "results": [],
        "overall_start_time": datetime.datetime.now().isoformat(),
        "overall_end_time": datetime.datetime.now().isoformat(),
        "overall_duration": "50.00ms",
        "error": "Some processing error"
    }

    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 200
    json_data = json.loads(response.data)
    assert json_data['job_id'] == test_job_id
    assert json_data['status'] == JOB_STATUS["FAILED"]
    assert json_data['error'] == "Some processing error"
    del OCR_JOBS[test_job_id] # Clean up


@patch('ocr.get_tesseract_version_string', return_value=MOCKED_TESSERACT_VERSION)
def test_ocr_status_not_found(mock_get_tesseract_version_string, client):
    test_job_id = "non-existent-job-id"
    response = client.get(f'/api/ocr_status/{test_job_id}')
    assert response.status_code == 404
    json_data = json.loads(response.data)
    assert json_data['status'] == "not_found"
    assert 'message' in json_data


# Helper function to stop patches. This fixture is included for completeness,
# though direct patching in tests often handles cleanup implicitly.
@pytest.fixture(autouse=True)
def cleanup_patches():
    yield
    patch.stopall()
