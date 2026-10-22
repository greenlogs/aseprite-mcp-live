"""P2 fault injection, followed by separately marked real editor recovery."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from websockets.asyncio.client import connect

from aseprite_mcp.backends.cli import CliBackend
from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.commands import AsepriteCommand
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.legacy import worker_tool
from aseprite_mcp.core.protocol import CORE_CAPABILITIES, Handshake, Limits, Result
from conftest import run
from live_support import live_port, editor_process, until


def wire(name="undo", session="s", request_id="once", **extra):
    return json.dumps({"request_id": request_id, "target": {"backend": "live", "session_id": session,
        "document_id": "d1"}, "expected_revision": 0, "action": {"name": name}, **extra})


def attach(executor, backend, session="s"):
    executor.attach_live(backend, Handshake(protocol_version=1, session_id=session,
        aseprite_version="1.3.7", api_version=28, capabilities=sorted(CORE_CAPABILITIES)))


def test_cancelled_waiter_keeps_receipt_and_single_execution():
    class Slow:
        capabilities = CORE_CAPABILITIES
        calls = 0

        async def execute(self, request):
            self.calls += 1
            await asyncio.sleep(.04)
            return Result(request_id=request.request_id, target=request.target, ok=True)

    async def scenario():
        backend = Slow()
        executor = Executor(None)
        attach(executor, backend)
        first = asyncio.create_task(executor.execute(wire()))
        await until(lambda: backend.calls == 1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        conflict = await executor.execute(wire(expected_revision=1))
        assert conflict.error.code == "REQUEST_CONFLICT"
        assert (await executor.execute(wire())).ok
        assert backend.calls == 1 and not executor._inflight and not executor._locks
    run(scenario())


def test_cancelled_cli_thread_finishes_before_duplicate_and_other_file_runs(tmp_path, monkeypatch):
    backend = CliBackend(Limits())
    calls = []

    def execute(request):
        calls.append(request.request_id)
        time.sleep(.12 if request.request_id == "slow" else .01)
        return Result(request_id=request.request_id, target=request.target, ok=True)

    monkeypatch.setattr(backend, "_execute", execute)

    def request(identifier, filename):
        return json.dumps({"request_id": identifier, "target": {"backend": "cli", "path": str(tmp_path / filename)},
                           "action": {"name": "get_document_info"}})

    async def scenario():
        executor = Executor(backend, Limits(timeout_seconds=.03))
        slow = asyncio.create_task(executor.execute(request("slow", "a")))
        await until(lambda: calls)
        slow.cancel()
        with pytest.raises(asyncio.CancelledError):
            await slow
        other = await executor.execute(request("fast", "b"))
        assert other.ok
        queued = await executor.execute(request("queued", "a"))
        assert queued.error.code == "TIMEOUT" and "queued" not in calls
        assert (await executor.execute(request("slow", "a"))).ok
        assert calls.count("slow") == 1
    run(scenario())


@pytest.mark.parametrize("drop", ["before", "after", "late"])
def test_socket_lost_or_late_write_receipt_is_not_replayed(tmp_path, monkeypatch, drop):

    async def scenario():
        limits = Limits(timeout_seconds=.08)
        executor = Executor(None, limits)
        bridge = LiveBridge(executor, RuntimeConfig(port=live_port(), limits=limits))
        async with bridge.lifespan():
            async with connect(bridge.url) as ws:
                hello = Handshake(protocol_version=1, session_id="s", aseprite_version="1.3.7",
                    api_version=28, capabilities=["undo"])
                await ws.send(hello.model_dump_json())
                await ws.recv()
                if drop == "before":
                    await ws.close()
                    await until(lambda: executor.live is None)
                    assert (await executor.execute(wire())).error.code == "NOT_CONNECTED"
                    return
                task = asyncio.create_task(executor.execute(wire()))
                sent = json.loads(await ws.recv())
                if drop == "after":
                    await ws.close()
                    assert (await task).error.code == "RESULT_UNKNOWN"
                else:
                    unknown = await task
                    assert unknown.error.code == "RESULT_UNKNOWN"
                    receipt = Result(request_id=sent["request_id"], target=sent["target"], ok=True).model_dump_json()
                    await ws.send(receipt)
                    await ws.send(receipt)  # duplicate late receipts are ignored
                    assert await executor.execute(wire()) == unknown
                    assert not executor.live.pending
                    with pytest.raises(TimeoutError):
                        await asyncio.wait_for(ws.recv(), .03)
    run(scenario())


def test_old_queued_requests_cannot_enter_new_session():
    class Slow:
        capabilities = CORE_CAPABILITIES
        calls = 0

        async def execute(self, request):
            self.calls += 1
            await asyncio.sleep(.08)
            return Result(request_id=request.request_id, target=request.target, ok=True)

    async def scenario():
        executor = Executor(None)
        old, new = Slow(), Slow()
        attach(executor, old)
        first = asyncio.create_task(executor.execute(wire()))
        queued = asyncio.create_task(executor.execute(wire(request_id="queued")))
        await until(lambda: old.calls == 1)
        executor.detach_live()
        attach(executor, new, "new")
        assert (await first).ok  # receipt belongs to the original caller only
        assert (await queued).error.code == "SESSION_MISMATCH"
        assert not executor._cache and new.calls == 0
    run(scenario())


def test_editor_reconnect_preserves_cli_write_receipt(tmp_path):
    class Disk:
        capabilities = CORE_CAPABILITIES
        calls = 0

        async def execute(self, request):
            self.calls += 1
            return Result(request_id=request.request_id, target=request.target, ok=True)

    async def scenario():
        disk = Disk()
        executor = Executor(disk)
        raw = json.dumps({"request_id": "disk-once", "target": {"backend": "cli", "path": str(tmp_path / "source")},
            "action": {"name": "apply_operations", "operations": [{"op": "create_layer", "ref": "x", "name": "x"}]}})
        first = await executor.execute(raw)
        attach(executor, Disk())
        executor.detach_live()
        attach(executor, Disk(), "new-session")
        assert await executor.execute(raw) == first
        assert disk.calls == 1
    run(scenario())


def test_port_collision_is_explicit_and_never_changes_endpoint():
    async def scenario():
        first = LiveBridge(Executor(None), RuntimeConfig(port=live_port()))
        async with first.lifespan():
            second = LiveBridge(Executor(None), RuntimeConfig(port=live_port()))
            with pytest.raises(OSError, match="choose another --port"):
                async with second.lifespan():
                    pytest.fail("Must not silently change port")
            assert first.url == f"ws://127.0.0.1:{live_port()}"
    run(scenario())


def test_command_timeout_kills_owned_process_and_decode_failure(tmp_path, monkeypatch):
    pid = tmp_path / "pid"
    monkeypatch.setenv("ASEPRITE_PATH", sys.executable)
    script = "import os,time,pathlib;pathlib.Path(" + repr(str(pid)) + ").write_text(str(os.getpid()));time.sleep(10)"
    started = time.perf_counter()
    success, output = AsepriteCommand.run_command(["-c", script], timeout=.4)
    assert not success and "timed out" in output and time.perf_counter() - started < 3
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid.read_text()))
        if handle:
            try:
                code = ctypes.c_ulong()
                assert ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
                assert code.value != 259  # STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
    success, output = AsepriteCommand.run_command(["-c", "import sys;sys.stdout.buffer.write(bytes([255]))"])
    assert not success and "UTF-8" in output
    success, output = AsepriteCommand.run_command(["-c", "import sys;print('diagnostic');sys.exit(7)"])
    assert not success and "7" in output and "diagnostic" in output


def test_cli_read_revision_rejects_external_change_before_start(tmp_path, monkeypatch):
    source = tmp_path / "中文 文件.aseprite"
    source.write_bytes(b"new external contents")
    def forbidden(*args, **kwargs):
        pytest.fail("Conflicting file must not start Aseprite")
    monkeypatch.setattr(AsepriteCommand, "run_command", forbidden)
    raw = json.dumps({"request_id": "stale", "target": {"backend": "cli", "path": str(source)},
        "expected_file_revision": hashlib.sha256(b"old").hexdigest(),
        "action": {"name": "apply_operations", "operations": [{"op": "create_layer", "ref": "x", "name": "x"}]}})
    result = run(Executor(CliBackend(Limits())).execute(raw))
    assert result.error.code == "CONTEXT_CONFLICT"
    assert source.read_bytes() == b"new external contents"


def test_legacy_worker_keeps_loop_responsive_and_same_file_serial(tmp_path):
    calls = []
    async def legacy(filename: str):
        calls.append("start")
        time.sleep(.06)
        calls.append("end")
        return "OK"

    async def scenario():
        fn = worker_tool(legacy)
        jobs = [asyncio.create_task(fn(str(tmp_path / "same"))) for _ in range(2)]
        await until(lambda: calls)
        assert calls == ["start"]
        assert await asyncio.gather(*jobs) == ["OK", "OK"]
        assert calls == ["start", "end", "start", "end"]
    run(scenario())


@pytest.mark.real
def test_real_editor_faults_recovery_and_limits(tmp_path, monkeypatch):

    async def scenario():
        limits = Limits(timeout_seconds=.6)
        executor = Executor(None, limits)
        bridge = LiveBridge(executor, RuntimeConfig(port=live_port(), limits=limits))
        async with bridge.lifespan(), editor_process(tmp_path) as manual:
            await until(lambda: executor.live is not None)
            async def call(name, document=None, revision=None, **params):
                request = {"request_id": uuid4().hex, "target": {"backend": "live", "session_id": executor.session_id},
                           "action": {"name": name, **params}}
                if document is not None:
                    request["target"]["document_id"] = document
                if revision is not None:
                    request["expected_revision"] = revision
                return await executor.execute(json.dumps(request))

            created = await call("create_sprite", width=16, height=16)
            assert created.ok
            document = created.data["document_id"]
            await manual('test_source=app.activeSprite; test_other=Sprite(2,2); return true')
            info = await call("get_document_info", document)
            await manual('for i=1,400 do test_source.layers[1].opacity=i%256 end; return true')
            stale = await call("undo", document, info.revision)
            assert stale.error.code == "REVISION_CONFLICT"
            info = await call("get_document_info", document)
            context = info.context_revision
            await manual('app.activeSprite=test_source; return true')
            stale = await executor.execute(json.dumps({"request_id": uuid4().hex,
                "target": {"backend": "live", "session_id": executor.session_id, "document_id": document},
                "action": {"name": "undo"}, "expected_revision": info.revision, "expected_context": context}))
            assert stale.error.code == "CONTEXT_CONFLICT"
            # Slow one real operation past CPU budget: transaction must roll back.
            await manual('''
local e=__aseprite_mcp_live.editor;e.original_apply=e.apply_one
e.apply_one=function(self,record,op,refs)
  self:original_apply(record,op,refs)
  local start=os.clock();while os.clock()-start<0.27 do end
end
return true
''')
            info = await call("get_document_info", document)
            failed = await call("apply_operations", document, info.revision,
                operations=[{"op": "create_layer", "ref": "x", "name": "rollback"}])
            assert failed.error.code == "LIMIT_EXCEEDED", failed
            assert await manual('return #test_source.layers') == 1
            await manual('local e=__aseprite_mcp_live.editor;e.apply_one=e.original_apply;return true')
            # Execute a real write, then suppress its receipt to emulate a lost acknowledgement.
            original_backend = executor.live
            original_socket = original_backend.socket
            # Hide only this request from the receiver's pending lookup after send.
            original_execute = original_backend.execute
            async def dropped(request):
                await original_socket.send(request.model_dump_json())
                await asyncio.sleep(2)
            # Rollback may advance the event revision; get a fresh value through restored transport.
            original_backend.execute = original_execute
            info = await call("get_document_info", document)
            original_backend.execute = dropped
            raw = json.dumps({"request_id": "lost-real-receipt", "target": {"backend": "live",
                "session_id": executor.session_id, "document_id": document}, "expected_revision": info.revision,
                "action": {"name": "apply_operations", "operations": [{"op": "create_layer", "name": "once", "ref": "x"}]}})
            unknown = await executor.execute(raw)
            assert unknown.error.code == "RESULT_UNKNOWN"
            original_backend.execute = original_execute
            assert await executor.execute(raw) == unknown
            assert await manual('return #test_source.layers') == 2
            # Actual undo command outside MCP and extension reconnect create fresh state.
            await manual('app.activeSprite=test_source;app.undo();return true')
            assert await manual('return #test_source.layers') == 1
            old_session = executor.session_id
            await manual('''
__aseprite_mcp_live:connect();return true
''')
            await until(lambda: executor.session_id not in (None, old_session))
            assert (await executor.execute(raw)).error.code == "SESSION_MISMATCH"
            documents = await call("list_documents")
            current = next(d for d in documents.data["documents"] if d["width"] == 16)
            document = current["document_id"]
            await manual('test_source:close();return true')
            assert (await call("get_document_info", document)).error.code == "INVALID_TARGET"
    run(scenario())
