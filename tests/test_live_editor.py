"""Real in-memory edits, manual tool strokes, rollback, history and save."""
import asyncio
import json
from uuid import uuid4

import pytest

from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Request
from conftest import run
from live_support import live_port, editor_process, until


@pytest.mark.real
def test_real_documents_transactions_history_save(tmp_path, monkeypatch):

    async def scenario():
        executor = Executor(None)
        bridge = LiveBridge(executor, RuntimeConfig(port=live_port()))
        async with bridge.lifespan(), editor_process(tmp_path) as manual:
            await until(lambda: executor.live is not None)
            # Welcome is processed asynchronously on the editor's UI thread.
            await until(lambda: bridge.hello is not None)

            async def call(name, document=None, revision=None, **args):
                request = {"request_id": str(uuid4()), "target": {"backend": "live", "session_id": executor.session_id},
                           "action": {"name": name, **args}}
                if document is not None:
                    request["target"]["document_id"] = document
                if revision is not None:
                    request["expected_revision"] = revision
                return await executor.execute(json.dumps(request))

            created = await call("create_sprite", width=12, height=10)
            assert created.ok, created
            document = created.data["document_id"]
            assert created.data["color_mode"] == "rgb" and not created.data["saved"]
            layer = created.data["layers"][0]["id"]
            # A real Aseprite pencil stroke simulates a user action, outside MCP.
            await manual('test_first=app.activeSprite;app.useTool{tool="pencil",color=Color(7,8,9,255),points={Point(1,1)}}; return true')
            info = await call("get_document_info", document)
            assert info.revision > created.revision
            revision = info.revision
            stale = await call("apply_operations", document, created.revision,
                               operations=[{"op": "set_opacity", "layer": {"kind": "id", "value": layer}, "opacity": 4}])
            assert stale.error.code == "REVISION_CONFLICT"
            # Switch to another document; all following operations still target the first.
            other = await call("create_sprite", width=3, height=3)
            assert other.ok
            await manual("test_other=app.activeSprite; return true")
            operations = [
                {"op": "create_layer", "ref": "a", "name": "重复"},
                {"op": "create_layer", "ref": "b", "name": "重复"},
                {"op": "rectangle", "layer": {"kind": "ref", "value": "a"}, "frame": 1,
                 "x": 2, "y": 2, "width": 4, "height": 4, "filled": False, "rgba": [200, 30, 40, 255]},
                {"op": "pixel", "layer": {"kind": "ref", "value": "b"}, "frame": 1,
                 "x": 3, "y": 3, "rgba": [50, 60, 70, 128]},
                {"op": "set_opacity", "layer": {"kind": "ref", "value": "b"}, "opacity": 170},
            ]
            edited = await call("apply_operations", document, revision, operations=operations)
            assert edited.ok, edited
            assert edited.revision > revision
            refs = edited.data["layer_refs"]
            assert refs["a"] != refs["b"]
            snapshot = await manual('''
local s=test_first; local a=s.layers[2]:cel(1); local b=s.layers[3]:cel(1)
return {active_other=app.activeSprite==test_other,layers=#s.layers,modified=s.isModified,
  a=a.image:getPixel(2-a.position.x,2-a.position.y),
  b=b.image:getPixel(3-b.position.x,3-b.position.y),opacity=s.layers[3].opacity}
''')
            assert snapshot == {"active_other": True, "layers": 3, "modified": True,
                                "a": int.from_bytes(bytes([200, 30, 40, 255]), "little"), "b": int.from_bytes(bytes([50, 60, 70, 128]), "little"), "opacity": 170}
            undone = await call("undo", document, edited.revision)
            assert undone.ok and undone.data["applied"], undone
            assert await manual('return #test_first.layers') == 1
            redone = await call("redo", document, undone.revision)
            assert redone.ok and redone.data["applied"]
            assert await manual('return #test_first.layers') == 3
            info = await call("get_document_info", document)
            assert [l["name"] for l in info.data["layers"]][1:] == ["重复", "重复"]
            # Registry identity survives repeated enumeration and rename.
            a_id = info.data["layers"][1]["id"]
            await manual('test_first.layers[2].name="改名"; return true')
            info = await call("get_document_info", document)
            assert info.data["layers"][1]["id"] == a_id
            assert info.revision > redone.revision
            # Inject a failure *inside* the real transaction after a successful edit.
            await manual('''
local editor=__aseprite_mcp_live.editor
editor.original_apply=editor.apply_one
local count=0
editor.apply_one=function(self,record,op,refs)
  count=count+1; if count==2 then error("injected transaction failure") end
  return self.original_apply(self,record,op,refs)
end
return true
''')
            failed = await call("apply_operations", document, info.revision, operations=operations[:2])
            assert failed.error.code == "EXECUTION_FAILED"
            assert await manual('local e=__aseprite_mcp_live.editor;e.apply_one=e.original_apply;return #test_first.layers') == 3
            # Offset Cel and empty Cel; preserve off-canvas source pixels.
            await manual('''
local s=test_first; local l=s:newLayer();l.name="offset"
local i=Image(2,2); i:putPixel(0,0,app.pixelColor.rgba(11,22,33,255))
s:newCel(l,1,i,Point(-1,4)); s:newEmptyFrame(); return true
''')
            info = await call("get_document_info", document)
            offset = info.data["layers"][-1]["id"]
            pixels = [{"op": "pixel", "layer": {"kind": "id", "value": offset}, "frame": f,
                       "x": 2, "y": 5, "rgba": [80, 90, 100, 255]} for f in [1, 2]]
            result = await call("apply_operations", document, info.revision, operations=pixels)
            assert result.ok, result
            assert await manual('''
local s=test_first;local l=s.layers[4];local c=l:cel(1)
return {left=c.position.x,top=c.position.y,old=c.image:getPixel(0,0),
 new=c.image:getPixel(2-c.position.x,5-c.position.y),second=l:cel(2)~=nil}
''') == {"left": -1, "top": 4, "old": int.from_bytes(bytes([11, 22, 33, 255]), "little"), "new": int.from_bytes(bytes([80, 90, 100, 255]), "little"), "second": True}
            info = await call("get_document_info", document)
            context_request = Request.model_validate_json(json.dumps({"request_id": "old-context",
                "target": {"backend": "live", "session_id": executor.session_id, "document_id": document},
                "expected_revision": info.revision, "expected_context": info.context_revision,
                "action": {"name": "apply_operations", "operations": [pixels[0]]}}))
            await manual('app.activeSprite=test_first; return true')
            conflict = await executor.execute(context_request.model_dump_json())
            assert conflict.error.code == "CONTEXT_CONFLICT"
            # Locked layers and unsupported color modes reject before mutation.
            await manual('test_first.layers[1].isEditable=false;return true')
            info = await call("get_document_info", document)
            locked = await call("apply_operations", document, info.revision, operations=[{
                **pixels[0], "layer": {"kind": "id", "value": layer}}])
            assert locked.error.code == "UNSUPPORTED_CAPABILITY"
            await manual('test_first.layers[1].isEditable=true;return true')
            for mode in ["GRAY", "INDEXED"]:
                await manual(f'test_unsupported=Sprite(2,2,ColorMode.{mode});return true')
                listing = await call("list_documents")
                unsupported = next(d for d in listing.data["documents"] if d["color_mode"] != "rgb")
                rejected = await call("apply_operations", unsupported["document_id"], unsupported["revision"],
                                      operations=[operations[0]])
                assert rejected.error.code == "UNSUPPORTED_CAPABILITY"
                await manual('test_unsupported:close();return true')
            await manual('app.activeSprite=test_other;return true')
            info = await call("get_document_info", document)
            for invalid, code in [({**pixels[0], "frame": 99}, "INVALID_TARGET"),
                                  ({**pixels[0], "x": 12}, "INVALID_REQUEST"),
                                  ({**pixels[0], "layer": {"kind": "id", "value": "deleted"}}, "INVALID_TARGET")]:
                bad = await call("apply_operations", document, info.revision, operations=[operations[0], invalid])
                assert bad.error.code == code
                assert await manual('return #test_first.layers') == 4
            # Editor-side duplicate receipts also prevent repeated changes.
            request = Request.model_validate_json(json.dumps({"request_id": "editor-dedup",
                "target": {"backend": "live", "session_id": executor.session_id, "document_id": document},
                "expected_revision": info.revision, "action": {"name": "apply_operations", "operations": [operations[0]]}}))
            first = await executor.live.execute(request)
            second = await executor.live.execute(request)
            assert first.ok and first == second
            assert await manual('return #test_first.layers') == 5
            changed = request.model_copy(update={"expected_revision": first.revision})
            assert (await executor.live.execute(changed)).error.code == "REQUEST_CONFLICT"
            # Save is explicit, absolute, native-format and overwrite guarded.
            info = await call("get_document_info", document)
            missing = await call("save_sprite", document, info.revision)
            assert missing.error.code == "INVALID_REQUEST"
            destination = tmp_path / "中文 画布.aseprite"
            saved = await call("save_sprite", document, info.revision, path=str(destination))
            assert saved.ok and destination.is_file(), saved
            info = await call("get_document_info", document)
            assert info.data["saved"] and not info.data["modified"]
            before = destination.read_bytes()
            refused = await call("save_sprite", document, info.revision, path=str(destination))
            assert refused.error.code == "INVALID_REQUEST" and destination.read_bytes() == before
            assert (await call("save_sprite", document, info.revision, path=str(destination), overwrite=True)).ok
            await manual('test_first:close();return true')
            assert (await call("get_document_info", document)).error.code == "INVALID_TARGET"
            assert (await call("get_document_info", other.data["document_id"])).ok

    run(scenario())
