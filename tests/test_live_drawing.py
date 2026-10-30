"""New drawing contracts and real API28 MCP transactions; simulations are separate."""
import asyncio
import base64
import gc
from datetime import timedelta
import io
import json
import os
import sys
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import pytest

from aseprite_mcp.backends.cli import CliBackend
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import BackendError, Limits, parse_request
from conftest import run
from live_support import editor_process, track_refresh


LAYER = {"kind": "id", "value": "l1"}


def wire(op):
    return {"request_id": str(uuid4()), "target": {"backend": "live", "session_id": "s", "document_id": "d"},
            "expected_revision": 0, "action": {"name": "apply_operations", "operations": [op]}}


@pytest.mark.parametrize("op", [
    {"op": "pixels", "layer": LAYER, "points": []},
    {"op": "pixels", "layer": LAYER, "points": [{"x": True, "y": 0, "rgba": [1, 2, 3, 4]}]},
    {"op": "write_region", "layer": LAYER, "x": 0, "y": 0, "width": 2, "height": 1, "pixels": [[0, 0, 0, 0]]},
    {"op": "write_region", "layer": LAYER, "x": 0, "y": 0, "width": 1, "height": 1, "encoding": "rle",
     "runs": [{"count": 0, "rgba": [0, 0, 0, 0]}]},
    {"op": "write_region", "layer": LAYER, "x": 0, "y": 0, "width": 1, "height": 1, "encoding": "rle",
     "runs": [{"count": 2, "rgba": [0, 0, 0, 0]}]},
    {"op": "write_region", "layer": LAYER, "x": 0, "y": 0, "width": 1, "height": 1,
     "pixels": [[0, 0, 0, 0]], "runs": [{"count": 1, "rgba": [0, 0, 0, 0]}]},
    {"op": "line", "layer": LAYER, "x1": 0, "y1": 0, "x2": 1, "y2": 1, "rgba": [1, 2, 3, 4], "thickness": 0},
    {"op": "ellipse", "layer": LAYER, "x": 0, "y": 0, "width": 2, "height": 0, "rgba": [1, 2, 3, 4]},
    {"op": "clear_region", "layer": LAYER, "x": 0, "y": 0, "width": 1, "height": 1, "rgba": [0, 0, 0, 0]},
])
def test_invalid_drawing_contract(op):
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(wire(op)), Limits())
    assert error.value.code == "INVALID_REQUEST"


def test_drawing_budgets_and_cli_refusal():
    op = {"op": "write_region", "layer": LAYER, "x": 0, "y": 0, "width": 100, "height": 100,
          "encoding": "rle", "runs": [{"count": 10000, "rgba": [1, 2, 3, 4]}]}
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(wire(op)), Limits(max_pixels=9999))
    assert error.value.code == "LIMIT_EXCEEDED"
    request = wire(op)
    request["target"] = {"backend": "cli", "path": "unused.aseprite"}
    del request["expected_revision"]
    result = run(Executor(CliBackend(Limits())).execute(json.dumps(request)))
    assert result.error.code == "UNSUPPORTED_CAPABILITY"
    request = wire({"op": "line", "layer": LAYER, "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "rgba": [0, 0, 0, 0], "thickness": 3})
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(request), Limits())
    assert error.value.code == "INVALID_REQUEST"


def test_read_pixels_contract_and_budgets():
    request = wire({"op": "pixel", "layer": LAYER, "x": 0, "y": 0, "rgba": [0, 0, 0, 0]})
    request["action"] = {"name": "read_pixels", "layer": "l1", "region": {"x": 0, "y": 0, "width": 3, "height": 3}}
    assert parse_request(json.dumps(request), Limits()).action.encoding == "rgba"
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(request), Limits(max_pixels=8))
    assert error.value.code == "LIMIT_EXCEEDED"
    del request["expected_revision"]
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(request), Limits())
    assert error.value.code == "INVALID_REQUEST"


@pytest.mark.real
def test_real_drawing_readback_history_buffers_and_rollback(tmp_path):
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="core", ASEPRITE_MCP_CAPABILITY_SETS="")
        params = StdioServerParameters(command=sys.executable, args=["-B", "-m", "aseprite_mcp"], env=env)
        async with stdio_client(params) as streams, ClientSession(*streams, read_timeout_seconds=timedelta(seconds=20)) as client:
            await client.initialize()
            async with editor_process(tmp_path) as manual:
                async with asyncio.timeout(15):
                    while True:
                        status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
                        if status["connected"]:
                            break
                        await asyncio.sleep(.04)
                assert "read_pixels" in status["capabilities"]
                session = status["session_id"]
                await track_refresh(manual)

                async def call(name, error=None, **args):
                    response = await client.call_tool(name, {"session_id": session, **args})
                    value = json.loads(response.content[0].text)
                    if error:
                        assert response.isError and value["error"]["code"] == error, value
                    else:
                        assert not response.isError, value
                    return value

                created = await call("create_sprite", width=16, height=16)
                document = created["data"]["document_id"]
                layer = created["data"]["layers"][0]["id"]
                target = {"kind": "id", "value": layer}
                await manual('test_draw=app.activeSprite;return true')
                await call("create_sprite", width=2, height=2)
                await manual('test_draw_other=app.activeSprite;return true')

                async def info():
                    return await call("get_document_info", document_id=document)

                async def edit(ops, error=None, **kwargs):
                    current = await info()
                    return await call("apply_operations", document_id=document, expected_revision=current["revision"],
                                      operations=ops, error=error, **kwargs)

                async def read(x=0, y=0, width=16, height=16, encoding="rgba", layer_id=None, frame=1, error=None):
                    current = await info()
                    return await call("read_pixels", document_id=document, expected_revision=current["revision"],
                                      layer=layer_id or layer, frame=frame, encoding=encoding,
                                      region={"x": x, "y": y, "width": width, "height": height}, error=error)

                # Each new primitive: exact expected pixels, single undo/redo and inactive-site preservation.
                red = [200, 10, 20, 255]
                region = {"x": 2, "y": 2, "width": 5, "height": 5}
                ellipse = {(x, y) for y, xs in enumerate([(1, 2, 3), (0, 1, 2, 3, 4), (0, 1, 2, 3, 4),
                                                         (0, 1, 2, 3, 4), (1, 2, 3)]) for x in xs}
                outline = {(x, y) for x, y in ellipse if any(p not in ellipse for p in
                           [(x-1, y), (x+1, y), (x, y-1), (x, y+1)])}
                cases = [
                    ({"op": "pixels", "points": [{"x": 2, "y": 2, "rgba": red}, {"x": 4, "y": 3, "rgba": red}]}, {(2, 2), (4, 3)}),
                    ({"op": "line", "x1": 2, "y1": 2, "x2": 6, "y2": 6, "rgba": red}, {(i, i) for i in range(2, 7)}),
                    ({"op": "line", "x1": 6, "y1": 6, "x2": 2, "y2": 2, "rgba": red}, {(i, i) for i in range(2, 7)}),
                    ({"op": "line", "x1": 2, "y1": 2, "x2": 2, "y2": 2, "thickness": 2, "rgba": red}, {(2, 2), (3, 2), (2, 3), (3, 3)}),
                    ({"op": "ellipse", **region, "rgba": red}, {(x+2, y+2) for x, y in ellipse}),
                    ({"op": "ellipse", **region, "filled": False, "rgba": red}, {(x+2, y+2) for x, y in outline}),
                    ({"op": "ellipse", "x": 2, "y": 2, "width": 1, "height": 3, "filled": False, "rgba": red}, {(2, 2), (2, 3), (2, 4)}),
                    ({"op": "write_region", "x": 2, "y": 2, "width": 2, "height": 2, "pixels": [red]*4}, {(2, 2), (3, 2), (2, 3), (3, 3)}),
                    ({"op": "write_region", "x": 2, "y": 2, "width": 2, "height": 2, "encoding": "rle",
                      "runs": [{"count": 4, "rgba": red}]}, {(2, 2), (3, 2), (2, 3), (3, 3)}),
                ]
                for op, coordinates in cases:
                    await edit([{**op, "layer": target}])
                    pixels = (await read())["data"]["pixels"]
                    assert pixels == [red if (x, y) in coordinates else [0, 0, 0, 0] for y in range(16) for x in range(16)], op
                    current = await info()
                    undone = await call("undo", document_id=document, expected_revision=current["revision"])
                    assert (await read())["data"]["pixels"] == [[0, 0, 0, 0]]*256
                    redone = await call("redo", document_id=document, expected_revision=undone["revision"])
                    assert (await read())["data"]["pixels"] == pixels
                    await call("undo", document_id=document, expected_revision=redone["revision"])
                    assert await manual('return app.activeSprite==test_draw_other')

                # Order, alpha-zero RGB, replacement and integer straight-alpha source-over.
                await edit([
                    {"op": "write_region", "layer": target, "x": 0, "y": 0, "width": 3, "height": 1,
                     "pixels": [[0, 0, 255, 128], [7, 8, 9, 0], [1, 2, 3, 255]]},
                    {"op": "write_region", "layer": target, "x": 0, "y": 0, "width": 2, "height": 1,
                     "mode": "source_over", "pixels": [[255, 0, 0, 128], [200, 20, 20, 0]]},
                    {"op": "clear_region", "layer": target, "x": 2, "y": 0, "width": 1, "height": 1},
                ])
                assert (await read(width=3, height=1))["data"]["pixels"] == [[170, 0, 85, 192], [7, 8, 9, 0], [0, 0, 0, 0]]
                before = await info()
                refresh = await manual('return test_refresh_count')
                await manual('test_draw.layers[1].isVisible=false;test_draw.layers[1].opacity=3;test_draw.layers[1].isEditable=false;return true')
                raw = await read(width=3, height=1, encoding="rle")
                assert raw["data"]["runs"][0] == {"count": 1, "rgba": [170, 0, 85, 192]}
                after_read = await info()
                assert (await read(width=3, height=1))["revision"] == after_read["revision"]
                assert await manual('return test_refresh_count') == refresh
                await call("read_pixels", document_id=document, layer=layer, expected_revision=before["revision"],
                           region={"x": 0, "y": 0, "width": 1, "height": 1}, error="REVISION_CONFLICT")
                await read(frame=99, error="INVALID_TARGET")
                await read(x=15, width=2, error="INVALID_REQUEST")
                await read(layer_id="deleted", error="INVALID_TARGET")
                await manual('test_draw.layers[1].isVisible=true;test_draw.layers[1].opacity=255;test_draw.layers[1].isEditable=true;return true')

                # New-layer refs and empty target frames; off-canvas old pixels survive final bounds expansion.
                await manual('local l=test_draw:newLayer();l.name="offset";local i=Image(2,2);i:putPixel(0,0,app.pixelColor.rgba(11,22,33,0));test_draw:newCel(l,1,i,Point(-1,4));test_draw:newEmptyFrame();return true')
                offset = (await info())["data"]["layers"][-1]["id"]
                result = await edit([
                    {"op": "create_layer", "name": "new", "ref": "new"},
                    {"op": "pixels", "layer": {"kind": "ref", "value": "new"}, "frame": 2, "points": [{"x": 3, "y": 3, "rgba": red}]},
                    {"op": "pixel", "layer": {"kind": "id", "value": offset}, "x": 3, "y": 5, "rgba": red},
                ])
                assert (await read(frame=2, layer_id=result["data"]["layer_refs"]["new"], x=3, y=3, width=1, height=1))["data"]["pixels"] == [red]
                assert await manual('local c=test_draw.layers[2]:cel(1);return c.position.x==-1 and c.position.y==4 and c.image:getPixel(0,0)==app.pixelColor.rgba(11,22,33,0)')
                assert (await read(layer_id=offset, frame=2, width=1, height=1))["data"]["pixels"] == [[0, 0, 0, 0]]

                # Probe real module calls: 256 operations against a full 128x128 Cel allocate/commit one buffer.
                large = await call("create_sprite", width=128, height=128)
                large_id = large["data"]["document_id"]
                large_layer = large["data"]["layers"][0]["id"]
                await manual('''
test_large=app.activeSprite
test_large:newCel(test_large.layers[1],1,Image(128,128),Point(0,0))
local e=__aseprite_mcp_live.editor
for i=1,20 do local name,value=debug.getupvalue(e.apply_one,i);if name=="drawing" then test_raster=value;break end end
assert(test_raster)
test_buffers=0;test_commits=0
local original=test_raster.prepare
test_raster.prepare=function(entry,...) if not entry.image then test_buffers=test_buffers+1 end;return original(entry,...) end
test_raster.original_commit=test_raster.commit
test_raster.commit=function(batch,tick) test_commits=test_commits+#batch.entries;return test_raster.original_commit(batch,tick) end
app.activeSprite=test_draw_other
return true
''')
                large_info = await call("get_document_info", document_id=large_id)
                operations = [{"op": "pixel", "layer": {"kind": "id", "value": large_layer}, "x": i%128, "y": i//128, "rgba": red} for i in range(256)]
                args = dict(document_id=large_id, expected_revision=large_info["revision"], operations=operations, request_id="buffer-once")
                first = await call("apply_operations", **args)
                assert await call("apply_operations", **args) == first
                assert await manual('return test_buffers==1 and test_commits==1 and app.activeSprite==test_draw_other')
                current = await call("get_document_info", document_id=large_id)
                decoded = await call("read_pixels", document_id=large_id, expected_revision=current["revision"], layer=large_layer,
                                     region={"x": 0, "y": 0, "width": 128, "height": 2}, encoding="rle")
                assert decoded["data"]["runs"] == [{"count": 256, "rgba": red}]
                raw_response = await client.call_tool("read_pixels", {"session_id": session, "document_id": large_id,
                    "expected_revision": current["revision"], "layer": large_layer,
                    "region": {"x": 0, "y": 0, "width": 128, "height": 128}})
                assert not raw_response.isError and len(raw_response.content[0].text) < 128*128*20+2048
                raw_pixels = json.loads(raw_response.content[0].text)["data"]["pixels"]
                assert raw_pixels[:256] == [red]*256 and raw_pixels[256:] == [[0, 0, 0, 0]]*(128*128-256)
                undone = await call("undo", document_id=large_id, expected_revision=current["revision"])
                assert await manual('return test_large.layers[1]:cel(1).image:getPixel(0,0)==0')
                await call("redo", document_id=large_id, expected_revision=undone["revision"])

                # Force an error AFTER actual Cel assignment: transaction rolls back all new pixels and metadata.
                await manual('test_raster.commit=function(batch,tick) test_raster.original_commit(batch,tick);error("after actual write") end;return true')
                original = (await read())["data"]["pixels"]
                await edit([{"op": "set_opacity", "layer": target, "opacity": 22},
                            {"op": "line", "layer": target, "x1": 0, "y1": 1, "x2": 10, "y2": 1, "rgba": red}], error="EXECUTION_FAILED")
                assert (await read())["data"]["pixels"] == original
                assert await manual('return test_draw.layers[1].opacity==255 and app.activeSprite==test_draw_other')
                await manual('test_raster.commit=test_raster.original_commit;__aseprite_mcp_live.editor.limits.max_batch_seconds=0.000000001;return true')
                await edit([{"op": "pixel", "layer": target, "x": 10, "y": 10, "rgba": red}], error="LIMIT_EXCEEDED")
                await read(width=1, height=1, error="LIMIT_EXCEEDED")
                await manual('__aseprite_mcp_live.editor.limits.max_batch_seconds=0.25;return true')
                assert (await read())["data"]["pixels"] == original
                await manual('__aseprite_mcp_live.editor.limits.max_message_bytes=2100;return true')
                await read(error="LIMIT_EXCEEDED")
                await manual('__aseprite_mcp_live.editor.limits.max_message_bytes=8388608;return true')
                await manual('__aseprite_mcp_live.editor.limits.max_pixels=1;return true')
                await edit([{"op": "pixel", "layer": target, "x": 0, "y": 0, "rgba": red}], error="LIMIT_EXCEEDED")
                await manual('__aseprite_mcp_live.editor.limits.max_pixels=262144;return true')
                for mode in ["GRAY", "INDEXED"]:
                    await manual(f'test_bad_draw=Sprite(2,2,ColorMode.{mode});return true')
                    listing = await call("list_documents")
                    bad = next(d for d in listing["data"]["documents"] if d["color_mode"] != "rgb")
                    await call("read_pixels", document_id=bad["document_id"], layer=bad["layers"][0]["id"],
                               expected_revision=bad["revision"], region={"x": 0, "y": 0, "width": 1, "height": 1},
                               error="UNSUPPORTED_CAPABILITY")
                    await manual('test_bad_draw:close();app.activeSprite=test_draw_other;return true')

                # Native image preview reflects the same bytes read back from the current memory document.
                current = await info()
                response = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                    "expected_revision": current["revision"], "frame": 1, "scale": 1})
                assert not response.isError
                png = base64.b64decode(response.content[1].data)
                (tmp_path / "drawing-preview.png").write_bytes(png)
                preview = Image.open(io.BytesIO(png)).convert("RGBA")
                assert list(preview.getpixel((0, 0))) == [170, 0, 85, 192]
                assert await manual('return app.activeSprite==test_draw_other')

                # Two linked source frames get independent buffers, copied before any final assignment.
                from test_live_animation import linked_sprite
                linked_path = tmp_path / "linked-drawing.aseprite"
                linked_sprite(linked_path)
                await manual(f'test_link_draw=app.open({json.dumps(linked_path.as_posix())});return true')
                range_before = await manual('''
local c=test_link_draw.layers[1]:cel(1)
c.opacity=123;c.zIndex=2;c.data="keep-user-data";c.color=Color(7,8,9,255)
c.properties.test_value={x=42};c.properties("another/extension").secret=73
app.range.layers={c.layer};app.range.frames={1,2};app.range.colors={1,3}
test_range_type=app.range.type
return {frames=#app.range.frames,colors=#app.range.colors}
''')
                listing = await call("list_documents")
                linked = next(d for d in listing["data"]["documents"] if d["active"])
                linked_target = {"kind": "id", "value": linked["layers"][0]["id"]}
                painted = await call("apply_operations", document_id=linked["document_id"], expected_revision=linked["revision"],
                                     operations=[{"op": "write_region", "layer": linked_target, "frame": f,
                                         "x": 0, "y": 0, "width": 1, "height": 1, "pixels": [color]}
                                         for f, color in [(1, red), (2, [0, 255, 0, 255])]])
                assert await manual('return test_link_draw.layers[1]:cel(1).image:getPixel(0,0)==app.pixelColor.rgba(200,10,20,255) and test_link_draw.layers[1]:cel(2).image:getPixel(0,0)==app.pixelColor.rgba(0,255,0,255)')
                linked_metadata = await manual('''
local c=test_link_draw.layers[1]:cel(1)
return {opacity=c.opacity,z=c.zIndex,data=c.data,red=c.color.red,
  property=c.properties.test_value.x,extension=c.properties("another/extension").secret,
  range_type=app.range.type==test_range_type,frames=#app.range.frames,colors=#app.range.colors}
''')
                assert linked_metadata == dict(opacity=123, z=2, data="keep-user-data", red=7,
                                               property=42, extension=73, range_type=True, **range_before)
                await call("undo", document_id=linked["document_id"], expected_revision=painted["revision"])
                assert await manual('return test_link_draw.layers[1]:cel(1).image.id==test_link_draw.layers[1]:cel(2).image.id')
                (tmp_path / "acceptance.json").write_text(json.dumps({"version": "0.6.0", "api": 28,
                    "operations_per_cel": 256, "buffers": 1, "commits": 1,
                    "primitive_cases": len(cases), "result": "passed"}, indent=2), encoding="utf-8")
        gc.collect()
        await asyncio.sleep(.05)

    run(scenario())
