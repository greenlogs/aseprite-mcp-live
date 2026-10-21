"""Pixel-art effect tools (fx.py)."""
from conftest import ok, run

from aseprite_mcp.tools import drawing, fx, pixel_read


def test_outline_cel(sprite):
    ok(run(fx.outline_cel(sprite, "body", 1, "#140C1C", False)))


def test_replace_color_changes_pixels(sprite):
    ok(run(drawing.draw_rectangle_at(sprite, "body", 1, 10, 10, 4, 4, "#D04648", True)))
    result = ok(run(fx.replace_color(sprite, "body", 1, "#D04648", "#597DCE", 0)))
    assert "Replaced" in result
    px = ok(run(pixel_read.get_pixel_color(sprite, 11, 11, "body", 1)))
    assert "#597dce" in px


def test_adjust_hsl(sprite):
    ok(run(fx.adjust_hsl(sprite, "body", 1, 30, 10, -5)))


def test_apply_dither_gradient(sprite):
    ok(run(fx.apply_dither_gradient(
        sprite, "body", 1, 0, 24, 32, 8, "#30346D", "#597DCE")))


def test_apply_dither_pattern(sprite):
    ok(run(fx.apply_dither_pattern(
        sprite, "body", 1, 0, 0, 8, 8, "#854C30", "#D2AA99", 0.5)))
