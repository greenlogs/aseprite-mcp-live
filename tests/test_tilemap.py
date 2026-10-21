"""Tilemap tools (tilemap.py)."""
import json

from conftest import ok, run

from aseprite_mcp.tools import tilemap


def test_create_tilemap_layer(sprite):
    ok(run(tilemap.create_tilemap_layer(sprite, "terrain", 8, 8)))


def test_draw_on_tiles(sprite):
    ok(run(tilemap.draw_on_tile(sprite, "terrain", 1, [
        {"x": x, "y": y, "color": "#3E8948"} for x in range(8) for y in range(8)])))
    ok(run(tilemap.draw_on_tile(sprite, "terrain", 2, [
        {"x": x, "y": y, "color": "#743F39"} for x in range(8) for y in range(4)])))


def test_get_tilemap_info(sprite):
    info = json.loads(ok(run(tilemap.get_tilemap_info(sprite, "terrain"))))
    assert info == {
        "tile_width": 8, "tile_height": 8, "tile_count": 2,
        "map_cols": 4, "map_rows": 4,
    }


def test_set_and_get_tiles(sprite):
    ok(run(tilemap.set_tiles(sprite, "terrain", 1, [
        {"col": 0, "row": 3, "tile_index": 1},
        {"col": 1, "row": 3, "tile_index": 1},
        {"col": 2, "row": 3, "tile_index": 2},
        {"col": 3, "row": 3, "tile_index": 1}])))
    tile = json.loads(ok(run(tilemap.get_tile_at(sprite, "terrain", 1, 2, 3))))
    assert tile["tile_index"] == 2


def test_set_tiles_rejects_out_of_range_index(sprite):
    result = run(tilemap.set_tiles(sprite, "terrain", 1, [
        {"col": 0, "row": 0, "tile_index": 99}]))
    assert "out of range" in result
