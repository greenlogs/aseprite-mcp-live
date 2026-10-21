"""Configuration/atomic discovery contracts and separately marked real UI auto-connect."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from websockets.asyncio.client import connect

from aseprite_mcp.__main__ import main
from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.config import DEFAULT_PORT, RuntimeConfig, discovery_file
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Handshake
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
    for args in [["--host", "0.0.0.0"], ["--port", "-1"], ["--port", "65536"], ["--port", "bad"], ["--prot", "8765"]]:
        with pytest.raises(SystemExit) as error:
            main(args)
        assert error.value.code == 2


def test_atomic_discovery_restart_collision_and_authentication(tmp_path, monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_CONNECTION_FILE", raising=False)
    async def scenario():
        path = discovery_file("127.0.0.1", DEFAULT_PORT)
        path.parent.mkdir()
        path.write_text("stale truncated old process file", encoding="utf-8")
        bridge = LiveBridge(Executor(None), RuntimeConfig())
        async with bridge.lifespan():
            first = json.loads(path.read_text(encoding="utf-8"))
            assert first["url"] == "ws://127.0.0.1:8765"
            assert bridge.status()["automatic_discovery"]
            assert "token" not in bridge.status()
            before = path.read_bytes()
            with pytest.raises(OSError, match="choose another --port"):
                async with LiveBridge(Executor(None), RuntimeConfig()).lifespan():
                    pytest.fail("Occupied fixed port must not fall back")
            assert path.read_bytes() == before
            async with connect(bridge.url) as ws:
                await ws.send(Handshake(protocol_version=1, token="wrong", session_id="s",
                    aseprite_version="1.3.7", api_version=28, capabilities=[]).model_dump_json())
                assert json.loads(await ws.recv())["error"]["code"] == "SESSION_MISMATCH"
        assert not path.exists()
        restarted = LiveBridge(Executor(None), RuntimeConfig())
        async with restarted.lifespan():
            assert restarted.connection_file == path
            assert json.loads(path.read_text())["token"] != first["token"]
            assert not list(path.parent.glob(".connection-*"))
    run(scenario())


def test_automatic_paths_and_ephemeral_legacy_mode(monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_CONNECTION_FILE", raising=False)
    assert discovery_file("::1", 8766).name == "connection-__1-8766.json"
    assert discovery_file("127.0.0.1", 8766) != discovery_file("127.0.0.1", 8765)
    assert not LiveBridge(Executor(None), RuntimeConfig(port=0)).automatic_discovery
    monkeypatch.setenv("ASEPRITE_MCP_RUNTIME_DIR", "relative")
    with pytest.raises(ValueError, match="absolute"):
        discovery_file("127.0.0.1", 8765)


def test_stdio_cli_endpoint_precedence(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import gc
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_PORT="1", ASEPRITE_MCP_HOST="::1", ASEPRITE_MCP_TOOL_PROFILE="core")
        env.pop("ASEPRITE_MCP_CONNECTION_FILE", None)
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "aseprite_mcp", "--host", "localhost", "--port", "8767"], env=env)
        async with stdio_client(params) as streams, ClientSession(*streams) as client:
            await client.initialize()
            status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
            assert status["url"] == "ws://127.0.0.1:8767"
            assert status["automatic_discovery"] and not status["connected"]
        gc.collect()
        await asyncio.sleep(.05)
        # SDK force-kills its own child; the next startup replaces this receipt.
        discovery_file("127.0.0.1", 8767).unlink(missing_ok=True)
    run(scenario())


@pytest.mark.real
def test_real_stdio_force_kill_restart_without_selecting_file(tmp_path, monkeypatch):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import gc
    monkeypatch.delenv("ASEPRITE_MCP_CONNECTION_FILE", raising=False)
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
        async with editor_process(tmp_path, None, automatic=True) as manual:
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
        discovery_file("127.0.0.1", 8765).unlink(missing_ok=True)
    run(scenario())


@pytest.mark.real
def test_real_editor_automatic_start_restart_stop_and_custom_port(tmp_path, monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_CONNECTION_FILE", raising=False)
    async def scenario():
        executor = Executor(None)
        first = LiveBridge(executor, RuntimeConfig())
        # Start the editor before any service. No config file or connect() call.
        async with editor_process(tmp_path, None, automatic=True) as manual:
            state = await manual('return {ready=__aseprite_mcp_live.ready or false,timer=__aseprite_mcp_live.auto_timer~=nil}')
            assert state == {"ready": False, "timer": True}
            async with first.lifespan():
                await until(lambda: executor.live is not None)
                session = executor.session_id
                raw = json.dumps({"request_id": "auto-created", "target": {"backend": "live", "session_id": session},
                    "action": {"name": "create_sprite", "width": 8, "height": 8}})
                assert (await executor.execute(raw)).ok
                # Open both settings dialogs to exercise API 28 widget bindings.
                assert await manual('__aseprite_mcp_live:settings();__aseprite_mcp_live.dialog:close();return true')
            assert executor.live is None
            # Server restart rotates the credential; the editor follows it automatically.
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
