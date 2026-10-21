"""Windows acceptance harness: only installed service, packaged extension and MCP SDK."""
import argparse
import asyncio
import base64
import gc
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image


async def until(predicate, timeout=20):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.04)


@asynccontextmanager
async def installed_editor(directory, extension_archive, aseprite, runtime_root):
    user = directory / "profile"
    extension = user / "extensions/aseprite-mcp-live"
    extension.mkdir(parents=True)
    with zipfile.ZipFile(extension_archive) as archive:
        assert set(archive.namelist()) == {"package.json", "main.lua", "bridge.lua", "editor.lua", "preview.lua", "LICENSE", "NOTICE.md"}
        archive.extractall(extension)
    boot, command_file = directory / "boot.lua", directory / "manual.lua"
    control, response = directory / "control.json", directory / "response.json"
    boot.write_text('''
local b=assert(__aseprite_mcp_live,"Installed extension did not initialize")
-- Product init starts automatic discovery. No test calls connect() or reads credentials.
local last=0
test_timer=Timer{interval=0.04,ontick=function()
  local f=io.open(app.params.control,"rb");if not f then return end
  local ok,p=pcall(json.decode,f:read("*a"));f:close()
  if not ok or p.sequence==last then return end
  last=p.sequence;local success,data=pcall(dofile,p.path)
  local result={sequence=last,ok=success};if success then result.data=data else result.error=tostring(data) end
  local out=assert(io.open(app.params.response,"wb"));out:write(json.encode(result));out:close()
end};test_timer:start()
''', encoding="utf-8")
    permissions = []
    for script in [boot, command_file, *extension.glob("*.lua")]:
        for filename in {str(script), script.as_posix()}:
            digest = hashlib.sha1(filename.encode()).hexdigest()
            permissions.extend([f"{digest} = 14", f"{digest.upper()} = 14"])
    (user / "aseprite.ini").write_text("[script_access]\n" + "\n".join(permissions), encoding="utf-8")
    sequence = 0

    async def manual(source):
        nonlocal sequence
        sequence += 1
        command_file.write_text(source, encoding="utf-8")
        control.write_text(json.dumps({"sequence": sequence, "path": str(command_file)}), encoding="utf-8")
        def complete():
            try:
                return json.loads(response.read_text(encoding="utf-8"))["sequence"] == sequence
            except (OSError, ValueError, KeyError):
                return False
        await until(complete)
        result = json.loads(response.read_text(encoding="utf-8"))
        assert result["ok"], result
        return result.get("data")

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (directory / "aseprite.log").open("w") as log:
        process = subprocess.Popen([str(aseprite), "--script-param", f"control={control}",
            "--script-param", f"response={response}",
            "--script", str(boot)], env=dict(os.environ, ASEPRITE_USER_FOLDER=str(user), ASEPRITE_MCP_RUNTIME_DIR=str(runtime_root),
                ASEPRITE_MCP_CONNECTION_FILE="", ASEPRITE_MCP_HOST="127.0.0.1", ASEPRITE_MCP_PORT="8765"),
            cwd=directory, startupinfo=startup, stdout=log, stderr=log)
        try:
            yield manual
        finally:
            if process.poll() is None:
                try:
                    await manual('for _,s in ipairs(app.sprites) do s:close() end;test_timer:stop();app.exit();return true')
                    await until(lambda: process.poll() is not None, 5)
                except (TimeoutError, AssertionError):
                    process.terminate()
                    await asyncio.to_thread(process.wait, 5)


async def verify(python, extension, aseprite, directory):
    assert os.name == "nt", "This real GUI harness is validated on Windows only"
    directory.mkdir(parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    env.update(ASEPRITE_PATH=str(aseprite), ASEPRITE_MCP_TOOL_PROFILE="all",
               ASEPRITE_MCP_ENABLE_RAW_LUA="0", ASEPRITE_MCP_RUNTIME_DIR=str(directory / "runtime"),
               ASEPRITE_MCP_HOST="127.0.0.1", ASEPRITE_MCP_PORT="8765")
    env.pop("ASEPRITE_MCP_CONNECTION_FILE", None)
    connection = directory / "runtime/connection-127.0.0.1-8765.json"
    probe = subprocess.run([str(python), "-I", "-c", "import aseprite_mcp,json,sys;from importlib.metadata import version;print(json.dumps({'package':aseprite_mcp.__file__,'python':sys.version,'mcp':version('mcp'),'service':version('aseprite-mcp')}))"],
        env=env, cwd=directory, check=True, capture_output=True, text=True)
    versions = json.loads(probe.stdout)
    assert "site-packages" in versions["package"], versions
    evidence = {"versions": versions, "checks": [], "timings_ms": {}}
    gallery = []
    parameters = StdioServerParameters(command=str(python), args=["-I", "-m", "aseprite_mcp"], env=env, cwd=str(directory))
    with (directory / "server-stderr.log").open("w") as errors:
        started = time.perf_counter()
        try:
            async with stdio_client(parameters, errlog=errors) as streams, ClientSession(*streams, read_timeout_seconds=timedelta(seconds=30)) as client:
                await client.initialize()
                evidence["timings_ms"]["startup"] = (time.perf_counter() - started) * 1000
                tools = await client.list_tools()
                assert len(tools.tools) == 125 and "run_lua_script" not in {tool.name for tool in tools.tools}
                async with installed_editor(directory, extension, aseprite, directory / "runtime") as manual:
                    async def connected(exclude=None):
                        async with asyncio.timeout(20):
                            while True:
                                status = json.loads((await client.call_tool("get_connection_status", {})).content[0].text)
                                if status["connected"] and status["session_id"] != exclude:
                                    return status
                                await asyncio.sleep(.05)
                    status = await connected()
                    evidence["editor"] = {key: status[key] for key in ("aseprite_version", "api_version", "service_version", "extension_version")}
                    assert status["extension_version"] == versions["service"]
                    assert status["automatic_discovery"]
                    session = status["session_id"]

                    async def call(name, **args):
                        start = time.perf_counter()
                        result = await client.call_tool(name, {"session_id": session, **args})
                        evidence["timings_ms"].setdefault(name, []).append((time.perf_counter() - start) * 1000)
                        assert not result.isError, result
                        return json.loads(result.content[0].text)

                    async def preview(document, revision, label):
                        response = await client.call_tool("get_preview", {"session_id": session, "document_id": document,
                            "expected_revision": revision, "scale": 8})
                        assert not response.isError and [part.type for part in response.content] == ["text", "image"], response
                        raw = base64.b64decode(response.content[1].data, validate=True)
                        image = Image.open(io.BytesIO(raw)).convert("RGBA")
                        assert image.size == (64, 64)
                        (directory / f"{label}.png").write_bytes(raw)
                        gallery.append((label, response.content[1].data))
                        return image

                    created = await call("create_sprite", width=8, height=8)
                    document = created["data"]["document_id"]
                    await manual('test_source=app.activeSprite;app.useTool{tool="pencil",color=Color(250,180,30,255),points={Point(1,1)}};return true')
                    info = await call("get_document_info", document_id=document)
                    assert info["data"]["modified"] and not info["data"]["saved"]
                    before = await preview(document, info["revision"], "before")
                    assert before.getpixel((8, 8)) == (250, 180, 30, 255)
                    args = dict(document_id=document, expected_revision=info["revision"], request_id="installed-once",
                        operations=[{"op": "create_layer", "ref": "p", "name": "Installed paint"},
                            {"op": "rectangle", "layer": {"kind": "ref", "value": "p"}, "x": 2, "y": 2,
                             "width": 4, "height": 4, "rgba": [40, 170, 220, 255]}])
                    edited = await call("apply_operations", **args)
                    assert await call("apply_operations", **args) == edited
                    after = await preview(document, edited["revision"], "after")
                    assert after.getpixel((16, 16)) == (40, 170, 220, 255)
                    undone = await call("undo", document_id=document, expected_revision=edited["revision"])
                    assert (await preview(document, undone["revision"], "undo")).tobytes() == before.tobytes()
                    redone = await call("redo", document_id=document, expected_revision=undone["revision"])
                    assert (await preview(document, redone["revision"], "redo")).tobytes() == after.tobytes()
                    target = directory / "中文 保存.aseprite"
                    saved = await call("save_sprite", document_id=document, expected_revision=redone["revision"], path=str(target))
                    assert target.is_file()
                    refusal = await client.call_tool("save_sprite", {"session_id": session, "document_id": document,
                        "expected_revision": saved["revision"], "path": str(target)})
                    assert refusal.isError and json.loads(refusal.content[0].text)["error"]["code"] == "INVALID_REQUEST"
                    request = {"request_id": "installed-cli-read", "target": {"backend": "cli", "path": str(target)},
                        "action": {"name": "get_document_info"}}
                    disk = await client.call_tool("cli_execute", {"request": request})
                    assert not disk.isError
                    disk_info = json.loads(disk.content[0].text)
                    assert disk_info["data"]["width"] == 8 and len(disk_info["data"]["file_revision"]) == 64
                    legacy = await client.call_tool("get_sprite_info", {"filename": str(target)})
                    assert not legacy.isError
                    # A CLI mutation uses an independent copy; never modifies the live-open source.
                    copy = directory / "CLI 独立副本.aseprite"
                    copy.write_bytes(target.read_bytes())
                    request.update(request_id="installed-cli-edit", target={"backend": "cli", "path": str(copy)},
                        expected_file_revision=disk_info["data"]["file_revision"],
                        action={"name": "apply_operations", "operations": [{"op": "create_layer", "ref": "c", "name": "CLI"}]})
                    disk_edit = await client.call_tool("cli_execute", {"request": request})
                    assert not disk_edit.isError, disk_edit
                    old = session
                    await manual('local b=__aseprite_mcp_live;b:disconnect();b.plugin.preferences.auto_connect=true;b:start_auto();return true')
                    status = await connected(old)
                    replay = await client.call_tool("cli_execute", {"request": request})
                    assert not replay.isError and replay.content == disk_edit.content, replay
                    stale = await client.call_tool("get_document_info", {"session_id": old, "document_id": document})
                    assert stale.isError and json.loads(stale.content[0].text)["error"]["code"] == "SESSION_MISMATCH"
                    session = status["session_id"]
                    docs = await call("list_documents")
                    assert len(docs["data"]["documents"]) == 1 and docs["data"]["documents"][0]["saved"]
                    evidence["checks"] = ["installed-site-packages", "125-tools-no-raw-lua", "packaged-extension-init", "automatic-discovery-no-manual-JSON", "unsaved-manual-edit",
                        "atomic-batch-and-dedup", "MCP-image-content", "undo-redo-pixel-equality", "explicit-Chinese-save",
                        "overwrite-refusal", "installed-CLI-read-edit", "legacy-CLI-read", "reconnect-stale-session",
                        "CLI-receipt-survives-editor-reconnect"]
            # Verify the exact console entry shown in the public client config.
            console = python.with_name("aseprite-mcp.exe")
            cli_parameters = StdioServerParameters(command=str(console), args=[],
                env=dict(env, ASEPRITE_MCP_TOOL_PROFILE="cli"), cwd=str(directory))
            async with stdio_client(cli_parameters, errlog=errors) as streams, ClientSession(*streams, read_timeout_seconds=timedelta(seconds=30)) as client:
                await client.initialize()
                assert len((await client.list_tools()).tools) == 116
                read = await client.call_tool("cli_execute", {"request": {"request_id": "console-entry-read",
                    "target": {"backend": "cli", "path": str(target)}, "action": {"name": "get_document_info"}}})
                assert not read.isError, read
                evidence["checks"].append("installed-console-entry")
        finally:
            # SDK 1.6.0 force-terminates its own child on Windows. Only this
            # harness's private discovery file is removed after the child exits.
            connection = directory / "runtime/connection-127.0.0.1-8765.json"
            if connection.exists():
                connection.unlink()
    gc.collect()
    await asyncio.sleep(.1)  # Flush SDK 1.6.0's Windows proactor close callbacks.
    html = '''<!doctype html><meta charset="utf-8"><title>Installed MCP image verification</title>
<style>body{font:18px sans-serif;background:#eceff3;padding:24px}main{display:flex;gap:24px}img{width:192px;height:192px;image-rendering:pixelated;background:white}figure{margin:0}figcaption{padding:12px 0}</style>
<h1>Installed MCP: before / after / undo / redo</h1><main>'''
    html += "".join(f'<figure><img alt="{label}" src="data:image/png;base64,{data}"><figcaption>{label}</figcaption></figure>' for label, data in gallery)
    html += '''</main><script>onload=()=>{document.body.dataset.imagesReady=String([...document.images].every(i=>i.complete&&i.naturalWidth===64&&i.naturalHeight===64))}</script>'''
    (directory / "client-gallery.html").write_text(html, encoding="utf-8")
    (directory / "acceptance.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--aseprite", type=Path, default=Path(os.environ.get("ASEPRITE_PATH", "aseprite")))
    parser.add_argument("--work-dir", type=Path, required=True, help="A new private test directory")
    args = parser.parse_args()
    asyncio.run(verify(args.python.resolve(), args.extension.resolve(), args.aseprite.resolve(), args.work_dir.resolve()))
