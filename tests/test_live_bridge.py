"""Real sockets with a simulated editor, plus a real UI extension lifecycle."""
import asyncio
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from websockets.asyncio.client import connect

from aseprite_mcp.backends.live import LiveBridge
from aseprite_mcp.core.config import RuntimeConfig
from aseprite_mcp.core.execution import Executor
from aseprite_mcp.core.protocol import Handshake, Result
from conftest import run


def test_socket_handshake_routing_dedup_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("ASEPRITE_MCP_CONNECTION_FILE", str(tmp_path / "connection.json"))

    async def scenario():
        config = RuntimeConfig()
        executor = Executor(None)
        bridge = LiveBridge(executor, config)
        async with bridge.lifespan():
            for patch, code in [({"token": "wrong"}, "SESSION_MISMATCH"),
                                ({"protocol_version": 2}, "VERSION_MISMATCH"),
                                ({"api_version": 27}, "UNSUPPORTED_CAPABILITY")]:
                async with connect(bridge.url) as ws:
                    hello = Handshake(protocol_version=1, token=config.token, session_id="s",
                                      aseprite_version="1.3.7", api_version=28, capabilities=["list_documents"])
                    await ws.send(json.dumps(hello.model_dump() | patch))
                    assert json.loads(await ws.recv())["error"]["code"] == code
            async with connect(bridge.url) as ws:
                await ws.send(hello.model_dump_json())
                assert json.loads(await ws.recv())["type"] == "welcome"
                async with connect(bridge.url) as second:
                    await second.send(hello.model_dump_json())
                    assert json.loads(await second.recv())["error"]["code"] == "SESSION_MISMATCH"
                assert executor.live is not None
                request = json.dumps({"request_id": "read", "target": {"backend": "live", "session_id": "s"},
                                      "action": {"name": "list_documents"}})
                task = asyncio.create_task(executor.execute(request))
                sent = json.loads(await ws.recv())
                await ws.send(Result(request_id=sent["request_id"], target=sent["target"], ok=True,
                                     data={"documents": []}).model_dump_json())
                assert (await task).ok
                assert (await executor.execute(request)).ok  # no second wire request
                await ws.send('{"unknown":true}')
                assert json.loads(await ws.recv())["error"]["code"] == "INVALID_REQUEST"
            await asyncio.sleep(.05)
            assert executor.live is None
        assert not bridge.connection_file.exists()
        # No residual listening socket; can immediately reuse the same port.
        async with bridge.lifespan():
            assert bridge.url
    run(scenario())


@pytest.mark.real
def test_real_extension_lifecycle(tmp_path, monkeypatch):
    """A real non-batch 1.3.7 process loads package.json and calls init/exit."""
    monkeypatch.setenv("ASEPRITE_MCP_CONNECTION_FILE", str(tmp_path / "connection.json"))
    root = Path(__file__).resolve().parents[1]
    user = tmp_path / "user"
    shutil.copytree(root / "extension", user / "extensions" / "aseprite-mcp-live")
    script = tmp_path / "lifecycle.lua"
    marker = tmp_path / "lifecycle.json"
    script.write_text('''
local instance=assert(_G.__aseprite_mcp_live, "Extension package did not initialize")
local f=assert(io.open(app.params.connection,"rb")); local config=json.decode(f:read("*a")); f:close()
local phase=0; local ticks=0
local function mark(value)
  local f=assert(io.open(app.params.marker,"wb")); f:write(json.encode(value)); f:close()
end
instance:connect(config)
local timer
timer=Timer{interval=0.1,ontick=function()
  ticks=ticks+1
  if phase==0 and instance.ready then
    phase=1; mark{phase="connected",session=instance.session,version=tostring(app.version),api=app.apiVersion}
  elseif phase==1 then
    local f=io.open(app.params.proceed,"rb")
    if f then f:close(); instance:disconnect(); phase=2 end
  elseif phase==2 then
    instance:connect(config); phase=3
  elseif phase==3 and instance.ready then
    phase=4; mark{phase="reconnected",session=instance.session,api=app.apiVersion}
  elseif phase==4 then
    local f=io.open(app.params.finish,"rb")
    if f then f:close(); timer:stop(); app.exit() end
  end
  if ticks>250 then mark{error=instance.status}; timer:stop(); app.exit() end
end}
timer:start()
''', encoding="utf-8")
    # Pre-authorize only these fixture scripts in the isolated test profile.
    # Aseprite hashes the absolute source path for read/write/socket permissions.
    permissions = []
    for source in [script, *list((user / "extensions" / "aseprite-mcp-live").glob("*.lua"))]:
        for filename in {str(source), source.as_posix()}:
            key = hashlib.sha1(filename.encode()).hexdigest()
            permissions.extend([f"{key} = 14", f"{key.upper()} = 14"])
    (user / "aseprite.ini").write_text("[script_access]\n" + "\n".join(permissions), encoding="utf-8")

    async def wait_until(predicate):
        async with asyncio.timeout(20):
            while not predicate():
                await asyncio.sleep(.05)

    async def scenario():
        executor = Executor(None)
        bridge = LiveBridge(executor, RuntimeConfig())
        async with bridge.lifespan():
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            with (tmp_path / "aseprite.log").open("w") as log:
                process = subprocess.Popen([os.environ["ASEPRITE_PATH"], "--script-param",
                    f"connection={bridge.connection_file}", "--script-param", f"marker={marker}",
                    "--script-param", f"proceed={tmp_path / 'proceed'}", "--script-param",
                    f"finish={tmp_path / 'finish'}", "--script", str(script)],
                    env=dict(os.environ, ASEPRITE_USER_FOLDER=str(user)), startupinfo=startup,
                    stdout=log, stderr=log)
                try:
                    await wait_until(lambda: executor.live is not None)
                    first = executor.session_id
                    request = {"request_id": "roundtrip", "target": {"backend": "live", "session_id": first},
                               "action": {"name": "list_documents"}}
                    result = await executor.execute(json.dumps(request))
                    assert result.ok, result
                    (tmp_path / "proceed").touch()
                    await wait_until(lambda: executor.session_id is not None and executor.session_id != first)
                    stale = await executor.execute(json.dumps(request | {"request_id": "stale"}))
                    assert stale.error.code == "SESSION_MISMATCH"
                    (tmp_path / "finish").touch()
                    await wait_until(lambda: process.poll() is not None)
                    await wait_until(lambda: executor.live is None)
                    assert process.returncode == 0
                    assert json.loads(marker.read_text())["api"] == 28
                finally:
                    if process.poll() is None:
                        process.terminate()
                        await asyncio.to_thread(process.wait, 5)
    run(scenario())
