"""Layer management tools (layers.py)."""
from conftest import ok, run

from aseprite_mcp.tools import canvas, drawing, layers


def test_rename_layer(sprite):
    ok(run(canvas.add_layer(sprite, "detail")))
    ok(run(drawing.draw_ellipse_at(sprite, "detail", 1, 16, 16, 6, 4, "#306230", True)))
    ok(run(layers.rename_layer(sprite, "detail", "shade")))


def test_duplicate_layer(sprite):
    result = ok(run(layers.duplicate_layer(sprite, "shade")))
    assert "shade copy" in result


def test_set_layer_blend_mode(sprite):
    ok(run(layers.set_layer_blend_mode(sprite, "shade copy", "multiply")))


def test_set_layer_blend_mode_rejects_unknown(sprite):
    result = run(layers.set_layer_blend_mode(sprite, "shade copy", "nonsense"))
    assert result.startswith("Unknown blend mode")


def test_reorder_layer(sprite):
    ok(run(layers.reorder_layer(sprite, "shade copy", 1)))


def test_merge_layer_down(sprite):
    ok(run(layers.merge_layer_down(sprite, "body")))


def test_delete_layer(sprite):
    ok(run(layers.delete_layer(sprite, "shade")))


def test_flatten_sprite(sprite):
    ok(run(layers.flatten_sprite(sprite)))
