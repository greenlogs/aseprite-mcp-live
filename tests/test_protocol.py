"""Contract tests. Live backends here are simulations, not editor validation."""
import asyncio
import json
from pathlib import Path

import pytest

from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import (
    BackendError, CORE_CAPABILITIES, ErrorCode, Handshake, Limits, PngPayload,
    Request, Result, Welcome, negotiate, parse_request,
)
from conftest import run


def wire(action="get_document_info", backend="live", **changes):
    target = {"backend": "live", "session_id": "session-1", "document_id": "doc-1"}
    if backend == "cli":
        target = {"backend": "cli", "path": "/tmp/test.aseprite"}
    request = {"request_id": "request-1", "target": target, "action": {"name": action}}
    request.update(changes)
    return request


def hello(**changes):
    fields = dict(protocol_version=1, token="secret", session_id="session-1",
                  aseprite_version="1.3.7", api_version=28, capabilities=sorted(CORE_CAPABILITIES))
    fields.update(changes)
    return Handshake(**fields)


class FakeBackend:
    capabilities = CORE_CAPABILITIES

    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    async def execute(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return Result(request_id=request.request_id, target=request.target, ok=True, revision=3, data={})


def attached(error=None, limits=None):
    backend = FakeBackend(error)
    executor = Executor(FakeBackend(), limits)
    executor.attach_live(backend, hello(), "secret")
    return executor, backend


def test_normal_request_and_defaults():
    request = parse_request(json.dumps(wire()), Limits())
    assert request.protocol_version == 1
    assert request.target.document_id == "doc-1"
    assert run(attached()[0].execute(request.model_dump_json())).ok


@pytest.mark.parametrize("change", [
    {"unexpected": True}, {"request_id": ""}, {"protocol_version": "1"},
    {"action": {"name": "arbitrary_lua"}},
    {"action": {"name": "get_preview"}},
    {"target": {"backend": "live", "session_id": "s"}},
    {"action": {"name": "apply_operations", "operations": []}, "expected_revision": 0},
    {"expected_revision": -1},
])
def test_invalid_request(change):
    result = run(attached()[0].execute(json.dumps(wire(**change))))
    assert result.error.code == ErrorCode.INVALID_REQUEST


@pytest.mark.parametrize("raw", ["{", b"\xff", "null", "[]"])
def test_malformed_messages(raw):
    assert run(attached()[0].execute(raw)).error.code == ErrorCode.INVALID_REQUEST


def test_version_and_startup_authentication():
    for change, code in [({"protocol_version": 2}, ErrorCode.VERSION_MISMATCH),
                         ({"token": "wrong"}, ErrorCode.SESSION_MISMATCH),
                         ({"api_version": 27}, ErrorCode.UNSUPPORTED_CAPABILITY)]:
        with pytest.raises(BackendError) as error:
            negotiate(hello(**change), "secret")
        assert error.value.code == code
    assert negotiate(hello(capabilities=["get_document_info", "future"]), "secret") == {"get_document_info"}
    result = run(attached()[0].execute(json.dumps(wire(protocol_version=2))))
    assert result.error.code == ErrorCode.VERSION_MISMATCH


def test_no_fallback_and_stale_session():
    cli = FakeBackend()
    executor = Executor(cli)
    assert run(executor.execute(json.dumps(wire()))).error.code == ErrorCode.NOT_CONNECTED
    assert cli.calls == 0
    executor.attach_live(FakeBackend(), hello(), "secret")
    request = wire()
    request["target"]["session_id"] = "old-session"
    assert run(executor.execute(json.dumps(request))).error.code == ErrorCode.SESSION_MISMATCH
    with pytest.raises(BackendError):
        executor.attach_live(FakeBackend(), hello(session_id="second"), "secret")


def test_capability_negotiation_is_enforced():
    executor = Executor(FakeBackend())
    executor.attach_live(FakeBackend(), hello(capabilities=[]), "secret")
    assert run(executor.execute(json.dumps(wire()))).error.code == ErrorCode.UNSUPPORTED_CAPABILITY


@pytest.mark.parametrize("code", [ErrorCode.REVISION_CONFLICT, ErrorCode.CONTEXT_CONFLICT,
    ErrorCode.INVALID_TARGET, ErrorCode.EXECUTION_FAILED, ErrorCode.RESULT_UNKNOWN, ErrorCode.TIMEOUT])
def test_backend_error_mapping(code):
    executor, _ = attached(BackendError(code, "simulated failure"))
    result = run(executor.execute(json.dumps(wire())))
    assert not result.ok and result.error.code == code and result.data is None


def test_deduplication_and_payload_conflict():
    async def scenario():
        executor, backend = attached()
        raw = json.dumps(wire())
        results = await asyncio.gather(executor.execute(raw), executor.execute(raw))
        assert results[0] == results[1] and backend.calls == 1
        request = wire()
        request["target"]["document_id"] = "doc-2"
        assert (await executor.execute(json.dumps(request))).error.code == ErrorCode.REQUEST_CONFLICT
        executor.detach_live()
        assert (await executor.execute(raw)).error.code == ErrorCode.NOT_CONNECTED
    run(scenario())


def test_limits_and_batch_references():
    edit = {"op": "rectangle", "layer": {"kind": "ref", "value": "new"},
            "x": 0, "y": 0, "width": 4, "height": 4, "rgba": [1, 2, 3, 255]}
    request = wire("apply_operations", expected_revision=2)
    request["action"]["operations"] = [{"op": "create_layer", "name": "a", "ref": "new"}, edit]
    parsed = parse_request(json.dumps(request), Limits())
    assert parsed.action.operations[1].frame == 1 and parsed.action.operations[1].filled
    for limits in [Limits(max_operations=1), Limits(max_pixels=8), Limits(max_message_bytes=1)]:
        with pytest.raises(BackendError) as error:
            parse_request(json.dumps(request), limits)
        assert error.value.code == ErrorCode.LIMIT_EXCEEDED
    for field, value in [("x", -1), ("frame", 0), ("rgba", [1, 2, 3, 256])]:
        invalid = json.loads(json.dumps(request))
        invalid["action"]["operations"][1][field] = value
        with pytest.raises(BackendError):
            parse_request(json.dumps(invalid), Limits())
    request["action"]["operations"].reverse()
    with pytest.raises(BackendError):
        parse_request(json.dumps(request), Limits())


def test_runtime_config(monkeypatch):
    monkeypatch.setenv("ASEPRITE_MCP_MAX_OPERATIONS", "12")
    assert RuntimeConfig.from_env().limits.max_operations == 12
    assert RuntimeConfig().token != RuntimeConfig().token
    with pytest.raises(ValueError):
        RuntimeConfig(host="0.0.0.0")


def test_png_payload_contract():
    import base64
    import io
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGBA", (1, 1)).save(buffer, format="PNG")
    raw = buffer.getvalue()
    png = PngPayload(data=base64.b64encode(raw).decode(), width=1, height=1, frame=1, scale=1)
    assert png.decode(Limits()) == raw
    with pytest.raises(BackendError):
        png.decode(Limits(max_png_bytes=1))
    with pytest.raises(BackendError):
        PngPayload(data="!!!", width=1, height=1, frame=1, scale=1).decode(Limits())


def test_mismatched_receipt_is_unknown():
    class Wrong(FakeBackend):
        async def execute(self, request):
            return Result(request_id="other", target=request.target, ok=True)
    executor = Executor(FakeBackend())
    executor.attach_live(Wrong(), hello(), "secret")
    assert run(executor.execute(json.dumps(wire()))).error.code == ErrorCode.RESULT_UNKNOWN


def test_live_deadline_distinguishes_unknown_edit():
    class Slow(FakeBackend):
        async def execute(self, request):
            await asyncio.sleep(0.1)
    async def scenario():
        executor = Executor(FakeBackend(), Limits(timeout_seconds=0.01))
        executor.attach_live(Slow(), hello(), "secret")
        assert (await executor.execute(json.dumps(wire()))).error.code == ErrorCode.TIMEOUT
        request = wire("undo", expected_revision=1, request_id="edit-1")
        assert (await executor.execute(json.dumps(request))).error.code == ErrorCode.RESULT_UNKNOWN
    run(scenario())


def test_frozen_protocol_examples():
    examples = json.loads((Path(__file__).parents[1] / "docs/development/protocol-v1.examples.json").read_text(encoding="utf-8"))
    parsed_hello = Handshake.model_validate_json(json.dumps(examples["hello"]))
    welcome = Welcome.model_validate_json(json.dumps(examples["welcome"]))
    assert set(welcome.capabilities) == negotiate(parsed_hello, "example-startup-token")
    for request in examples["requests"]:
        assert parse_request(json.dumps(request), Limits()).request_id
    for result in examples["results"]:
        assert Result.model_validate_json(json.dumps(result)).request_id


def test_cache_capacity_and_ttl(monkeypatch):
    import aseprite_mcp.core.execution as execution
    now = [0.0]
    monkeypatch.setattr(execution.time, "monotonic", lambda: now[0])
    async def scenario():
        executor, backend = attached(limits=Limits(dedup_entries=1, dedup_ttl_seconds=2.0))
        first = json.dumps(wire())
        await executor.execute(first)
        await executor.execute(first)
        assert backend.calls == 1
        now[0] = 3.0
        await executor.execute(first)
        assert backend.calls == 2
        await executor.execute(json.dumps(wire(request_id="second")))
        assert len(executor._cache) == 1
        await executor.execute(first)
        assert backend.calls == 4
    run(scenario())
