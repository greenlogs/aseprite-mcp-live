"""Frame, cel, and tag tools added to animation.py."""
import json

from conftest import ok, run

from aseprite_mcp.tools import animation


def test_add_frames(sprite):
    ok(run(animation.add_frames(sprite, 3, 100)))
    info = json.loads(run(animation.get_sprite_info(sprite)))
    assert info["frames"] == 4


def test_set_cel_opacity(sprite):
    ok(run(animation.set_cel_opacity(sprite, "body", 1, 200)))


def test_set_and_delete_tag(sprite):
    ok(run(animation.set_tag(sprite, "walk", 1, 3, "forward")))
    ok(run(animation.delete_tag(sprite, "walk")))
    info = json.loads(run(animation.get_sprite_info(sprite)))
    assert info["tags"] == []


def test_delete_tag_missing(sprite):
    result = run(animation.delete_tag(sprite, "nope"))
    assert "Tag not found" in result


def test_delete_frame(sprite):
    ok(run(animation.delete_frame(sprite, 4)))
    info = json.loads(run(animation.get_sprite_info(sprite)))
    assert info["frames"] == 3
