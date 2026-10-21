"""Lua escape hatch (script.py)."""
from conftest import ok, run

from aseprite_mcp.tools import script


def test_run_lua_script_returns_printed_output(sprite):
    out = ok(run(script.run_lua_script(
        'local spr = app.activeSprite print("size=" .. spr.width .. "x" .. spr.height)',
        sprite)))
    assert "size=32x32" in out


def test_run_lua_script_rejects_empty():
    assert run(script.run_lua_script("  ")) == "Script cannot be empty"
