
import pytest
import threading
import time
import os
import uvicorn
from playwright.sync_api import Page, expect
from ocr import starlette_app

E2E_PORT = 5007
BASE_URL = f"http://127.0.0.1:{E2E_PORT}"

def run_server():
    uvicorn.run(starlette_app, host="127.0.0.1", port=E2E_PORT, log_level="error")

@pytest.fixture(scope="module")
def server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)
    return BASE_URL

@pytest.fixture
def browser_page(server, page: Page):
    page.goto(server)
    return page

def test_split_timing_visibility(browser_page):
    """Test that both Total and Server times are shown in the UI."""
    page = browser_page
    
    # Upload image
    test_image = os.path.abspath("static/uploads/test_uploads/82092117.png")
    page.set_input_files("#uploadimage", test_image)
    
    # Submit
    page.click("button:has-text('Submit Single File')")
    
    # Wait for completion
    page.wait_for_selector("main:not(.scanning)", timeout=15000)
    
    # Verify both fields exist and are populated
    expect(page.locator("#duration")).to_be_visible() # Total Time
    expect(page.locator("#server-time")).to_be_visible() # Server Processing Time
    
    # Verify they don't say N/A
    expect(page.locator("#duration")).not_to_have_text("N/A")
    expect(page.locator("#server-time")).not_to_have_text("N/A")
    
    # Optional: Verify format (mm:ss.SSS)
    import re
    duration_text = page.inner_text("#duration")
    server_text = page.inner_text("#server-time")
    assert re.match(r"^\d{2}:\d{2}\.\d{3}$", duration_text)
    assert re.match(r"^\d{2}:\d{2}\.\d{3}$", server_text)
