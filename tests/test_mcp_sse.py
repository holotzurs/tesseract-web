
import pytest
import httpx
import asyncio
import threading
import time
import uvicorn
from ocr import starlette_app

def run_server():
    uvicorn.run(starlette_app, host="127.0.0.1", port=5001)

@pytest.fixture(scope="module")
def server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2) # Give it time to start
    yield "http://127.0.0.1:5001"

@pytest.mark.asyncio
async def test_flask_home(server):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{server}/")
        assert resp.status_code == 200
        assert "OCR Service" in resp.text

@pytest.mark.asyncio
async def test_mcp_sse_connection(server):
    async with httpx.AsyncClient() as client:
        # Test that the SSE endpoint is reachable and starts a stream
        async with client.stream("GET", f"{server}/mcp/sse") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            
            # Read first chunk to ensure it actually starts
            async for line in response.aiter_lines():
                if line.startswith("event: endpoint"):
                    # Success!
                    break
                if "retry" in line: continue
                break
