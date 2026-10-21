"""MCP registration and a real stdio session (no live editor transport)."""
import json
import os
import sys
import asyncio
import gc

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from aseprite_mcp.server import create_server
from aseprite_mcp.tools import canvas
from conftest import ok, run


@pytest.mark.parametrize("profile,count", [("core", 9), ("cli", 116), ("all", 125)])
def test_tool_profiles(profile, count, monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_ENABLE_RAW_LUA", raising=False)
    tools = run(create_server(profile).list_tools())
    names = {tool.name for tool in tools}
    assert len(names) == count
    assert "run_lua_script" not in names
    if profile in {"all", "cli"}:
        assert {"create_canvas", "draw_pixels", "cli_execute"} <= names
    if profile in {"all", "core"}:
        assert {"get_connection_status", "apply_operations"} <= names


def test_raw_lua_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ASEPRITE_MCP_ENABLE_RAW_LUA", "1")
    assert "run_lua_script" in {t.name for t in run(create_server("cli").list_tools())}
    with pytest.raises(ValueError):
        create_server("unknown")


def test_stdio_enumeration_and_mcp_error_flag(tmp_path):
    async def scenario():
        connection = tmp_path / "connection.json"
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core", ASEPRITE_MCP_CONNECTION_FILE=str(connection))
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "aseprite_mcp"], env=env)
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 9
                status = await session.call_tool("get_connection_status", {})
                assert not status.isError
                assert json.loads(status.content[0].text)["connected"] is False
                result = await session.call_tool("get_document_info", {"session_id": "s", "document_id": "d"})
                assert result.isError
                error = json.loads(result.content[0].text)
                assert error["error"]["code"] == "NOT_CONNECTED" and not error["ok"]
                invalid = await session.call_tool("get_document_info", {"session_id": "s"})
                assert invalid.isError and json.loads(invalid.content[0].text)["error"]["code"] == "INVALID_REQUEST"
        # Flush Windows proactor callbacks before asyncio.run closes the loop.
        gc.collect()
        await asyncio.sleep(0.05)
        connection.unlink(missing_ok=True)  # SDK 1.6.0 force-terminates the Windows child.
    run(scenario())


def test_real_cli_through_stdio(tmp_path):
    source = tmp_path / "mcp.aseprite"
    ok(run(canvas.create_canvas(8, 8, source.as_posix())))

    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="cli")
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "aseprite_mcp"], env=env)
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                request = {"request_id": "stdio-info", "target": {"backend": "cli", "path": str(source)},
                           "action": {"name": "get_document_info"}}
                result = await session.call_tool("cli_execute", {"request": request})
                assert not result.isError, result
                data = json.loads(result.content[0].text)
                assert data["ok"] and data["data"]["width"] == 8
        gc.collect()
        await asyncio.sleep(0.05)
    run(scenario())
