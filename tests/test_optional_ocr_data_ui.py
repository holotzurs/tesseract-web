
import pytest
import threading
import time
import os
import uvicorn
from playwright.sync_api import Page
from ocr import starlette_app

def run_server():
    uvicorn.run(starlette_app, host="127.0.0.1", port=5003)

@pytest.fixture(scope="module")
def server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)
    return "http://127.0.0.1:5003"

@pytest.fixture
def browser_context(server, page: Page):
    page.goto(server)
    return page

def test_ui_bounding_box_checkbox_exists(browser_context):
    """Test that the 'Include Bounding Boxes' checkbox exists in the UI."""
    page = browser_context
    # This will FAIL initially as we haven't added the checkbox yet
    assert page.is_visible("#include-ocr-bounding-boxes")
    assert page.is_checked("#include-ocr-bounding-boxes") # Should be checked by default

def test_ui_ocr_no_boxes(browser_context):
    """Test that OCR still shows the image but no boxes when checkbox is unchecked."""
    page = browser_context
    page.uncheck("#include-ocr-bounding-boxes")
    
    # Upload a file
    test_image = os.path.abspath("static/uploads/test_uploads/82092117.png")
    page.set_input_files("#uploadimage", test_image)
    
    # Submit
    page.click("button:has-text('Submit Single File')")
    
    # Wait for processing (scanning class to be removed)
    page.wait_for_selector("main:not(.scanning)", timeout=10000)
    page.wait_for_timeout(1000) # Give it a second to update the textarea
    
    # Verify result textarea has content
    assert len(page.input_value("#resulttext")) > 10
    
    # Verify canvas is hidden but image is visible
    assert page.is_hidden("#ocr-canvas")
    assert page.is_visible("#ocr-img")
