
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os
import sys

# We will implement the server in mcp_server.py
SERVER_SCRIPT = "mcp_server.py"

@pytest.mark.asyncio
async def test_list_tools():
    """Test that the MCP server correctly lists its tools."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=os.environ
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            
            tool_names = [tool.name for tool in tools.tools]
            assert "ocr_file" in tool_names
            assert "ocr_url" in tool_names
            assert "submit_async_ocr" in tool_names
            assert "get_job_status" in tool_names

@pytest.mark.asyncio
async def test_ocr_file_tool():
    """Test calling the ocr_file tool."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=os.environ
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            test_image = "static/uploads/test_uploads/82092117.png"
            
            result = await session.call_tool(
                "ocr_file",
                arguments={
                    "path": test_image,
                    "language": "en"
                }
            )
            
            assert not result.isError
            # Check that it's a JSON string containing text and ocr_data
            content = result.content[0].text
            import json
            data = json.loads(content)
            assert "text" in data
            assert "ocr_data" in data
            assert "Attomey General" in data["text"]

@pytest.mark.asyncio
async def test_submit_async_ocr_tool():
    """Test calling the submit_async_ocr tool."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=os.environ
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "submit_async_ocr",
                arguments={
                    "files": [
                        {"url": "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"}
                    ]
                }
            )
            
            assert not result.isError
            import json
            data = json.loads(result.content[0].text)
            assert "job_id" in data
            assert data["status"] == "pending"
