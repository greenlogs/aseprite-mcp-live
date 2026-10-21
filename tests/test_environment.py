"""Real baseline: Unicode paths, tool registration and exported pixels."""
import asyncio
from PIL import Image
from conftest import ok, run
from aseprite_mcp import mcp
from aseprite_mcp.tools import canvas, drawing, export, animation


def test_tools_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {"create_canvas", "draw_pixels", "get_sprite_info", "export_sprite"} <= names
    assert len(names) == 116


def test_unicode_cli_roundtrip(tmp_path):
    directory = tmp_path / "中文 路径"
    directory.mkdir()
    source = (directory / "画布.aseprite").as_posix()
    output = (directory / "预览.png").as_posix()
    ok(run(canvas.create_canvas(8, 8, source)))
    ok(run(drawing.draw_pixels(source, [{"x": 2, "y": 3, "color": "#A020F0"}])))
    info = ok(run(animation.get_sprite_info(source)))
    assert "8" in info
    ok(run(export.export_sprite(source, output)))
    with Image.open(output) as image:
        assert image.size == (8, 8)
        assert image.convert("RGBA").getpixel((2, 3)) == (160, 32, 240, 255)

