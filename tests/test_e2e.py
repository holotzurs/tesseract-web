import pytest
import threading
import time
import os
import uvicorn
from playwright.sync_api import Page, expect
from ocr import starlette_app

E2E_PORT = 5006
BASE_URL = f"http://127.0.0.1:{E2E_PORT}"

def run_server():
    uvicorn.run(starlette_app, host="127.0.0.1", port=E2E_PORT, log_level="error")

@pytest.fixture(scope="module")
def e2e_server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)
    return BASE_URL

@pytest.fixture
def browser_page(e2e_server, page: Page):
    console_errors = []
    page.on("pageerror", lambda err: console_errors.append(err))
    # Log console messages for debug
    page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.type}: {msg.text}"))
    
    page.goto(e2e_server)
    yield page
    if console_errors:
        pytest.fail(f"JavaScript errors detected: {console_errors}")

def test_sync_ocr_pdf_with_boxes(browser_page):
    """Verify PDF OCR actually shows the canvas and timing info."""
    page = browser_page
    page.reload() # Fresh state
    
    page.check("#include-ocr-bounding-boxes")
    test_pdf = os.path.abspath("static/samples/sample.pdf")
    page.set_input_files("#uploadimage", test_pdf)
    
    page.click("button:has-text('Submit Single File')")
    
    # Wait for the scanning class to appear then disappear
    page.wait_for_selector("main.scanning", timeout=5000)
    page.wait_for_selector("main:not(.scanning)", timeout=20000)
    
    # Assertions
    expect(page.locator("#resulttext")).not_to_be_empty()
    expect(page.locator("#timing-info")).to_be_visible()
    expect(page.locator("#start-time")).not_to_have_text("N/A")
    expect(page.locator("#end-time")).not_to_have_text("N/A")
    
    # Bounding boxes should be on canvas
    expect(page.locator("#ocr-canvas")).to_be_visible()
    
    # Verify canvas has data (not just empty)
    # We can check if height/width are > 0
    canvas_handle = page.locator("#ocr-canvas")
    box = canvas_handle.bounding_box()
    assert box['width'] > 0
    assert box['height'] > 0

def test_ui_logic_persistence(browser_page):
    """Test that reloading the same file resets the UI state (no boxes)."""
    page = browser_page
    page.reload()
    
    test_image = os.path.abspath("static/samples/82092117.png")
    
    # 1. Run OCR with boxes
    page.check("#include-ocr-bounding-boxes")
    page.set_input_files("#uploadimage", test_image)
    page.click("button:has-text('Submit Single File')")
    page.wait_for_selector("main:not(.scanning)", timeout=15000)
    expect(page.locator("#ocr-canvas")).to_be_visible()
    
    # 2. Select same file again (should trigger UI reset)
    page.click("#uploadimage") # Trigger the click listener that clears the value
    page.set_input_files("#uploadimage", test_image)
    time.sleep(0.5) # Wait for JS to process the change event
    
    # 3. Canvas should be hidden now
    expect(page.locator("#ocr-canvas")).to_be_hidden()
    expect(page.locator("#ocr-img")).to_be_visible()
