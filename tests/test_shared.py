"""Real shared processes, concurrent stdio clients, and editor integration."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import gc
import json
import os
import socket
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import psutil
import pytest

from aseprite_mcp.__main__ import main
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.shared import run_shared_server, shared_connection
from conftest import run
from live_support import editor_process, live_port, until, listener_pids


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@asynccontextmanager
async def client(port, *, profile="core"):
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "aseprite_mcp", "--port", str(port)],
        env=dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE=profile))
    async with stdio_client(params) as streams, ClientSession(*streams, read_timeout_seconds=timedelta(seconds=15)) as session:
        await session.initialize()
        yield session
    gc.collect()
    await asyncio.sleep(.05)


def stop_test_background(port):
    # Only this test's isolated port and recognizable shared child may be stopped.
    for pid in listener_pids("127.0.0.1", port):
        assert pid and pid != os.getpid()
        process = psutil.Process(pid)
        assert "--serve-shared" in process.cmdline()
        assert process.environ()["ASEPRITE_MCP_TEST_OWNER"] == os.environ["ASEPRITE_MCP_TEST_OWNER"]
        process.terminate()
        process.wait(timeout=5)


async def status(session):
    result = await session.call_tool("get_connection_status", {})
    assert not result.isError, result
    return json.loads(result.content[0].text)


async def tool(session, name, **args):
    result = await session.call_tool(name, args)
    assert not result.isError, result
    return json.loads(result.content[0].text)


def test_removed_takeover_flags_and_cli_shared_rejected(monkeypatch):
    for argument in ["--takeover", "--no-takeover"]:
        with pytest.raises(SystemExit) as error:
            main([argument])
        assert error.value.code == 2
    monkeypatch.setenv("ASEPRITE_MCP_TOOL_PROFILE", "cli")
    with pytest.raises(SystemExit) as error:
        main(["--shared"])
    assert error.value.code == 2


@pytest.mark.parametrize("arguments", [[], ["--shared"]])
def test_live_entrypoint_always_uses_shared_proxy(monkeypatch, arguments):
    called = []
    monkeypatch.setenv("ASEPRITE_MCP_TOOL_PROFILE", "core")
    # A leftover setting must never restore the removed behaviour.
    monkeypatch.setenv("ASEPRITE_MCP_TAKEOVER", "1")
    async def proxy(config, profile):
        called.append(profile)
        assert not hasattr(config, "takeover")
    monkeypatch.setattr("aseprite_mcp.shared.run_shared_proxy", proxy)
    monkeypatch.setattr("aseprite_mcp.__main__.create_server", lambda **kwargs: pytest.fail("No direct live startup"))
    main(arguments)
    assert called == ["core"]


def test_concurrent_cold_start_shares_one_process_and_sessions():
    async def scenario():
        port = unused_port()
        ready = asyncio.Event()
        arrived = 0
        owners = []
        async def use():
            nonlocal arrived
            async with client(port) as session:
                owners.append(listener_pids("127.0.0.1", port))
                assert len((await session.list_tools()).tools) == 10
                arrived += 1
                if arrived == 4:
                    ready.set()
                await asyncio.wait_for(ready.wait(), 15)
                # SDK request IDs overlap across sessions; replies stay local.
                assert not (await status(session))["connected"]
                assert not (await status(session))["connected"]
        try:
            await asyncio.gather(*(use() for _ in range(4)))
            assert len(owners[0]) == 1 and all(owner == owners[0] for owner in owners)
            async with client(port) as returning:
                assert listener_pids("127.0.0.1", port) == owners[0]
                assert not (await status(returning))["connected"]
        finally:
            stop_test_background(port)
    run(scenario())


def test_killing_one_proxy_preserves_other_client_and_background():
    async def scenario():
        port = unused_port()
        try:
            async with client(port) as survivor:
                owner = listener_pids("127.0.0.1", port)
                process = subprocess.Popen([sys.executable, "-m", "aseprite_mcp", "--shared", "--port", str(port)],
                    env=dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core"),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    # Initialize the second raw client before forcing its death.
                    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "killed", "version": "1"}}}
                    process.stdin.write((json.dumps(request) + "\n").encode())
                    process.stdin.flush()
                    async with asyncio.timeout(10):
                        response = await asyncio.to_thread(process.stdout.readline)
                    assert json.loads(response)["id"] == 1
                finally:
                    process.terminate()
                    process.wait(timeout=5)
                    process.stdin.close()
                    process.stdout.close()
                assert not (await status(survivor))["connected"]
                assert listener_pids("127.0.0.1", port) == owner
        finally:
            stop_test_background(port)
    run(scenario())


def test_configuration_mismatch_does_not_replace_background():
    async def scenario():
        port = unused_port()
        try:
            async with client(port) as first:
                owner = listener_pids("127.0.0.1", port)
                with pytest.raises(OSError, match="configuration mismatch"):
                    async with shared_connection(RuntimeConfig(port=port), "all"):
                        pytest.fail("Must reject another tool catalog")
                assert listener_pids("127.0.0.1", port) == owner
                assert not (await status(first))["connected"]
        finally:
            stop_test_background(port)
    run(scenario())


def test_shared_preserves_unrelated_listener(monkeypatch):
    async def scenario():
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            monkeypatch.setattr("aseprite_mcp.shared.start_background", lambda *args: pytest.fail("Must not spawn on a listening endpoint"))
            with pytest.raises(OSError, match="no process was terminated"):
                async with shared_connection(RuntimeConfig(port=port), "core"):
                    pytest.fail("Unrelated listener must be preserved")
            assert listener.fileno() >= 0
    run(scenario())


def test_background_exits_after_idle_timeout():
    async def scenario():
        port = unused_port()
        await asyncio.wait_for(run_shared_server(RuntimeConfig(port=port), "core", idle_timeout=.1), 3)
        assert listener_pids("127.0.0.1", port) == set()
    run(scenario())


def test_shared_client_refuses_direct_service_without_replacing_it(monkeypatch):
    from aseprite_mcp.backends.live import LiveBridge
    from aseprite_mcp.core.execution import Executor
    monkeypatch.setattr("aseprite_mcp.shared.start_background", lambda *args: pytest.fail("Must preserve direct service"))
    async def scenario():
        config = RuntimeConfig(port=unused_port())
        bridge = LiveBridge(Executor(None), config)
        async with bridge.lifespan():
            with pytest.raises(OSError, match="Shared connection ended"):
                async with shared_connection(config, "core"):
                    pytest.fail("Must reject direct service")
            assert bridge.server.is_serving() and bridge.executor.live is None
    run(scenario())


def test_backend_failure_closes_proxy_without_replay():
    async def scenario():
        port = unused_port()
        params = [sys.executable, "-m", "aseprite_mcp", "--shared", "--port", str(port)]
        process = subprocess.Popen(params, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core"))
        try:
            await until(lambda: bool(listener_pids("127.0.0.1", port)))
            request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "failure", "version": "1"}}}
            process.stdin.write((json.dumps(request) + "\n").encode())
            process.stdin.flush()
            async with asyncio.timeout(15):
                response = await asyncio.to_thread(process.stdout.readline)
            assert json.loads(response)["id"] == 1
            stop_test_background(port)
            await until(lambda: process.poll() is not None, timeout=5)
            assert listener_pids("127.0.0.1", port) == set()
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
            if listener_pids("127.0.0.1", port):
                stop_test_background(port)
    run(scenario())


@pytest.mark.real
def test_real_editor_shared_clients_keep_canvas_revisions_and_preview(tmp_path):
    async def scenario():
        port = live_port()
        try:
            async with client(port) as first, editor_process(tmp_path) as manual:
                async with asyncio.timeout(20):
                    while not (before := await status(first))["connected"]:
                        await asyncio.sleep(.1)
                session_id = before["session_id"]
                created = await tool(first, "create_sprite", session_id=session_id, width=8, height=8)
                document_id = created["data"]["document_id"]
                async with client(port) as second:
                    assert (await status(second))["session_id"] == session_id
                    assert (await status(first))["mcp_mode"] == "shared"
                    assert (await status(first))["service_pid"] == (await status(second))["service_pid"]
                    listed = await tool(second, "list_documents", session_id=session_id)
                    assert listed["data"]["documents"][0]["document_id"] == document_id
                    operations = [{"op": "pixel", "layer": {"kind": "id", "value": created["data"]["layers"][0]["id"]},
                                   "frame": 1, "x": 1, "y": 1, "rgba": [17,34,51,255]}]
                    # Both clients write against the same revision concurrently.
                    results = await asyncio.gather(*(s.call_tool("apply_operations", {"session_id": session_id,
                        "document_id": document_id, "expected_revision": created["revision"], "operations": operations}) for s in [first, second]))
                    assert sorted(result.isError for result in results) == [False, True]
                    stale = next(result for result in results if result.isError)
                    assert json.loads(stale.content[0].text)["error"]["code"] == "REVISION_CONFLICT"
                    info = await tool(second, "get_document_info", session_id=session_id, document_id=document_id)
                    preview = await first.call_tool("get_preview", {"session_id": session_id,
                        "document_id": document_id, "expected_revision": info["revision"]})
                    assert not preview.isError and [part.type for part in preview.content] == ["text", "image"]
                    assert await manual('local c=app.activeCel;return #app.sprites==1 and not app.fs.isFile(app.activeSprite.filename) and c.image:getPixel(1-c.position.x,1-c.position.y)==app.pixelColor.rgba(17,34,51,255)')
                # Closing the second proxy leaves the first's session and canvas usable.
                assert (await status(first))["session_id"] == session_id
                current = await tool(first, "get_document_info", session_id=session_id, document_id=document_id)
                operations[0]["rgba"] = [255,0,0,255]
                await tool(first, "apply_operations", session_id=session_id, document_id=document_id,
                           expected_revision=current["revision"], operations=operations)
                assert await manual('local c=app.activeCel;return c.image:getPixel(1-c.position.x,1-c.position.y)==app.pixelColor.rgba(255,0,0,255)')
                await manual('__aseprite_mcp_live:disconnect();return true')
        finally:
            stop_test_background(port)
    run(scenario())
