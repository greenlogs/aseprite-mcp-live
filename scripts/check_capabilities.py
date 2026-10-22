"""Check the reviewed upstream inventory against source and MCP registration."""
import ast
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check():
    from aseprite_mcp.server import create_server

    matrix = json.loads((ROOT / "docs/development/tool-compatibility.json").read_text(encoding="utf-8"))
    records = matrix["tools"]
    source_names = set()
    for path in (ROOT / "aseprite_mcp/tools").glob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
                for d in node.decorator_list
            ):
                source_names.add(node.name)
    assert len(records) == len({row["name"] for row in records})
    assert {row["name"] for row in records} == source_names
    for row in records:
        assert (ROOT / row["path"]).is_file()
        assert all(key in row for key in ("cli", "live", "minimum_api", "active_state", "save_effect",
                                         "undo", "tests", "simulation", "real_live", "license", "migration"))
        assert all((ROOT / path).is_file() for path in row["tests"])
    old = os.environ.pop("ASEPRITE_MCP_ENABLE_RAW_LUA", None)
    try:
        names = {tool.name for tool in asyncio.run(create_server("cli").list_tools())}
        assert names - {"cli_execute"} == source_names - {"run_lua_script"}
    finally:
        if old is not None:
            os.environ["ASEPRITE_MCP_ENABLE_RAW_LUA"] = old
    print(f"Checked {len(records)} baseline tools, CLI registration and compatibility fields")


if __name__ == "__main__":
    check()
