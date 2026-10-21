"""Visual feedback tools (analysis.py)."""
import json
import os

from conftest import ok, run

from aseprite_mcp.tools import analysis, animation, drawing


def test_render_onion_skin(sprite, base_dir):
    ok(run(animation.add_frames(sprite, 2, 100)))
    out = f"{base_dir}/onion.png"
    ok(run(analysis.render_onion_skin(sprite, 2, out, 1, 1, 4, 100)))
    assert os.path.exists(out)


def test_compare_identical_frames(sprite):
    # add_frames duplicates content, so frames 1 and 2 are identical;
    # this used to crash on math.huge in the bbox formatting
    diff = json.loads(ok(run(analysis.compare_frames(sprite, 1, 2))))
    assert diff["total_pixels"] == 1024
    assert diff["changed_pixels"] == 0
    assert "changed_bounds" not in diff


def test_compare_differing_frames(sprite):
    ok(run(drawing.draw_rectangle_at(sprite, "body", 3, 0, 0, 4, 4, "#FFFFFF", True)))
    diff = json.loads(ok(run(analysis.compare_frames(sprite, 1, 3))))
    assert diff["changed_pixels"] == 16
    assert diff["changed_bounds"] == {"x": 0, "y": 0, "width": 4, "height": 4}


def test_get_color_stats(sprite):
    stats = json.loads(ok(run(analysis.get_color_stats(sprite, 1))))
    assert stats["unique_colors"] >= 1
    assert stats["top_colors"][0]["count"] > 0
