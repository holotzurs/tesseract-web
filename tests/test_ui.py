import json
import os
import pathlib
import pytest
from playwright.sync_api import Page, expect

# Assuming the Docker container is running on localhost:3001
BASE_URL = "http://localhost:3001/"

# Absolute paths for test files using pathlib for robustness
TEST_IMAGE_PATH = str(pathb.Path(__file__).parent.parent / "static" / "uploads" / "test_uploads" / "image.png")
TEST_PDF_PATH = str(pathlib.Path(__file__).parent.parent / "static" / "uploads" / "test_uploads" / "test_document.pdf")

def test_initial_view(page: Page):
    """
    Tests the initial state of the UI when the page loads with a simplified layout.
    - Job dashboard should be visible.
    - Visual display elements (image, PDF, canvas) should be hidden.
    """
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')

    # Assert that the job dashboard is visible
    expect(page.locator("#job-dashboard")).to_be_visible()
    expect(page.locator("#job-list")).to_be_visible()
    expect(page.locator(".no-jobs-message")).to_be_visible()
    expect(page.locator(".no-jobs-message")).to_have_text("No active jobs yet.")

    # Assert that visual display elements are hidden
    expect(page.locator("#ocr-img")).to_be_hidden()
    expect(page.locator("#ocr-pdf")).to_be_hidden()
    expect(page.locator("#ocr-canvas")).to_be_hidden()
    
    # Assert that the file input and buttons are visible
    expect(page.locator("#uploadimage")).to_be_visible()
    expect(page.locator("button:has-text('Submit Single File (Sync)')")).to_be_visible()
    expect(page.locator("button:has-text('Submit Multiple Files (Async)')")).to_be_visible()
    expect(page.locator(".resulttext")).to_be_visible()


def test_image_upload_sync_and_display(page: Page):
    """
    Tests uploading an image via sync OCR, checks image display and result text.
    """
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')

    # Upload an image file
    page.set_input_files("input#uploadimage", TEST_IMAGE_PATH)
    page.click("button:has-text('Submit Single File (Sync)')")

    # Expect the image to become visible
    expect(page.locator("#ocr-img")).to_be_visible()
    expect(page.locator("#ocr-pdf")).to_be_hidden()
    expect(page.locator("#ocr-canvas")).to_be_hidden()

    # Check that resulttext contains JSON output
    expect(page.locator("#resulttext")).not_to_have_value("")
    result_json = page.evaluate("document.querySelector('#resulttext').value")
    data = json.loads(result_json)
    assert "text" in data
    assert "tesseract_version" in data
    assert "ocr_data" in data # Even if not visually drawn, the data should be there
    assert "image_base64" in data # Image base64 should be in result

    # Check job dashboard entry
    expect(page.locator(".job-entry")).to_have_count(1)
    expect(page.locator(".job-entry .job-col-status")).to_have_text("completed", timeout=10000)


def test_pdf_upload_sync_and_display(page: Page):
    """
    Tests uploading a PDF via sync OCR, checks PDF display and result text.
    """
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')

    # Upload a PDF file
    page.set_input_files("input#uploadimage", TEST_PDF_PATH)
    page.click("button:has-text('Submit Single File (Sync)')")

    # Expect the PDF embed to become visible
    expect(page.locator("#ocr-pdf")).to_be_visible()
    expect(page.locator("#ocr-img")).to_be_hidden()
    expect(page.locator("#ocr-canvas")).to_be_hidden()
    
    # Check that resulttext contains JSON output
    expect(page.locator("#resulttext")).not_to_have_value("")
    result_json = page.evaluate("document.querySelector('#resulttext').value")
    data = json.loads(result_json)
    assert "text" in data
    assert "tesseract_version" in data
    assert "ocr_data" in data
    assert "image_base64" not in data or data["image_base64"] is None # PDF should not have image_base64

    # Check job dashboard entry
    expect(page.locator(".job-entry")).to_have_count(1)
    expect(page.locator(".job-entry .job-col-status")).to_have_text("completed", timeout=10000)


def test_switching_visual_display_via_job_click(page: Page):
    """
    Tests switching between image and PDF displays by clicking job entries
    in the dashboard. (Simplified to show the correct result in textarea)
    """
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')

    # --- Upload and process an image first ---
    page.set_input_files("input#uploadimage", TEST_IMAGE_PATH)
    page.click("button:has-text('Submit Single File (Sync)')")
    expect(page.locator("#ocr-img")).to_be_visible() # Image is displayed
    expect(page.locator(".job-entry .job-col-status")).to_have_text("completed", timeout=10000)
    
    # Check that resulttext contains JSON output with ocr_data and image_base64
    result_json_image = page.evaluate("document.querySelector('#resulttext').value")
    data_image = json.loads(result_json_image)
    assert "image_base64" in data_image
    
    image_job_locator = page.locator(".job-entry").filter(has_text="image.png")

    # --- Upload and process a PDF ---
    page.set_input_files("input#uploadimage", TEST_PDF_PATH)
    page.click("button:has-text('Submit Single File (Sync)')")
    expect(page.locator("#ocr-pdf")).to_be_visible() # PDF is displayed
    expect(page.locator(".job-entry")).to_have_count(2)
    expect(page.locator(".job-entry").nth(1).locator(".job-col-status")).to_have_text("completed", timeout=10000)

    # Check that resulttext contains JSON output without image_base64
    result_json_pdf = page.evaluate("document.querySelector('#resulttext').value")
    data_pdf = json.loads(result_json_pdf)
    assert "image_base64" not in data_pdf or data_pdf["image_base64"] is None
    
    pdf_job_locator = page.locator(".job-entry").filter(has_text="test_document.pdf")

    # --- Click on the image job entry and verify image display ---
    image_job_locator.click()
    expect(page.locator("#ocr-img")).to_be_visible()
    expect(page.locator("#ocr-pdf")).to_be_hidden()
    expect(page.locator("#ocr-canvas")).to_be_hidden()
    expect(page.locator("#resulttext")).to_have_value(result_json_image) # Check resulttext matches image job

    # --- Click on the PDF job entry and verify PDF display ---
    pdf_job_locator.click()
    expect(page.locator("#ocr-pdf")).to_be_visible()
    expect(page.locator("#ocr-img")).to_be_hidden()
    expect(page.locator("#ocr-canvas")).to_be_hidden()
    expect(page.locator("#resulttext")).to_have_value(result_json_pdf) # Check resulttext matches PDF job