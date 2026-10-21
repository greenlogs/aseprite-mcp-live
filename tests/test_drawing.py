"""Drawing tools added in this round (drawing.py)."""
from conftest import ok, run

from aseprite_mcp.tools import drawing, pixel_read


def test_draw_ellipse_at(sprite):
    ok(run(drawing.draw_ellipse_at(sprite, "body", 1, 16, 16, 6, 4, "#306230", True)))
    px = ok(run(pixel_read.get_pixel_color(sprite, 16, 16, "body", 1)))
    assert "#306230" in px


def test_draw_ellipse_rejects_bad_radius(sprite):
    result = run(drawing.draw_ellipse_at(sprite, "body", 1, 16, 16, 0, 4, "#306230"))
    assert "must be > 0" in result
