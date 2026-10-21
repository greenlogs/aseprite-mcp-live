"""Export and import tools (export.py)."""
import os
import struct

from conftest import ok, run

from aseprite_mcp.tools import animation, export


def png_size(path):
    with open(path, "rb") as f:
        data = f.read(24)
    return struct.unpack(">II", data[16:24])


def test_export_frame_scaled(sprite, base_dir):
    out = f"{base_dir}/frame1.png"
    ok(run(export.export_frame(sprite, 1, out, 8)))
    assert png_size(out) == (256, 256)


def test_export_spritesheet_with_data(sprite, base_dir):
    ok(run(animation.add_frames(sprite, 3, 100)))
    out = f"{base_dir}/sheet.png"
    data = f"{base_dir}/sheet.json"
    ok(run(export.export_spritesheet(sprite, out, "horizontal", data, 2, 1)))
    assert os.path.exists(out) and os.path.exists(data)


def test_export_spritesheet_tag_filter(sprite, base_dir):
    ok(run(animation.set_tag(sprite, "clip", 1, 2, "forward")))
    out = f"{base_dir}/sheet_tag.png"
    ok(run(export.export_spritesheet(sprite, out, "horizontal", "", 1, 0, "clip")))
    w, h = png_size(out)
    assert (w, h) == (64, 32), "tag filter must export only the 2 tagged frames"


def test_export_layers(sprite, base_dir):
    result = ok(run(export.export_layers(sprite, f"{base_dir}/layers")))
    assert ".png" in result


def test_export_tag_gif(sprite, base_dir):
    out = f"{base_dir}/clip.gif"
    ok(run(export.export_tag(sprite, "clip", out, 4)))
    assert os.path.exists(out)


def test_import_image_as_layer(sprite, base_dir):
    ok(run(export.import_image_as_layer(sprite, f"{base_dir}/frame1.png", "ref", 1, 0, 0)))
