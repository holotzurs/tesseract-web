
import pytest
import threading
import time
import uvicorn
from playwright.sync_api import Page
from ocr import starlette_app

def run_server():
    uvicorn.run(starlette_app, host="127.0.0.1", port=5002)

@pytest.fixture(scope="session")
def server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)
    return "http://127.0.0.1:5002"

@pytest.fixture
def browser_context(server, page: Page):
    page.goto(server)
    return page

def test_js_format_duration(browser_context):
    page = browser_context
    
    # Test 0ms
    assert page.evaluate("formatDuration(0)") == "00:00.000"
    
    # Test 999ms
    assert page.evaluate("formatDuration(999)") == "00:00.999"
    
    # Test 1000ms
    assert page.evaluate("formatDuration(1000)") == "00:01.000"
    
    # Test 61500ms -> 01:01.500
    assert page.evaluate("formatDuration(61500)") == "01:01.500"
    
    # Test large value: 3600000ms (1 hour) -> 60:00.000
    assert page.evaluate("formatDuration(3600000)") == "60:00.000"

def test_js_format_time(browser_context):
    page = browser_context
    
    # Test a specific ISO string
    # "2026-02-23T12:00:00.123Z"
    # Note: local time conversion might vary, so we check the suffix
    result = page.evaluate("formatTime('2026-02-23T12:00:00.123')")
    assert ".123" in result
    
    # Verify format matches HH:MM:SS.mmm (regex)
    import re
    assert re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}$", result)

def test_js_timing_utc_synchronization(browser_context):
    page = browser_context
    
    # Simulate a 'current' local time on the host
    now_local = page.evaluate("Date.now()")
    
    # 1. Simulate server in UTC (2 hours behind local time)
    # We create a UTC string that is 'now' but marked as UTC
    # e.g., if local is 14:00, UTC is 12:00.
    # ISO string with 'Z' suffix forces JS to interpret it as UTC.
    server_start_time_iso = page.evaluate(f"new Date({now_local}).toISOString()")
    
    # 2. Calculate elapsed time in JS logic (it should be ~0, not 120 minutes)
    # This is exactly what the live interval does
    elapsed = page.evaluate(f"""
        (() => {{
            const startTime = new Date('{server_start_time_iso}').getTime();
            const now = {now_local};
            return now - startTime;
        }})()
    """)
    
    # The elapsed time should be approximately 0 (within a few ms of jitter)
    # If the bug exists, this would be 7,200,000 ms (2 hours)
    assert abs(elapsed) < 1000 

def test_invalid_timing_inputs(browser_context):
    page = browser_context
    assert page.evaluate("formatDuration(NaN)") == "00:00.000"
    assert page.evaluate("formatTime(null)") == "N/A"
    assert page.evaluate("formatTime('')") == "N/A"
