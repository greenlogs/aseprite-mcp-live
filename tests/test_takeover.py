"""Process-level takeover safety and separately marked real editor recovery."""
import asyncio
from contextlib import contextmanager
import errno
import json
import os
import socket
import subprocess
import sys
from types import SimpleNamespace

import psutil
import pytest

from aseprite_mcp.__main__ import main
from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.backends import takeover
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from conftest import run
from live_support import editor_process, live_port, until


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def service(directory, port):
    env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core", ASEPRITE_MCP_HOST="127.0.0.1",
               ASEPRITE_MCP_PORT=str(port), ASEPRITE_MCP_TAKEOVER="0")
    with (directory / "previous-service.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "aseprite_mcp"], env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()


async def rpc(process, request_id, method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if request_id is not None:
        payload["id"] = request_id
    process.stdin.write((json.dumps(payload) + "\n").encode())
    process.stdin.flush()
    if request_id is None:
        return
    async with asyncio.timeout(15):
        line = await asyncio.to_thread(process.stdout.readline)
    assert line, "Previous MCP service exited unexpectedly"
    response = json.loads(line)
    assert response["id"] == request_id and "error" not in response, response
    return response["result"]


async def old_tool(process, request_id, name, arguments):
    result = await rpc(process, request_id, "tools/call", {"name": name, "arguments": arguments})
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def test_takeover_is_opt_in_and_cli_overrides_environment(monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_TAKEOVER", raising=False)
    assert not RuntimeConfig.from_env().takeover
    monkeypatch.setenv("ASEPRITE_MCP_TAKEOVER", "1")
    assert RuntimeConfig.from_env().takeover
    captured = []
    def create(**kwargs):
        captured.append(kwargs["config"].takeover)
        return SimpleNamespace(run=lambda **kwargs: None)
    monkeypatch.setattr("aseprite_mcp.__main__.create_server", create)
    main(["--no-takeover"])
    monkeypatch.setenv("ASEPRITE_MCP_TAKEOVER", "invalid")
    main(["--takeover"])
    assert captured == [False, True]
    with pytest.raises(ValueError, match="TAKEOVER"):
        RuntimeConfig.from_env()


@pytest.mark.parametrize("executable,arguments,expected", [
    ("python.exe", ["python.exe", "-B", "-m", "aseprite_mcp", "--port", "8765"], True),
    ("python.exe", ["python.exe", "C:/venv/Scripts/aseprite-mcp.exe"], True),
    ("aseprite-mcp.exe", ["aseprite-mcp.exe"], True),
    ("python.exe", ["python.exe", "-c", "import aseprite_mcp"], False),
    ("python.exe", ["python.exe", "other.py", "-m", "aseprite_mcp"], False),
    ("Aseprite.exe", ["Aseprite.exe"], False),
])
def test_only_recognizes_service_entrypoints(executable, arguments, expected):
    process = SimpleNamespace(exe=lambda: executable, cmdline=lambda: arguments)
    assert takeover._is_service(process) == expected


@pytest.mark.parametrize("failure", ["access", "changed", "other_user", "unknown"])
def test_refuses_unverifiable_owner_without_signalling(monkeypatch, failure):
    calls = []
    owner = SimpleNamespace(pid=12345, username=lambda: "other" if failure == "other_user" else "same",
                            cmdline=lambda: [], terminate=lambda: calls.append("terminate"), wait=lambda **kwargs: None)
    monkeypatch.setattr(takeover.psutil, "Process", lambda pid=None: owner if pid else SimpleNamespace(username=lambda: "same"))
    monkeypatch.setattr(takeover, "_is_service", lambda process: True)
    owners = iter([{12345}, {54321}])
    def listeners(*args):
        if failure == "access":
            raise psutil.AccessDenied()
        if failure == "unknown":
            return {None}
        return next(owners)
    monkeypatch.setattr(takeover, "_listener_pids", listeners)
    with pytest.raises(OSError, match="Takeover"):
        takeover.terminate_previous_listener("127.0.0.1", 8765)
    assert calls == []


def test_non_collision_error_never_triggers_takeover(monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError(errno.EACCES, "permission denied")
    monkeypatch.setattr("aseprite_mcp.backends.live.serve", fail)
    monkeypatch.setattr("aseprite_mcp.backends.live.terminate_previous_listener",
                        lambda *args: pytest.fail("Must not signal a process for a non-collision error"))
    async def scenario():
        bridge = LiveBridge(Executor(None), RuntimeConfig(port=unused_port(), takeover=True))
        with pytest.raises(OSError, match="permission denied"):
            async with bridge.lifespan():
                pytest.fail("Listener must fail")
    run(scenario())


def test_bind_retry_never_takes_over_a_second_listener(monkeypatch):
    signals = []
    failures = iter([errno.EADDRINUSE, errno.EADDRINUSE, errno.EACCES])
    async def fail(*args, **kwargs):
        raise OSError(next(failures), "injected listener race")
    monkeypatch.setattr("aseprite_mcp.backends.live.serve", fail)
    monkeypatch.setattr("aseprite_mcp.backends.live.terminate_previous_listener", lambda *args: signals.append(args))
    async def scenario():
        bridge = LiveBridge(Executor(None), RuntimeConfig(port=unused_port(), takeover=True))
        with pytest.raises(OSError, match="injected listener race"):
            async with bridge.lifespan():
                pytest.fail("Competing listener must not be killed again")
    run(scenario())
    assert len(signals) == 1


def test_real_service_process_is_only_replaced_when_enabled(tmp_path):
    async def scenario():
        port = unused_port()
        with service(tmp_path, port) as previous:
            await until(lambda: takeover._listener_pids("127.0.0.1", port) != set())
            bridge = LiveBridge(Executor(None), RuntimeConfig(port=port))
            with pytest.raises(OSError, match="Cannot listen"):
                async with bridge.lifespan():
                    pytest.fail("Default must not take over")
            assert previous.poll() is None
            bridge = LiveBridge(Executor(None), RuntimeConfig(port=port, takeover=True))
            async with bridge.lifespan():
                await until(lambda: previous.poll() is not None)
                assert bridge.status()["url"] == f"ws://127.0.0.1:{port}"
    run(scenario())


def test_unrelated_real_listener_survives_takeover(tmp_path):
    async def scenario():
        port = unused_port()
        script = ("import socket,sys; s=socket.socket(); "
                  f"s.bind(('127.0.0.1',{port})); s.listen(); print('ready',flush=True); sys.stdin.read()")
        process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            assert (await asyncio.to_thread(process.stdout.readline)).strip() == b"ready"
            bridge = LiveBridge(Executor(None), RuntimeConfig(port=port, takeover=True))
            with pytest.raises(OSError, match="unrecognized program"):
                async with bridge.lifespan():
                    pytest.fail("Must preserve unrelated listener")
            assert process.poll() is None
        finally:
            process.terminate()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
    run(scenario())


@pytest.mark.real
def test_real_editor_new_stdio_client_takes_over_unsaved_canvas(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def scenario():
        port = live_port()
        async with editor_process(tmp_path) as manual:
            with service(tmp_path, port) as previous:
                await rpc(previous, 1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                                     "clientInfo": {"name": "previous", "version": "1"}})
                await rpc(previous, None, "notifications/initialized")
                async with asyncio.timeout(20):
                    while True:
                        first = await old_tool(previous, 2, "get_connection_status", {})
                        if first["connected"]:
                            break
                        await asyncio.sleep(.1)
                created = await old_tool(previous, 3, "create_sprite", {"session_id": first["session_id"], "width": 8, "height": 8})
                document = created["data"]
                # Use the real editor API to mark the unsaved canvas, then read
                # and edit it through the replacement MCP connection.
                await manual('app.useTool{tool="pencil",color=Color(17,34,51,255),points={Point(0,0)}};return true')
                params = StdioServerParameters(command=sys.executable,
                    args=["-m", "aseprite_mcp", "--port", str(port), "--takeover"],
                    env=dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core", ASEPRITE_MCP_TAKEOVER="0"))
                async with stdio_client(params) as streams, ClientSession(*streams) as client:
                    await client.initialize()
                    await until(lambda: previous.poll() is not None)
                    async with asyncio.timeout(20):
                        while True:
                            result = await client.call_tool("get_connection_status", {})
                            second = json.loads(result.content[0].text)
                            if second["connected"]:
                                break
                            await asyncio.sleep(.1)
                    assert second["session_id"] != first["session_id"]
                    snapshot = await manual('return {count=#app.sprites,saved=app.fs.isFile(app.activeSprite.filename),pixel=app.activeCel.image:getPixel(0,0)}')
                    assert snapshot == {"count": 1, "saved": False,
                                        "pixel": int.from_bytes(bytes([17,34,51,255]), "little")}
                    old = await client.call_tool("list_documents", {"session_id": first["session_id"]})
                    assert old.isError and json.loads(old.content[0].text)["error"]["code"] == "SESSION_MISMATCH"
                    listed = await client.call_tool("list_documents", {"session_id": second["session_id"]})
                    documents = json.loads(listed.content[0].text)["data"]["documents"]
                    assert len(documents) == 1
                    info = await client.call_tool("get_document_info", {"session_id": second["session_id"], "document_id": documents[0]["document_id"]})
                    state = json.loads(info.content[0].text)
                    assert state["data"]["width"] == document["width"] == 8
                    # A new edit succeeds with the replacement's fresh IDs.
                    edited = await client.call_tool("apply_operations", {"session_id": second["session_id"],
                        "document_id": documents[0]["document_id"], "expected_revision": state["revision"],
                        "operations": [{"op": "pixel", "layer": {"kind": "id", "value": state["data"]["layers"][0]["id"]},
                                        "frame": 1, "x": 1, "y": 1, "rgba": [255,0,0,255]}]})
                    assert not edited.isError, edited
                    assert await manual('return app.activeCel.image:getPixel(1,1)==app.pixelColor.rgba(255,0,0,255)')
                await manual('__aseprite_mcp_live:disconnect();return true')
    run(scenario())
