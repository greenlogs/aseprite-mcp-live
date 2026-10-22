"""Direct endpoint contracts and separately marked file-free real UI connection."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from websockets.asyncio.client import connect

from aseprite_mcp.__main__ import main
from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.config import DEFAULT_PORT, RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Handshake
from websockets.exceptions import InvalidStatus
from conftest import run
from live_support import editor_process, until


def test_cli_overrides_env_and_defaults(monkeypatch):
    import aseprite_mcp.__main__ as entry
    monkeypatch.delenv("ASEPRITE_MCP_HOST", raising=False)
    monkeypatch.delenv("ASEPRITE_MCP_PORT", raising=False)
    assert RuntimeConfig.from_env().port == DEFAULT_PORT == 8765
    monkeypatch.setenv("ASEPRITE_MCP_HOST", "::1")
    monkeypatch.setenv("ASEPRITE_MCP_PORT", "8766")
    assert (RuntimeConfig.from_env().host, RuntimeConfig.from_env().port) == ("::1", 8766)
    captured = []
    class Server:
        def run(self, **kwargs):
            assert kwargs == {"transport": "stdio"}
    def create(**kwargs):
        captured.append(kwargs["config"])
        return Server()
    monkeypatch.setattr(entry, "create_server", create)
    main(["--host", "localhost", "--port", "8767"])
    assert (captured[0].host, captured[0].port) == ("127.0.0.1", 8767)
    for args in [["--host", "0.0.0.0"], ["--port", "0"], ["--port", "-1"], ["--port", "65536"], ["--port", "bad"], ["--prot", "8765"]]:
        with pytest.raises(SystemExit) as error:
            main(args)
        assert error.value.code == 2


def test_direct_connection_without_file_access(tmp_path, monkeypatch):
    # Obsolete variables point at an impossible directory: neither side needs it.
    forbidden = tmp_path / "not-a-directory"
    forbidden.write_text("leave this untouched", encoding="utf-8")
    monkeypatch.setenv("ASEPRITE_MCP_CONNECTION_FILE", str(forbidden / "connection.json"))
    monkeypatch.setenv("ASEPRITE_MCP_RUNTIME_DIR", str(forbidden))
    async def scenario():
        executor = Executor(None)
        bridge = LiveBridge(executor, RuntimeConfig())
        async with bridge.lifespan():
            assert bridge.status()["connection_mode"] == "direct"
            assert bridge.status()["authentication"] == "none"
            assert "connection_file" not in bridge.status()
            async with connect(bridge.url) as ws:
                await ws.send(Handshake(protocol_version=1, session_id="s", aseprite_version="1.3.7",
                    api_version=28, capabilities=[]).model_dump_json())
                assert json.loads(await ws.recv())["type"] == "welcome"
        assert forbidden.read_text(encoding="utf-8") == "leave this untouched"
        assert list(tmp_path.iterdir()) == [forbidden]
    run(scenario())


def test_browser_origin_rejected_native_loopback_allowed():
    async def scenario():
        bridge = LiveBridge(Executor(None), RuntimeConfig())
        async with bridge.lifespan():
            for origin in ("https://example.com", "http://localhost", "null"):
                with pytest.raises(InvalidStatus) as error:
                    async with connect(bridge.url, origin=origin):
                        pytest.fail("Browser connections must be rejected")
                assert error.value.response.status_code == 403
            for origin in (None, bridge.url):
                async with connect(bridge.url, origin=origin) as ws:
                    await ws.send(Handshake(protocol_version=1, session_id="native", aseprite_version="1.3.7",
                        api_version=28, capabilities=[]).model_dump_json())
                    assert json.loads(await ws.recv())["type"] == "welcome"
                await until(lambda: bridge.executor.live is None)
    run(scenario())


def test_stdio_cli_endpoint_precedence(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import gc
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_PORT="1", ASEPRITE_MCP_HOST="::1", ASEPRITE_MCP_TOOL_PROFILE="core")
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "aseprite_mcp", "--host", "localhost", "--port", "8767"], env=env)
        async with stdio_client(params) as streams, ClientSession(*streams) as client:
            await client.initialize()
            status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
            assert status["url"] == "ws://127.0.0.1:8767"
            assert status["connection_mode"] == "direct" and not status["connected"]
        gc.collect()
        await asyncio.sleep(.05)
    run(scenario())


@pytest.mark.real
def test_real_stdio_force_kill_restart_without_selecting_file(tmp_path, monkeypatch):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import gc
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core", ASEPRITE_MCP_HOST="127.0.0.1", ASEPRITE_MCP_PORT="8765")
        params = StdioServerParameters(command=sys.executable, args=["-m", "aseprite_mcp"], env=env)
        async def connected(client):
            async with asyncio.timeout(20):
                while True:
                    status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
                    if status["connected"]:
                        return status
                    await asyncio.sleep(.05)
        async with editor_process(tmp_path) as manual:
            async with stdio_client(params) as streams, ClientSession(*streams) as client:
                await client.initialize()
                first = await connected(client)
                assert not (await client.call_tool("create_sprite", {"session_id": first["session_id"], "width": 8, "height": 8})).isError
            gc.collect()
            await asyncio.sleep(.1)
            # The SDK force-killed its child. No unlink, token transfer or UI action.
            async with stdio_client(params) as streams, ClientSession(*streams) as client:
                await client.initialize()
                second = await connected(client)
                assert second["session_id"] != first["session_id"]
                docs = await client.call_tool("list_documents", {"session_id": second["session_id"]})
                assert len(json.loads(docs.content[0].text)["data"]["documents"]) == 1
                old = await client.call_tool("list_documents", {"session_id": first["session_id"]})
                assert old.isError and json.loads(old.content[0].text)["error"]["code"] == "SESSION_MISMATCH"
            gc.collect()
            await asyncio.sleep(.1)
            await manual('__aseprite_mcp_live:disconnect();return true')
    run(scenario())


@pytest.mark.real
def test_real_editor_automatic_start_restart_stop_and_custom_port(tmp_path, monkeypatch):
    async def scenario():
        forbidden = tmp_path / "blocked-discovery-root"
        forbidden.write_text("not a directory", encoding="utf-8")
        monkeypatch.setenv("ASEPRITE_MCP_RUNTIME_DIR", str(forbidden))
        monkeypatch.setenv("ASEPRITE_MCP_CONNECTION_FILE", str(forbidden / "connection.json"))
        executor = Executor(None)
        first = LiveBridge(executor, RuntimeConfig())
        # Start the editor before any service. No config file or connect() call.
        async with editor_process(tmp_path) as manual:
            # Give only production bridge.lua a filesystem-denying environment.
            # Control files for manual GUI actions remain available to the fixture.
            await manual('''
local b=__aseprite_mcp_live
local function blocked() error("Production connection must not open files") end
local env=setmetatable({io=setmetatable({open=blocked},{__index=io})},{__index=_G})
local found=false
for index=1,20 do
  local name=debug.getupvalue(b.start_auto,index)
  if not name then break end
  if name=="_ENV" then debug.setupvalue(b.start_auto,index,env);found=true;break end
end
assert(found,"Expected production Lua module environment")
return true
''')
            state = await manual('return {ready=__aseprite_mcp_live.ready or false,timer=__aseprite_mcp_live.auto_timer~=nil}')
            assert state == {"ready": False, "timer": True}
            async with first.lifespan():
                await until(lambda: executor.live is not None)
                session = executor.session_id
                raw = json.dumps({"request_id": "auto-created", "target": {"backend": "live", "session_id": session},
                    "action": {"name": "create_sprite", "width": 8, "height": 8}})
                assert (await executor.execute(raw)).ok
                # Exercise the only settings dialog; there is no file selector.
                assert await manual('__aseprite_mcp_live:settings();__aseprite_mcp_live.dialog:close();return __aseprite_mcp_live.legacy_settings==nil')
            assert executor.live is None
            # Server restart keeps the endpoint; the editor reconnects without reading files.
            second = LiveBridge(executor, RuntimeConfig())
            async with second.lifespan():
                await until(lambda: executor.session_id not in (None, session))
                assert (await executor.execute(raw)).error.code == "SESSION_MISMATCH"
                assert await manual('return #app.sprites') == 1
                assert await manual('__aseprite_mcp_live:disconnect();return __aseprite_mcp_live.auto_timer==nil')
                await until(lambda: executor.live is None)
                await asyncio.sleep(1.2)
                assert executor.live is None  # manual stop is respected
                await manual('__aseprite_mcp_live.plugin.preferences.auto_connect=true;__aseprite_mcp_live:start_auto();return true')
                await until(lambda: executor.live is not None)
                # Retarget via persisted settings, then start an independent custom port.
                await manual('local b=__aseprite_mcp_live;b:disconnect();b.plugin.preferences.port=8766;b.plugin.preferences.auto_connect=true;b:start_auto();return true')
                await until(lambda: executor.live is None)
                custom_executor = Executor(None)
                async with LiveBridge(custom_executor, RuntimeConfig(port=8766)).lifespan():
                    await until(lambda: custom_executor.live is not None)
                    assert executor.live is None
                    await manual('__aseprite_mcp_live:shutdown();return true')
                    await until(lambda: custom_executor.live is None)
                    assert await manual('return __aseprite_mcp_live.auto_timer==nil and __aseprite_mcp_live.editor==nil')
    run(scenario())
