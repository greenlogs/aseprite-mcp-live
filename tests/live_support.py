"""Isolated real UI process fixtures; no test-control commands enter production MCP."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


async def until(predicate, timeout=15):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.04)


@asynccontextmanager
async def editor_process(directory, connection_file, *, automatic=False):
    user = directory / "user"
    extension = user / "extensions" / "aseprite-mcp-live"
    shutil.copytree(ROOT / "extension", extension)
    boot = directory / "boot.lua"
    control = directory / "control.json"
    response = directory / "control-result.json"
    command_file = directory / "control.lua"
    boot_source='''
local bridge=assert(_G.__aseprite_mcp_live,"Extension init missing")
local last=0
_G.test_timer=Timer{interval=0.04,ontick=function()
  local f=io.open(app.params.control,"rb")
  if not f then return end
  local raw=f:read("*a"); f:close()
  local ok,p=pcall(json.decode,raw)
  if not ok or p.sequence==last then return end
  last=p.sequence
  local success,data=pcall(dofile,p.path)
  local result={sequence=last,ok=success}
  if success then result.data=data else result.error=tostring(data) end
  local out=assert(io.open(app.params.response,"wb"));out:write(json.encode(result));out:close()
end}
test_timer:start()
'''
    if not automatic:
        boot_source+='''
local f=assert(io.open(app.params.connection,"rb")); local config=json.decode(f:read("*a")); f:close()
bridge:connect(config)
'''
    boot.write_text(boot_source, encoding="utf-8")
    permissions = []
    for source in [boot, command_file, *extension.glob("*.lua")]:
        for filename in {str(source), source.as_posix()}:
            key = hashlib.sha1(filename.encode()).hexdigest()
            permissions.extend([f"{key} = 14", f"{key.upper()} = 14"])
    (user / "aseprite.ini").write_text("[script_access]\n" + "\n".join(permissions), encoding="utf-8")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    sequence = 0

    async def command(code):
        nonlocal sequence
        sequence += 1
        command_file.write_text(code, encoding="utf-8")
        control.write_text(json.dumps({"sequence": sequence, "path": str(command_file)}), encoding="utf-8")

        def complete():
            try:
                return json.loads(response.read_text(encoding="utf-8")).get("sequence") == sequence
            except (OSError, ValueError):
                return False

        await until(complete)
        result = json.loads(response.read_text(encoding="utf-8"))
        assert result["ok"], result
        return result.get("data")

    with (directory / "aseprite.log").open("w") as log:
        args = [os.environ["ASEPRITE_PATH"]]
        if not automatic:
            args.extend(["--script-param", f"connection={connection_file}"])
        process = subprocess.Popen([*args, "--script-param", f"control={control}",
            "--script-param", f"response={response}", "--script", str(boot)],
            env=dict(os.environ, ASEPRITE_USER_FOLDER=str(user)), startupinfo=startup,
            stdout=log, stderr=log)
        try:
            yield command
        finally:
            if process.poll() is None:
                try:
                    await command('for _,s in ipairs(app.sprites) do s:close() end; test_timer:stop(); app.exit(); return true')
                    await until(lambda: process.poll() is not None, 5)
                except (TimeoutError, AssertionError):
                    process.terminate()
                    await asyncio.to_thread(process.wait, 5)
