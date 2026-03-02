import pytest
import io
import os
from unittest.mock import patch, ANY
from ocr_engine import _process_single_ocr_task

@pytest.fixture
def client():
    from ocr import flask_app
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

@pytest.mark.parametrize("include_data, expected_empty", [
    (True, False),
    (False, True)
])
def test_engine_optional_ocr_data(include_data, expected_empty):
    test_image = "static/uploads/test_uploads/82092117.png"
    upload_folder = "static/uploads"
    formats = ["png", "pdf"]
    
    file_input = {
        "filepath": test_image,
        "filename": "82092117.png",
        "language": "en"
    }
    
    result = _process_single_ocr_task(
        file_input, 
        upload_folder, 
        formats, 
        include_ocr_bounding_boxes=include_data
    )
    
    if expected_empty:
        assert result["ocr_data"] == []
        assert result["image_base64"] is None
    else:
        assert len(result["ocr_data"]) > 0
        assert result["image_base64"] is not None

def test_api_ocr_optional_data(client):
    """Test that the /api/ocr endpoint respects include_ocr_bounding_boxes."""
    # Test True (explicit)
    data_true = {
        'file': (io.BytesIO(b"dummy image"), 'test.png'),
        'language': 'en',
        'include_ocr_bounding_boxes': 'true'
    }
    with patch('ocr._process_single_ocr_task') as mock_process:
        mock_process.return_value = {"ocr_data": [{"page": 1}], "text": "...", "error": None}
        resp = client.post('/api/ocr', data=data_true, content_type='multipart/form-data')
        assert resp.status_code == 200
        mock_process.assert_called_with(ANY, ANY, ANY, include_ocr_bounding_boxes=True)

    # Test False
    data_false = {
        'file': (io.BytesIO(b"dummy image"), 'test.png'),
        'language': 'en',
        'include_ocr_bounding_boxes': 'false'
    }
    with patch('ocr._process_single_ocr_task') as mock_process:
        mock_process.return_value = {"ocr_data": [], "text": "...", "error": None}
        resp = client.post('/api/ocr', data=data_false, content_type='multipart/form-data')
        assert resp.status_code == 200
        mock_process.assert_called_with(ANY, ANY, ANY, include_ocr_bounding_boxes=False)

    # Test Default (should be True)
    data_default = {
        'file': (io.BytesIO(b"dummy image"), 'test.png'),
        'language': 'en'
    }
    with patch('ocr._process_single_ocr_task') as mock_process:
        mock_process.return_value = {"ocr_data": [{"page": 1}], "text": "...", "error": None}
        resp = client.post('/api/ocr', data=data_default, content_type='multipart/form-data')
        assert resp.status_code == 200
        mock_process.assert_called_with(ANY, ANY, ANY, include_ocr_bounding_boxes=True)
