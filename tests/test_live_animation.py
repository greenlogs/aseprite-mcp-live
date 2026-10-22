"""Optional animation contracts plus real MCP/UI/CLI timeline acceptance."""
import asyncio
import base64
import gc
from datetime import timedelta
import io
import json
import os
import struct
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import pytest

from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Handshake, LIVE_CAPABILITIES, Limits, Result, parse_request, BackendError
from aseprite_mcp.server import create_server
from aseprite_mcp.tools import animation
from conftest import run
from live_support import editor_process


def linked_sprite(path):
    """Minimal native format fixture: one raw Cel and one link to frame zero."""
    def chunk(kind, body):
        return struct.pack("<IH", len(body) + 6, kind) + body

    def frame(chunks):
        body = b"".join(chunks)
        return struct.pack("<IHHH2xI", len(body) + 16, 0xF1FA, len(chunks), 100, 0) + body

    layer = chunk(0x2004, struct.pack("<6HB3xH", 3, 0, 0, 0, 0, 0, 255, 4) + b"body")
    cel = lambda kind: struct.pack("<HhhBHh5x", 0, 0, 0, 255, kind, 0)
    first = frame([layer, chunk(0x2005, cel(0) + struct.pack("<HH", 2, 2) + bytes([90, 180, 40, 255]) * 4)])
    second = frame([chunk(0x2005, cel(1) + struct.pack("<H", 0))])
    header = bytearray(128)
    struct.pack_into("<I5HIH", header, 0, 128 + len(first) + len(second), 0xA5E0, 2, 2, 2, 32, 1, 100)
    header[34:36] = bytes([1, 1])
    path.write_bytes(header + first + second)


def wire(operations, **changes):
    return dict(request_id="animation", target={"backend": "live", "session_id": "s", "document_id": "d"},
                action={"name": "apply_animation", "operations": operations}, expected_revision=0, **changes)


@pytest.mark.parametrize("op", [
    {"op": "add_frames", "count": 0}, {"op": "add_frames", "count": 256},
    {"op": "add_frames", "count": True},
    {"op": "set_frame_duration", "from_frame": 1, "to_frame": 2, "duration_ms": 65536},
    {"op": "set_frame_duration", "from_frame": 1, "to_frame": 2, "duration_ms": 0},
    {"op": "set_tag", "tag": "", "from_frame": 1, "to_frame": 1},
    {"op": "set_tag", "tag": "a", "from_frame": 1, "to_frame": 1, "direction": "bad"},
    {"op": "delete_frame", "frame": 0}, {"op": "delete_tag", "tag": "a", "extra": 1},
])
def test_animation_invalid_schema(op):
    with pytest.raises(BackendError) as error:
        parse_request(json.dumps(wire([op])), Limits())
    assert error.value.code == "INVALID_REQUEST"


def test_animation_opt_in_negotiation_limits_and_unknown_receipt(monkeypatch):
    monkeypatch.delenv("ASEPRITE_MCP_CAPABILITY_SETS", raising=False)
    assert "apply_animation" not in {t.name for t in run(create_server().list_tools())}
    monkeypatch.setenv("ASEPRITE_MCP_CAPABILITY_SETS", "animation")
    for profile, count in [("core", 10), ("cli", 116), ("all", 126)]:
        names = {t.name for t in run(create_server(profile).list_tools())}
        assert len(names) == count
        assert ("apply_animation" in names) == (profile != "cli")
    monkeypatch.setenv("ASEPRITE_MCP_CAPABILITY_SETS", "typo")
    with pytest.raises(ValueError):
        RuntimeConfig.from_env()
    raw = json.dumps(wire([{"op": "add_frames", "count": 1}]))
    with pytest.raises(BackendError):
        parse_request(json.dumps(wire([{"op": "delete_tag", "tag": "x"}] * 2)), Limits(max_operations=1))
    missing_revision = json.loads(raw)
    del missing_revision["expected_revision"]
    with pytest.raises(BackendError):
        parse_request(json.dumps(missing_revision), Limits())

    class Slow:
        capabilities = LIVE_CAPABILITIES

        async def execute(self, request):
            await asyncio.sleep(.1)
            return Result(request_id=request.request_id, target=request.target, ok=True)

    async def scenario():
        hello = Handshake(protocol_version=1, session_id="s", aseprite_version="1.3.7", api_version=28,
                          capabilities=list(LIVE_CAPABILITIES))
        disabled = Executor(Slow())
        disabled.attach_live(Slow(), hello)
        assert (await disabled.execute(raw)).error.code == "UNSUPPORTED_CAPABILITY"
        enabled = Executor(Slow(), Limits(timeout_seconds=.01), capability_sets=frozenset({"animation"}))
        enabled.attach_live(Slow(), hello.model_copy(update={"capabilities": ["get_document_info"]}))
        assert (await enabled.execute(raw)).error.code == "UNSUPPORTED_CAPABILITY"
        enabled.detach_live()
        enabled.attach_live(Slow(), hello)
        assert (await enabled.execute(raw)).error.code == "RESULT_UNKNOWN"
        cli = json.loads(raw)
        cli["target"] = {"backend": "cli", "path": "unused.aseprite"}
        del cli["expected_revision"]
        from aseprite_mcp.backends.cli import CliBackend
        assert (await Executor(CliBackend(Limits())).execute(json.dumps(cli))).error.code == "UNSUPPORTED_CAPABILITY"
    run(scenario())


@pytest.mark.real
def test_real_animation_mcp_history_preview_cli_and_failures(tmp_path):
    async def scenario():
        env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE="all", ASEPRITE_MCP_CAPABILITY_SETS="animation")
        parameters = StdioServerParameters(command=sys.executable, args=["-B", "-m", "aseprite_mcp"], env=env)
        gallery = []
        async with stdio_client(parameters) as streams, ClientSession(*streams, read_timeout_seconds=timedelta(seconds=20)) as client:
            await client.initialize()
            assert len((await client.list_tools()).tools) == 126
            async with editor_process(tmp_path) as manual:
                async with asyncio.timeout(15):
                    while True:
                        status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
                        if status["connected"]:
                            break
                        await asyncio.sleep(.04)
                assert "apply_animation" in status["capabilities"]
                session = status["session_id"]

                async def call(name, error=None, **args):
                    response = await client.call_tool(name, {"session_id": session, **args})
                    value = json.loads(response.content[0].text)
                    if error:
                        assert response.isError and value["error"]["code"] == error, value
                    else:
                        assert not response.isError, value
                    return value

                created = await call("create_sprite", width=8, height=8)
                document = created["data"]["document_id"]

                async def info():
                    return await call("get_document_info", document_id=document)

                async def edit(operations, error=None, **args):
                    current = await info()
                    return await call("apply_animation", document_id=document,
                                      expected_revision=current["revision"], operations=operations, error=error, **args)

                async def preview(frame, label):
                    current = await info()
                    response = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                        "expected_revision": current["revision"], "frame": frame, "scale": 8})
                    assert not response.isError and [c.type for c in response.content] == ["text", "image"]
                    raw = base64.b64decode(response.content[1].data)
                    (tmp_path / f"{label}.png").write_bytes(raw)
                    gallery.append((label, response.content[1].data))
                    return Image.open(io.BytesIO(raw)).convert("RGBA").tobytes()

                # Offset Cel, group, missing Cel and real pencil edit; target becomes inactive.
                await manual('''
test_anim=app.activeSprite
app.useTool{tool="pencil",color=Color(240,50,70,255),points={Point(2,2)}}
local g=test_anim:newGroup();g.name="group"
local l=test_anim:newLayer();l.parent=g;l.name="offset"
local i=Image(2,2);i:putPixel(0,0,app.pixelColor.rgba(20,80,240,255))
test_anim:newCel(l,1,i,Point(4,3))
test_anim:newLayer().name="empty"
return true
''')
                other = await call("create_sprite", width=3, height=3)
                await manual('test_anim_other=app.activeSprite;return true')
                before = await preview(1, "before")
                batch = [{"op": "add_frames", "count": 2, "duration_ms": 120},
                         {"op": "set_frame_duration", "from_frame": 2, "to_frame": 3, "duration_ms": 220},
                         {"op": "set_tag", "tag": "走路", "from_frame": 1, "to_frame": 3, "direction": "pingpong"}]
                current = await info()
                added = await call("apply_animation", document_id=document, expected_revision=current["revision"],
                                   operations=batch, request_id="animation-dedup")
                assert added["data"]["frames"] == 3
                assert added["data"]["frame_durations_ms"] == [100, 220, 220]
                assert added["data"]["tags"] == [{"name": "走路", "from_frame": 1, "to_frame": 3, "direction": "pingpong"}]
                assert await call("apply_animation", document_id=document, expected_revision=current["revision"],
                                  operations=batch, request_id="animation-dedup") == added
                assert await manual('return app.activeSprite==test_anim_other')
                for frame in [1, 2, 3]:
                    assert await preview(frame, f"frame-{frame}") == before
                undone = await call("undo", document_id=document, expected_revision=added["revision"])
                assert (await info())["data"]["frames"] == 1
                assert await preview(1, "undo") == before
                redone = await call("redo", document_id=document, expected_revision=undone["revision"])
                assert redone["data"]["applied"] and (await info())["data"]["frames"] == 3
                assert await preview(3, "redo") == before
                await call("apply_animation", document_id=document, expected_revision=current["revision"],
                           operations=batch, error="REVISION_CONFLICT")
                # Core drawing after animation must only change the requested frame.
                current = await info()
                layer = current["data"]["layers"][0]["id"]
                await call("apply_operations", document_id=document, expected_revision=current["revision"], operations=[{
                    "op": "pixel", "layer": {"kind": "id", "value": layer}, "frame": 3,
                    "x": 1, "y": 1, "rgba": [10, 200, 30, 255]}])
                changed = await preview(3, "changed")
                assert changed != before and await preview(1, "original") == before
                # Append must clone the final frame, independently of the active frame/document.
                await edit([{"op": "add_frames", "count": 1}])
                assert await preview(4, "appended") == changed
                assert await manual('''
local s=test_anim;local offset=s.layers[2].layers[1]
return offset:cel(4).position==Point(4,3) and s.layers[3]:cel(4)==nil
''')
                for direction in ["forward", "reverse", "pingpong", "pingpong_reverse"]:
                    result = await edit([{"op": "set_tag", "tag": "走路", "from_frame": 2, "to_frame": 4, "direction": direction}])
                    assert result["data"]["tags"][0]["direction"] == direction
                # Update/delete labels and timing each have native history.
                for operation in [
                    {"op": "set_frame_duration", "from_frame": 1, "to_frame": 4, "duration_ms": 65535},
                    {"op": "delete_tag", "tag": "走路"}, {"op": "delete_frame", "frame": 4},
                ]:
                    previous = (await info())["data"]
                    result = await edit([operation])
                    undone = await call("undo", document_id=document, expected_revision=result["revision"])
                    restored = (await info())["data"]
                    for key in ["frames", "frame_durations_ms", "tags"]:
                        assert restored[key] == previous[key]
                    await call("redo", document_id=document, expected_revision=undone["revision"])
                # Full validation before mutation, including sequential frame limits.
                for invalid, code in [
                    ({"op": "delete_frame", "frame": 99}, "INVALID_TARGET"),
                    ({"op": "set_frame_duration", "from_frame": 3, "to_frame": 2, "duration_ms": 100}, "INVALID_TARGET"),
                    ({"op": "set_tag", "tag": "bad", "from_frame": 1, "to_frame": 99}, "INVALID_TARGET"),
                    ({"op": "delete_tag", "tag": "missing"}, "INVALID_TARGET"),
                    ({"op": "add_frames", "count": 255}, "LIMIT_EXCEEDED"),
                ]:
                    previous = (await info())["data"]["frames"]
                    await edit([{"op": "add_frames", "count": 1}, invalid], error=code)
                    assert (await info())["data"]["frames"] == previous
                # Real mid-transaction exception and CPU budget exhaustion roll back all writes.
                await manual('''
local m=__aseprite_mcp_live.editor.animation;m.original=m.apply_one
local count=0;m.apply_one=function(...) count=count+1;if count==2 then error("injected animation failure") end;return m.original(...) end
return true
''')
                await edit([{"op": "add_frames", "count": 1}, {"op": "add_frames", "count": 1}], error="EXECUTION_FAILED")
                assert (await info())["data"]["frames"] == 3
                await manual('local e=__aseprite_mcp_live.editor;e.animation.apply_one=e.animation.original;e.limits.max_batch_seconds=0.000000001;return true')
                await edit([{"op": "add_frames", "count": 1}], error="LIMIT_EXCEEDED")
                assert (await info())["data"]["frames"] == 3
                await manual('local e=__aseprite_mcp_live.editor;e.limits.max_batch_seconds=0.25;e.limits.max_pixels=1;return true')
                await edit([{"op": "add_frames", "count": 1}], error="LIMIT_EXCEEDED")
                await manual('local e=__aseprite_mcp_live.editor;e.limits.max_pixels=262144;test_anim.layers[1].isEditable=false;return true')
                await edit([{"op": "add_frames", "count": 1}], error="UNSUPPORTED_CAPABILITY")
                await manual('test_anim.layers[1].isEditable=true;return true')
                current = await info()
                await manual('app.activeSprite=test_anim_other;app.activeLayer=test_anim_other.layers[1];return true')
                await call("apply_animation", document_id=document, expected_revision=current["revision"],
                           expected_context=current["context_revision"], operations=[{"op": "add_frames", "count": 1}],
                           error="CONTEXT_CONFLICT")
                # Duplicate tag names are never resolved by an arbitrary first match.
                await manual('local a=test_anim:newTag(1,1);a.name="dup";local b=test_anim:newTag(1,1);b.name="dup";return true')
                await edit([{"op": "delete_tag", "tag": "dup"}], error="INVALID_TARGET")
                await manual('for i=#test_anim.tags,1,-1 do test_anim:deleteTag(test_anim.tags[i]) end;return true')
                # Deleting the active last frame must restore a surviving context, not a dead Frame handle.
                await manual('app.activeSprite=test_anim;app.activeFrame=test_anim.frames[3];return true')
                await edit([{"op": "delete_frame", "frame": 3}])
                assert await manual('return app.activeFrame.frameNumber') == 2
                await edit([{"op": "delete_frame", "frame": 2}])
                await edit([{"op": "delete_frame", "frame": 1}], error="INVALID_REQUEST")
                # Metadata changes outside MCP must invalidate a previously read revision.
                current = await info()
                await manual('test_anim.frames[1].duration=0.345;return true')
                await call("apply_animation", document_id=document, expected_revision=current["revision"],
                           operations=[{"op": "add_frames", "count": 1}], error="REVISION_CONFLICT")
                # Explicit save and old CLI read/write retain their disk semantics.
                await edit(batch)
                destination = tmp_path / "动画.aseprite"
                current = await info()
                assert not current["data"]["saved"]
                await call("save_sprite", document_id=document, expected_revision=current["revision"], path=str(destination))
                disk = json.loads(await animation.get_sprite_info(str(destination)))
                assert disk["frames"] == 3 and disk["tags"][0]["name"] == "走路"
                assert disk["durations_ms"] == [345, 220, 220]
                cli_response = await client.call_tool("set_frame_duration_all", {"filename": str(destination), "duration_ms": 150})
                assert not cli_response.isError
                disk = json.loads(await animation.get_sprite_info(str(destination)))
                assert disk["durations_ms"] == [150, 150, 150]
                assert (await info())["data"]["frame_durations_ms"] == [345, 220, 220]
                # Unsupported modes and Tilemap are rejected before editing.
                for mode in ["GRAY", "INDEXED"]:
                    await manual(f'test_bad=Sprite(2,2,ColorMode.{mode});return true')
                    listing = await call("list_documents")
                    bad = next(d for d in listing["data"]["documents"] if d["color_mode"] != "rgb")
                    await call("apply_animation", document_id=bad["document_id"], expected_revision=bad["revision"],
                               operations=[{"op": "add_frames", "count": 1}], error="UNSUPPORTED_CAPABILITY")
                    await manual('test_bad:close();return true')
                await manual('app.activeSprite=test_anim;app.command.NewLayer{tilemap=true};return true')
                await edit([{"op": "add_frames", "count": 1}], error="UNSUPPORTED_CAPABILITY")
                await manual('test_anim:deleteLayer(app.activeLayer);return true')
                current = await info()
                await manual('test_anim:close();return true')
                await call("apply_animation", document_id=document, expected_revision=current["revision"],
                           operations=[{"op": "add_frames", "count": 1}], error="INVALID_TARGET")
                assert (await call("get_document_info", document_id=other["data"]["document_id"]))["ok"]
                # A real native-format linked-Cel fixture avoids UI focus assumptions
                # in LinkCels (which requires the timeline to have keyboard focus).
                linked_path = tmp_path / "linked.aseprite"
                linked_sprite(linked_path)
                assert await manual(f'''
test_linked=app.open({json.dumps(linked_path.as_posix())})
return test_linked.layers[1]:cel(1).image.id==test_linked.layers[1]:cel(2).image.id
''')
                listing = await call("list_documents")
                document = next(d["document_id"] for d in listing["data"]["documents"] if d["active"])
                linked_before = await preview(1, "linked-before")
                await edit([{"op": "add_frames", "count": 1}])
                assert await preview(3, "linked-appended") == linked_before
                assert await manual('return test_linked.layers[1]:cel(1).image.id==test_linked.layers[1]:cel(2).image.id')
                current = await info()
                painted = await call("apply_operations", document_id=document, expected_revision=current["revision"], operations=[{
                    "op": "pixel", "layer": {"kind": "id", "value": current["data"]["layers"][0]["id"]},
                    "frame": 3, "x": 0, "y": 0, "rgba": [10, 20, 30, 255]}])
                assert await preview(1, "linked-original") == linked_before
                undone = await call("undo", document_id=document, expected_revision=painted["revision"])
                assert await preview(3, "linked-undo") == linked_before
                await call("redo", document_id=document, expected_revision=undone["revision"])
                (tmp_path / "gallery.html").write_text('<meta charset="utf-8">' + ''.join(
                    f'<p>{label}</p><img src="data:image/png;base64,{data}">' for label, data in gallery), encoding="utf-8")
                (tmp_path / "acceptance.json").write_text(json.dumps({"status": status, "images": len(gallery),
                    "cli_durations_ms": disk["durations_ms"], "result": "passed"}, indent=2), encoding="utf-8")
        gc.collect()
        await asyncio.sleep(.05)
    run(scenario())
