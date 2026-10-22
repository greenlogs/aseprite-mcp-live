"""MCP SDK 1.6.0 client -> real stdio server -> real Aseprite UI -> ImageContent."""
import asyncio
import base64
import gc
import io
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import pytest

from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Limits
from conftest import run
from live_support import editor_process, until


@pytest.mark.real
def test_real_mcp_preview_and_phase_integration(tmp_path):
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core")
        started = time.perf_counter()
        timings = {}
        gallery = []
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "aseprite_mcp"], env=env)
        async with stdio_client(parameters) as streams, ClientSession(*streams) as client:
            initialized = await client.initialize()
            timings["mcp_startup_ms"] = round((time.perf_counter() - started) * 1000, 2)
            async with editor_process(tmp_path) as manual:
                async with asyncio.timeout(15):
                    while True:
                        status = await client.call_tool("get_connection_status", {})
                        status = json.loads(status.content[0].text)
                        if status["connected"]:
                            break
                        await asyncio.sleep(.05)
                session = status["session_id"]

                async def call(name, **args):
                    before = time.perf_counter()
                    result = await client.call_tool(name, {"session_id": session, **args})
                    timings.setdefault(name + "_ms", []).append(round((time.perf_counter() - before) * 1000, 2))
                    assert not result.isError, result
                    return json.loads(result.content[0].text)

                async def preview(document, revision, label, **args):
                    started = time.perf_counter()
                    response = await client.call_tool("get_preview", {"session_id": session,
                        "document_id": document, "expected_revision": revision, **args})
                    timings.setdefault("get_preview_ms", []).append(round((time.perf_counter() - started) * 1000, 2))
                    assert not response.isError, response
                    assert [c.type for c in response.content] == ["text", "image"]
                    metadata = json.loads(response.content[0].text)
                    assert "data" not in metadata["data"]["png"]
                    assert metadata["revision"] == revision
                    image = response.content[1]
                    assert image.mimeType == "image/png"
                    raw = base64.b64decode(image.data, validate=True)
                    decoded = Image.open(io.BytesIO(raw)).convert("RGBA")
                    (tmp_path / f"{label}.png").write_bytes(raw)
                    gallery.append((label, image.data))
                    return decoded, metadata

                created = await call("create_sprite", width=8, height=8)
                document = created["data"]["document_id"]
                # Aseprite's pencil tool provides the manual, unsaved starting image.
                await manual('''
test_source=app.activeSprite
app.useTool{tool="pencil",color=Color(250,180,30,255),points={Point(1,1)}}
return true
''')
                info = await call("get_document_info", document_id=document)
                assert info["data"]["modified"] and not info["data"]["saved"]
                before, _ = await preview(document, info["revision"], "before", scale=8)
                assert before.size == (64, 64) and before.getpixel((8, 8)) == (250, 180, 30, 255)
                assert before.getpixel((0, 0))[3] == 0
                operations = [
                    {"op": "create_layer", "ref": "paint", "name": "MCP paint"},
                    {"op": "rectangle", "layer": {"kind": "ref", "value": "paint"},
                     "frame": 1, "x": 2, "y": 2, "width": 4, "height": 4,
                     "filled": True, "rgba": [40, 170, 220, 255]},
                    {"op": "pixel", "layer": {"kind": "ref", "value": "paint"},
                     "frame": 1, "x": 3, "y": 3, "rgba": [230, 70, 120, 255]},
                ]
                edited = await call("apply_operations", document_id=document, expected_revision=info["revision"],
                                    operations=operations, request_id="integrated-batch")
                after, _ = await preview(document, edited["revision"], "after", scale=8)
                assert after.getpixel((16, 16)) == (40, 170, 220, 255)
                assert after.getpixel((24, 24)) == (230, 70, 120, 255)
                # A preview has no content/context/modified/history side effects.
                stable = await call("get_document_info", document_id=document)
                assert stable["revision"] == edited["revision"]
                await preview(document, edited["revision"], "after-repeat", scale=8)
                unchanged = await call("get_document_info", document_id=document)
                assert {k: v for k, v in stable.items() if k != "request_id"} == {
                    k: v for k, v in unchanged.items() if k != "request_id"}
                undone = await call("undo", document_id=document, expected_revision=edited["revision"])
                undo_image, _ = await preview(document, undone["revision"], "undo", scale=8)
                assert undo_image.tobytes() == before.tobytes()
                redone = await call("redo", document_id=document, expected_revision=undone["revision"])
                redo_image, _ = await preview(document, redone["revision"], "redo", scale=8)
                assert redo_image.tobytes() == after.tobytes()
                # Region origin and integer nearest-neighbor blocks must match source pixels.
                cropped, meta = await preview(document, redone["revision"], "region", scale=3,
                                              region={"x": 2, "y": 2, "width": 3, "height": 3})
                assert cropped.size == (9, 9)
                assert meta["data"]["png"]["region"]["x"] == 2
                assert cropped.getpixel((3, 3)) == (230, 70, 120, 255)
                assert all(cropped.getpixel((x, y)) == (230, 70, 120, 255)
                           for y in range(3, 6) for x in range(3, 6))
                # Nonzero Cel, transparency/opacity, multiple layers and frames.
                await manual('''
local s=test_source;s:newEmptyFrame()
local l=s:newLayer();l.name="offset";l.opacity=128
local i=Image(2,2);i:putPixel(0,0,app.pixelColor.rgba(30,60,90,255))
s:newCel(l,2,i,Point(4,3))
test_other=Sprite(3,3);test_other.selection=Selection(Rectangle(1,1,1,1))
return true
''')
                info = await call("get_document_info", document_id=document)
                frame2, _ = await preview(document, info["revision"], "frame2", frame=2, scale=1)
                assert frame2.getpixel((4, 3)) == (30, 60, 90, 128)
                assert frame2.getpixel((0, 0))[3] == 0
                assert await manual('return app.activeSprite==test_other and test_other.selection.bounds.x==1')
                for args, expected in [({"frame": 99}, "INVALID_TARGET"),
                    ({"region": {"x": 7, "y": 7, "width": 2, "height": 2}}, "INVALID_REQUEST"),
                    ({"scale": 64}, None)]:
                    result = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                        "expected_revision": info["revision"], **args})
                    if expected:
                        assert result.isError and expected in result.content[0].text
                    else:  # 8*8*64^2 is the exact default pixel budget.
                        assert not result.isError, result
                outdated = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                                                               "expected_revision": 0})
                assert outdated.isError and "REVISION_CONFLICT" in outdated.content[0].text
                large = await call("create_sprite", width=9, height=9)
                exceeded = await client.call_tool("get_preview", {"session_id": session,
                    "document_id": large["data"]["document_id"], "expected_revision": large["revision"], "scale": 64})
                assert exceeded.isError and "LIMIT_EXCEEDED" in exceeded.content[0].text
                await manual('app.activeSprite=test_other;return true')
                # Encoding failure is caught, with source and context left intact.
                await manual('''
local e=__aseprite_mcp_live.editor;e.original_execute=e.execute
e.execute=function(self,r)
  if r.action.name=="get_preview" then error("injected encoding failure") end
  return self.original_execute(self,r)
end
return true
''')
                failed = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                                                               "expected_revision": info["revision"]})
                assert failed.isError and "EXECUTION_FAILED" in failed.content[0].text
                await manual('local e=__aseprite_mcp_live.editor;e.execute=e.original_execute;return true')
                assert (await call("get_document_info", document_id=document))["revision"] == info["revision"]
                await manual('test_source:close();return true')
                closed = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                                                               "expected_revision": info["revision"]})
                assert closed.isError and "INVALID_TARGET" in closed.content[0].text
                assert not list(tmp_path.glob("*.aseprite"))
        gc.collect()
        await asyncio.sleep(.05)
        # A minimal real MCP client gallery renders exactly the received image blocks.
        html = '<!doctype html><meta charset="utf-8"><title>P1 MCP image verification</title>'
        html += '<style>body{background:#20242c;color:#eee;font:16px sans-serif;display:flex;gap:20px;flex-wrap:wrap}img{width:192px;height:192px;object-fit:contain;image-rendering:pixelated}figure{margin:20px}</style>'
        html += ''.join(f'<figure><img alt="{label}" src="data:image/png;base64,{data}"><figcaption>{label}</figcaption></figure>'
                        for label, data in gallery if label in {"before", "after", "undo", "redo"})
        (tmp_path / "client-gallery.html").write_text(html, encoding="utf-8")
        (tmp_path / "client-evidence.json").write_text(json.dumps({"client": "Python MCP SDK 1.6.0",
            "server": initialized.serverInfo.model_dump(), "aseprite": status, "timings": timings}, indent=2), encoding="utf-8")

    run(scenario())


@pytest.mark.real
@pytest.mark.parametrize("limit", ["max_png_bytes", "max_message_bytes"])
def test_real_preview_limits_without_mutation(tmp_path, monkeypatch, limit):

    async def scenario():
        limits = Limits(**{limit: 500 if limit == "max_png_bytes" else 2100})
        executor = Executor(None, limits)
        bridge = LiveBridge(executor, RuntimeConfig(limits=limits))
        async with bridge.lifespan(), editor_process(tmp_path) as manual:
            await until(lambda: executor.live is not None)
            created = await executor.execute(json.dumps({"request_id": "create", "target": {
                "backend": "live", "session_id": executor.session_id}, "action": {
                "name": "create_sprite", "width": 8, "height": 8}}))
            assert created.ok, created
            request = {"request_id": "limited-preview", "target": {"backend": "live",
                "session_id": executor.session_id, "document_id": created.data["document_id"]},
                "expected_revision": created.revision, "action": {"name": "get_preview", "frame": 1, "scale": 2}}
            result = await executor.execute(json.dumps(request))
            assert result.error.code == "LIMIT_EXCEEDED", result
            assert "reduce region or scale" in result.error.message
            info = await executor.execute(json.dumps(request | {"request_id": "info", "action": {"name": "get_document_info"}}))
            assert info.ok and info.revision == created.revision
            assert not info.data["saved"]

    run(scenario())
