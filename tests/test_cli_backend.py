"""Real CLI vertical path and simulated process/receipt failures."""
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from aseprite_mcp.backends.cli import CliBackend
from aseprite_mcp.core.commands import AsepriteCommand
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import BackendError, ErrorCode, Limits, Request
from aseprite_mcp.tools import canvas, export
from conftest import ok, run


def request(source, action, request_id="cli-1"):
    return json.dumps({"request_id": request_id, "target": {"backend": "cli", "path": str(source)},
                       "action": action})


def executor():
    return Executor(CliBackend(Limits()))


def test_real_cli_read_edit_export(tmp_path):
    directory = tmp_path / "契约 路径"
    directory.mkdir()
    source = directory / "画布.aseprite"
    ok(run(canvas.create_canvas(8, 8, source.as_posix())))
    bridge = executor()
    info = run(bridge.execute(request(source, {"name": "get_document_info"})))
    assert info.ok, info
    assert (info.data["width"], info.data["height"], info.data["api_version"]) == (8, 8, 28)
    layer = info.data["layers"][0]["id"]
    action = {"name": "apply_operations", "operations": [
        {"op": "create_layer", "ref": "paint", "name": '中文 " 图层'},
        {"op": "rectangle", "layer": {"kind": "ref", "value": "paint"},
         "x": 1, "y": 1, "width": 4, "height": 4, "rgba": [20, 40, 60, 255], "filled": False},
        {"op": "pixel", "layer": {"kind": "ref", "value": "paint"},
         "x": 2, "y": 2, "rgba": [90, 80, 70, 255]},
        {"op": "set_opacity", "layer": {"kind": "id", "value": layer}, "opacity": 123},
    ]}
    result = run(bridge.execute(request(source, action, "edit-1")))
    assert result.ok, result
    assert result.data["layer_refs"]["paint"]
    output = directory / "验证.png"
    ok(run(export.export_sprite(source.as_posix(), output.as_posix())))
    with Image.open(output) as image:
        image = image.convert("RGBA")
        assert image.getpixel((1, 1)) == (20, 40, 60, 255)
        assert image.getpixel((2, 2)) == (90, 80, 70, 255)
        assert image.getpixel((3, 3))[3] == 0
    assert not list(directory.glob("aseprite-mcp-*"))


@pytest.mark.parametrize("operations,code", [
    ([{"op": "pixel", "layer": {"value": "missing"}, "x": 0, "y": 0, "rgba": [0, 0, 0, 255]}], ErrorCode.INVALID_TARGET),
    ([{"op": "pixel", "layer": {"value": "1"}, "x": 8, "y": 0, "rgba": [0, 0, 0, 255]}], ErrorCode.INVALID_REQUEST),
    ([{"op": "pixel", "layer": {"value": "1"}, "frame": 2, "x": 0, "y": 0, "rgba": [0, 0, 0, 255]}], ErrorCode.INVALID_TARGET),
])
def test_real_cli_invalid_batch_leaves_source_unchanged(tmp_path, operations, code):
    source = tmp_path / "unchanged.aseprite"
    ok(run(canvas.create_canvas(8, 8, source.as_posix())))
    before = source.read_bytes()
    # An earlier valid create must not leak from an invalid atomic batch.
    operations.insert(0, {"op": "create_layer", "ref": "new", "name": "not committed"})
    result = run(executor().execute(request(source, {"name": "apply_operations", "operations": operations})))
    assert result.error.code == code, result
    assert source.read_bytes() == before


@pytest.mark.parametrize("mode", ["exit-zero", "script-error", "wrong-nonce", "no-artifact", "bad-artifact", "malformed"])
def test_process_receipt_and_fresh_artifact_required(tmp_path, monkeypatch, mode):
    source = tmp_path / "existing.aseprite"
    source.write_bytes(b"an old existing output is not evidence")
    original = source.read_bytes()

    def fake_process(args, timeout):
        payload = Path(next(arg.removeprefix("payload=") for arg in args if arg.startswith("payload=")))
        receipt = Path(next(arg.removeprefix("result=") for arg in args if arg.startswith("result=")))
        fields = json.loads(payload.read_text(encoding="utf-8"))
        if mode == "exit-zero":
            return True, ""
        response = {"nonce": fields["nonce"], "ok": True, "data": {"width": 1, "height": 1, "layers": [], "frames": 1}}
        if mode == "script-error":
            response.update(ok=False, error={"code": "EXECUTION_FAILED", "message": "Lua failed"})
        if mode == "wrong-nonce":
            response["nonce"] = "stale"
        if mode == "bad-artifact":
            Path(fields["artifact"]).write_bytes(b"x" * 128)
        receipt.write_text("{" if mode == "malformed" else json.dumps(response), encoding="utf-8")
        return True, ""

    monkeypatch.setattr(AsepriteCommand, "run_command", fake_process)
    action = {"name": "apply_operations", "operations": [{"op": "create_layer", "name": "x", "ref": "x"}]}
    result = run(executor().execute(request(source, action)))
    assert result.error.code == ErrorCode.EXECUTION_FAILED
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("aseprite-mcp-*"))


@pytest.mark.parametrize("fault,code", [(FileNotFoundError("missing executable"), ErrorCode.EXECUTION_FAILED),
    (subprocess.TimeoutExpired("aseprite", 0.1), ErrorCode.TIMEOUT)])
def test_command_os_error_and_timeout(tmp_path, monkeypatch, fault, code):
    source = tmp_path / "existing.aseprite"
    source.write_bytes(b"old")
    def fail(*args, **kwargs):
        raise fault
    monkeypatch.setattr(subprocess, "run", fail)
    result = run(executor().execute(request(source, {"name": "get_document_info"})))
    assert result.error.code == code


def test_cli_unsupported_and_invalid_target(tmp_path):
    source = tmp_path / "missing.aseprite"
    result = run(executor().execute(request(source, {"name": "get_document_info"})))
    assert result.error.code == ErrorCode.INVALID_TARGET
    result = run(executor().execute(request(source, {"name": "list_documents"})))
    assert result.error.code == ErrorCode.UNSUPPORTED_CAPABILITY
    live = Request.model_validate_json(json.dumps({"request_id": "wrong-backend",
        "target": {"backend": "live", "session_id": "s", "document_id": "d"},
        "action": {"name": "get_document_info"}}))
    with pytest.raises(BackendError) as error:
        run(CliBackend(Limits()).execute(live))
    assert error.value.code == ErrorCode.INVALID_TARGET


def test_concurrent_disk_change_is_not_overwritten(tmp_path, monkeypatch):
    source = tmp_path / "existing.aseprite"
    source.write_bytes(b"original")

    def fake_process(args, timeout):
        payload = Path(next(arg.removeprefix("payload=") for arg in args if arg.startswith("payload=")))
        receipt = Path(next(arg.removeprefix("result=") for arg in args if arg.startswith("result=")))
        fields = json.loads(payload.read_text(encoding="utf-8"))
        Path(fields["artifact"]).write_bytes(b"\x00" * 4 + b"\xe0\xa5" + b"\x00" * 122)
        receipt.write_text(json.dumps({"nonce": fields["nonce"], "ok": True,
            "data": {"width": 1, "height": 1, "layers": [], "frames": 1}}), encoding="utf-8")
        source.write_bytes(b"external change")
        return True, ""

    monkeypatch.setattr(AsepriteCommand, "run_command", fake_process)
    action = {"name": "apply_operations", "operations": [{"op": "create_layer", "name": "x", "ref": "x"}]}
    result = run(executor().execute(request(source, action)))
    assert result.error.code == ErrorCode.CONTEXT_CONFLICT
    assert source.read_bytes() == b"external change"
