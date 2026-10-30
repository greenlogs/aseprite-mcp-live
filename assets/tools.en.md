# MCP Tool Reference

Checked against the current source and the tools exposed in this chat on 2026-10-30: **126 tools** in total, consisting of 10 live tools (including optional basic animation) and 116 CLI/utility tools.

The default `core` profile provides 9 live tools. Setting `ASEPRITE_MCP_CAPABILITY_SETS=animation` adds `apply_animation`. The `cli` profile provides 116 CLI/utility tools by default. The `all` profile includes both groups: 125 tools without animation, or 126 with animation enabled. Arbitrary Lua execution is disabled by default; see the final numbered section.

Live tools operate on documents currently open in Aseprite memory, including unsaved documents. CLI tools primarily read, modify, or export files on disk by path. A failed live connection never automatically falls back to CLI.

## Parameter Conventions

Required parameters must be supplied. Optional parameters are shown with their default values. Tables use the abbreviations below; actual calls must use the full field names.

| Abbreviation | Actual parameters |
|---|---|
| `F` | `filename`: Aseprite file path; an absolute path is recommended |
| `L` | `layer_name`: layer name |
| `I` | `frame_index`: frame number, starting at **1** |
| `B` | `x, y, width, height`: rectangle top-left position and dimensions |
| `R` | `start_frame, end_frame`: inclusive frame range |

Coordinates generally start at **0** and dimensions are in pixels. `duration_ms` is in milliseconds; opacity generally ranges from `0–255`. `null` means the parameter may be omitted or explicitly set to null. A cel is the image on a particular layer at a particular frame.

String IDs and revision numbers in the examples are placeholders; replace them with values returned by actual reads. Color formats depend on each tool, commonly `#RRGGBB`. Live drawing batches use a four-channel integer array named `rgba`.

## 1. Live Tools: 10

These tools use WebSocket to operate on an explicitly targeted document in memory. Edits do not automatically save files; use `save_sprite` to save.

### Shared Parameters

| Parameter | Meaning |
|---|---|
| `session_id` | Current editor session ID returned by `get_connection_status` |
| `document_id` | Document ID returned by `list_documents` or document creation |
| `expected_revision` | Document revision from the latest read, used to detect concurrent changes |
| `expected_context` | Optional context revision used to check active layer, frame, and related context |
| `request_id` | Optional request ID, generated when omitted; used for result correlation and deduplication |

After the session reconnects, read document IDs and revisions again. Do not calculate the next revision number yourself.

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `get_connection_status` | Inspect connection status, session, versions, capabilities, and service mode | None | None |
| `list_documents` | List documents open in the editor | `session_id` | None |
| `get_document_info` | Read document dimensions, layers, frames, tags, revisions, and related metadata | `session_id, document_id` | None |
| `create_sprite` | Create an unsaved RGB document | `session_id, width, height` | `request_id=null` |
| `apply_operations` | Apply an atomic batch of drawing/layer operations with one undo step | `session_id, document_id, expected_revision, operations` | `expected_context=null, request_id=null` |
| `apply_animation` | Batch frame creation/deletion, duration changes, and tag edits with one undo step | `session_id, document_id, expected_revision, operations` | `expected_context=null, request_id=null` |
| `get_preview` | Return a PNG image and metadata for a frame or region directly | `session_id, document_id, expected_revision` | `frame=1, scale=1, region=null` |
| `save_sprite` | Explicitly save a native Aseprite file | `session_id, document_id, expected_revision` | `path=null, overwrite=false, request_id=null` |
| `undo` | Undo the target document's latest history action, which may include a manual edit | `session_id, document_id, expected_revision` | `request_id=null` |
| `redo` | Redo a history action in the target document | `session_id, document_id, expected_revision` | `request_id=null` |

`get_preview.region` uses `{"x":0,"y":0,"width":32,"height":32}`. `scale` is an integer from `1–64`, using nearest-neighbor enlargement and still subject to the image pixel budget. Saving an unnamed document requires `path`. Live saving accepts absolute `.aseprite` / `.ase` paths only; overwriting an existing file requires `overwrite=true`.

### operations for apply_operations

Current live drawing primarily supports ordinary RGB layers and provides these four operations:

| `op` | Purpose | Required fields (besides `op`) | Optional fields |
|---|---|---|---|
| `create_layer` | Create a layer | `ref, name` | None |
| `set_opacity` | Set layer opacity | `layer, opacity` | None |
| `pixel` | Draw one pixel | `layer, x, y, rgba` | `frame=1` |
| `rectangle` | Draw a rectangle | `layer, x, y, width, height, rgba` | `frame=1, filled=true` |

- `layer={"kind":"id","value":"layer-id"}` references an existing layer.
- `layer={"kind":"ref","value":"batch-reference"}` references a layer created earlier in the same batch.
- `rgba=[255,0,0,255]` specifies red, green, blue, and alpha, each from `0–255`.

Example: create a layer and draw a red square.

```json
{
  "session_id": "actual-session-id",
  "document_id": "actual-document-id",
  "expected_revision": 3,
  "operations": [
    {"op": "create_layer", "ref": "paint", "name": "Paint"},
    {
      "op": "rectangle",
      "layer": {"kind": "ref", "value": "paint"},
      "frame": 1,
      "x": 4,
      "y": 4,
      "width": 8,
      "height": 8,
      "rgba": [255, 0, 0, 255],
      "filled": true
    }
  ]
}
```

### operations for apply_animation

| `op` | Purpose | Required fields (besides `op`) | Optional fields |
|---|---|---|---|
| `add_frames` | Append the specified number of frames by copying the last frame | `count` | `duration_ms=100` |
| `delete_frame` | Delete a specific frame | `frame` | None |
| `set_frame_duration` | Set duration across an inclusive frame range | `from_frame, to_frame, duration_ms` | None |
| `set_tag` | Create or update an animation tag | `tag, from_frame, to_frame` | `direction="forward"` |
| `delete_tag` | Delete an animation tag | `tag` | None |

`direction` accepts `forward`, `reverse`, `pingpong`, and `pingpong_reverse`. Duration ranges from `1–65535` milliseconds. `count` ranges from `1–255`; live basic animation currently allows at most 256 frames in total, and the only remaining frame cannot be deleted. Live animation currently targets ordinary editable RGB layers.

## 2. CLI: Canvas and Basic Context, 7

CLI operations run in a separate Aseprite process. The active state changed by `set_frame` and `set_layer` belongs to that process; these tools do not switch the active frame or layer in the current GUI editor.

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `create_canvas` | Create a canvas and save it as a file | `width, height` | `filename="canvas.aseprite"` |
| `add_layer` | Add an ordinary layer, optionally inside a group | `F, L` | `group=""` |
| `add_group` | Add a layer group, optionally nested | `F, group_name` | `parent_group=""` |
| `add_frame` | Add one frame | `F` | None |
| `set_frame` | Set the active frame in the CLI document | `F, I` | None |
| `set_frame_duration` | Set one frame's duration | `F, I, duration_ms` | None |
| `set_layer` | Set the active layer in the CLI document | `F, L` | `create_if_missing=false` |

`group` / `parent_group` may be a group name or a `group/subgroup` path. An empty string means the top level.

## 3. CLI: Drawing, 14

Tools ending in `_at` explicitly target a layer and frame. Basic drawing tools without `_at` depend on the active state after the CLI loads the document.

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `draw_pixels` | Draw a batch of pixels | `F, pixels` | None |
| `draw_line` | Draw a straight line | `F, x1, y1, x2, y2` | `color="#000000", thickness=1` |
| `draw_rectangle` | Draw a rectangle | `F, B` | `color="#000000", fill=false` |
| `fill_area` | Flood-fill from a given point | `F, x, y` | `color="#000000"` |
| `draw_circle` | Draw a circle | `F, center_x, center_y, radius` | `color="#000000", fill=false` |
| `draw_pixels_at` | Draw pixels on a specific layer/frame | `F, L, I, pixels` | `create_if_missing=true` |
| `draw_line_at` | Draw a line on a specific layer/frame | `F, L, I, x1, y1, x2, y2` | `color="#000000", thickness=1, create_if_missing=true` |
| `draw_rectangle_at` | Draw a rectangle on a specific layer/frame | `F, L, I, B` | `color="#000000", fill=false, create_if_missing=true` |
| `draw_circle_at` | Draw a circle on a specific layer/frame | `F, L, I, center_x, center_y, radius` | `color="#000000", fill=false, create_if_missing=true` |
| `fill_area_at` | Flood-fill on a specific layer/frame | `F, L, I, x, y` | `color="#000000", create_if_missing=true` |
| `draw_polygon` | Draw a polygon | `F, L, I, points` | `color="#000000", fill=false, create_if_missing=true` |
| `draw_path` | Draw a polyline through multiple points | `F, L, I, points` | `color="#000000", thickness=1, create_if_missing=true` |
| `apply_gradient_rect` | Fill a rectangle with a standard two-color gradient | `F, L, I, B, color_start, color_end` | `horizontal=true, create_if_missing=true` |
| `draw_ellipse_at` | Draw an ellipse | `F, L, I, center_x, center_y, radius_x, radius_y` | `color="#000000", fill=false, create_if_missing=true` |

Array formats:

```json
{
  "pixels": [{"x": 1, "y": 2, "color": "#FF0000"}],
  "points": [{"x": 0, "y": 0}, {"x": 8, "y": 8}, {"x": 16, "y": 0}]
}
```

## 4. CLI: Animation and Cels, 24

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `add_frames` | Add multiple frames, optionally setting their duration | `F, count` | `duration_ms=null` |
| `set_frame_duration_all` | Set the duration of all frames | `F, duration_ms` | None |
| `set_layer_visibility` | Show or hide a layer | `F, L` | `visible=true` |
| `set_layer_opacity` | Set layer opacity | `F, L, opacity` | None |
| `get_sprite_info` | Read dimensions, color mode, frames, layers, and tags from a sprite file | `F` | None |
| `duplicate_frame_range` | Copy a frame range and append it to the end | `F, R` | `times=1` |
| `set_cel_position` | Set a cel's position | `F, L, I, x, y` | `create_if_missing=false, source_frame_index=null` |
| `tween_cel_positions` | Interpolate cel positions linearly | `F, L, R, start_x, start_y, end_x, end_y` | `create_missing_cels=false, source_frame_index=null` |
| `offset_cel_positions` | Move cels across a frame range by a fixed offset | `F, L, R, dx, dy` | None |
| `create_cel` | Create an empty cel on a specific layer/frame | `F, L, I` | `x=0, y=0` |
| `clear_cel` | Delete a specific cel | `F, L, I` | None |
| `copy_cel` | Copy a cel between frames on the same layer | `F, L, source_frame, target_frame` | `replace=true` |
| `copy_frame` | Copy a whole frame to a target frame or append it | `F, source_frame` | `target_frame=null, overwrite=true` |
| `propagate_frame_to_range` | Copy all layers from a source frame across a frame range | `F, source_frame, R` | `overwrite=true` |
| `set_tag` | Create or update an animation tag | `F, name, from_frame, to_frame` | `direction="forward"` |
| `set_onion_skin` | Configure onion-skin settings | `F` | `enabled=true, before=2, after=2, opacity=128` |
| `propagate_cels` | Copy cels from selected layers across a frame range | `F, layer_names, source_frame, R` | `replace=true` |
| `tween_cel_positions_eased` | Interpolate positions with easing | `F, L, R, start_x, start_y, end_x, end_y` | `easing="smoothstep", create_missing_cels=false, source_frame_index=null` |
| `oscillate_cel_positions` | Oscillate cel positions along a sine wave | `F, L, R` | `amplitude_x=0, amplitude_y=0, cycles=1.0, phase_deg=0.0, create_missing_cels=false, source_frame_index=null` |
| `tween_cel_opacity_eased` | Interpolate cel opacity with easing | `F, L, R, start_opacity, end_opacity` | `easing="smoothstep", create_missing_cels=false, source_frame_index=null` |
| `tween_cel_scale_eased` | Interpolate cel scale with easing | `F, L, R, start_scale, end_scale` | `easing="smoothstep", anchor="center", replace=true, create_missing_cels=true, source_frame_index=null` |
| `delete_frame` | Delete a frame | `F, I` | None |
| `delete_tag` | Delete a tag | `F, name` | None |
| `set_cel_opacity` | Set the opacity of a single cel | `F, L, I, opacity` | None |

`layer_names` is a string array, such as `["Character","Shadow"]`. `source_frame_index` supplies a frame to copy from when creating missing cels. The CLI `set_tag` tool uses the field `name`; the live animation operation uses `tag`.

## 5. CLI: Layer Management, 7

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `delete_layer` | Delete a layer | `F, L` | None |
| `rename_layer` | Rename a layer | `F, L, new_name` | None |
| `duplicate_layer` | Duplicate a layer, optionally specifying its name and destination group | `F, L` | `new_name="", group=""` |
| `reorder_layer` | Change a layer's stacking position | `F, L, position` | None |
| `set_layer_blend_mode` | Set a layer's blend mode | `F, L, mode` | None |
| `merge_layer_down` | Merge a layer down | `F, L` | None |
| `flatten_sprite` | Flatten the sprite's layers | `F` | None |

## 6. CLI: Transforms, 4

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `flip_layer` | Flip a cel image horizontally or vertically | `F, L, I` | `direction="horizontal"` |
| `rotate_layer` | Rotate a cel image clockwise | `F, L, I` | `angle=90` |
| `resize_canvas` | Scale the canvas and its contents to new dimensions | `F, width, height` | None |
| `crop_canvas` | Crop the canvas, discarding content outside the region | `F, B` | None |

`flip_layer.direction` accepts `horizontal` / `vertical`. `rotate_layer.angle` accepts `90` / `180` / `270`.

## 7. CLI: Region Copying and Erasing, 4

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `move_region` | Cut and move a rectangle, leaving the source transparent | `F, L, I, B, dest_x, dest_y` | None |
| `copy_region` | Copy a rectangle, optionally to another layer or frame | `F, L, I, B, dest_x, dest_y` | `target_layer_name="", target_frame_index=0` |
| `erase_region` | Erase a rectangular region | `F, L, I, B` | None |
| `erase_color` | Make a particular color transparent | `F, L, I, color` | `tolerance=0` |

By default, `copy_region` targets the source layer and frame. `tolerance` controls color matching; `0` means an exact match.

## 8. CLI: Palettes, 8

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `get_palette` | Read the palette | `F` | None |
| `set_palette` | Set the palette from a color list | `F, colors` | None |
| `remap_colors_in_cel_range` | Replace colors using mappings on a layer across a frame range | `F, L, R, mappings` | `create_missing_cels=false, source_frame_index=null` |
| `list_palette_presets` | List built-in retro palettes and their colors | None | None |
| `apply_palette_preset` | Apply a built-in palette; only the palette changes | `F, preset` | None |
| `generate_color_ramp` | Generate a dark-to-light shading ramp from a base color | `base_color` | `steps=5, hue_shift_degrees=20, lightness_range=0.5` |
| `quantize_to_palette` | Match pixel colors to the nearest palette colors | `F` | `layer_name="", start_frame=1, end_frame=0` |
| `set_color_mode` | Convert to RGB, grayscale, or indexed color mode | `F, mode` | None |

Parameter examples:

```json
{
  "colors": ["#000000", "#FFFFFF", "#FF0000"],
  "mappings": [{"from": "#FF0000", "to": "#00FF00"}]
}
```

`preset` accepts `gameboy`, `monochrome`, `grayscale_4`, `cga`, `pico8`, `c64`, `dawnbringer16`, and `dawnbringer32`. `mode` accepts `rgb` / `grayscale` / `indexed`. For `quantize_to_palette`, `end_frame=0` means the last frame, and an empty layer name processes all top-level layers.

## 9. CLI: Pixel-Art Effects, 5

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `outline_cel` | Add a pixel outline to a cel | `F, L, I` | `color="#000000", include_diagonals=false` |
| `replace_color` | Replace a color in a cel | `F, L, I, from_color, to_color` | `tolerance=0` |
| `adjust_hsl` | Adjust hue, saturation, and lightness | `F, L, I` | `hue_shift=0, saturation_shift=0, lightness_shift=0` |
| `apply_dither_gradient` | Create a two-color gradient with ordered dithering | `F, L, I, B, color_start, color_end` | `horizontal=false, create_if_missing=true` |
| `apply_dither_pattern` | Create a dithered texture with a fixed mix of two colors | `F, L, I, B, color_a, color_b` | `density=0.5, create_if_missing=true` |

`hue_shift` is in degrees, from `-360` to `360`; saturation and lightness shifts range from `-100` to `100`. `density` ranges from `0–1` and specifies the proportion of `color_b`.

## 10. CLI: Native Aseprite Filters, 7

In this table, `N` represents this group of **optional parameters**:

```text
layer_name="", frame_index=1, x=0, y=0, width=0, height=0
```

The operation is restricted to the rectangle when both width and height are greater than 0. Otherwise, that rectangular restriction is not applied. An empty layer name uses the active layer.

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `outline_native` | Apply the native outline command | `F` | `layer_name="", frame_index=1, color="#000000", place="outside", matrix="circle"` |
| `adjust_hsl_native` | Apply native HSL adjustment | `F` | `N`, plus `hue=0, saturation=0, lightness=0` |
| `adjust_brightness_contrast` | Adjust brightness and contrast | `F` | `N`, plus `brightness=0, contrast=0` |
| `invert_colors` | Invert colors | `F` | `N` |
| `apply_convolution` | Apply convolution filters such as blur, sharpen, or edge detection | `F, matrix` | `N` |
| `list_convolution_matrices` | List available built-in convolution matrix names | None | None |
| `extract_palette` | Extract colors from the image to generate a palette | `F` | `max_colors=16, with_alpha=false` |

Example convolution matrices: `blur-3x3`, `sharpen-3x3`, `edges-find`, and `misc-emboss`.

## 11. CLI: Pixel Reading, 4

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `get_pixel_color` | Read RGBA at one point on a single layer | `F, x, y` | `layer_name="", frame_index=1` |
| `get_pixels_rect` | Read every pixel in a rectangle on a single layer | `F, B` | `layer_name="", frame_index=1` |
| `get_composite_pixel` | Read the composited color of all visible layers at one point | `F, x, y` | `frame_index=1` |
| `get_composite_rect` | Read composited pixels from all visible layers in a rectangle | `F, B` | `frame_index=1` |

The first two tools read a single layer; an empty layer name uses the active layer. The latter two are useful for checking the final visible image.

## 12. CLI: Export and Import, 7

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `export_sprite` | Export a sprite image | `F, output_filename` | `format="png"` |
| `copy_sprite` | Save a copy of the sprite to another path | `F, output_filename` | `overwrite=false` |
| `export_frame` | Export one frame, optionally enlarged by an integer factor | `F, I, output_filename` | `scale=1` |
| `export_spritesheet` | Export a sprite sheet, optionally with JSON metadata | `F, output_filename` | `sheet_type="horizontal", data_filename="", scale=1, padding=0, tag_name="", data_format="json-array", list_tags=false` |
| `export_layers` | Export layers separately to a directory | `F, output_directory` | `include_hidden=false` |
| `export_tag` | Export a specific animation tag | `F, tag_name, output_filename` | `scale=1` |
| `import_image_as_layer` | Import an external image into a layer/frame | `F, image_path, L` | `frame_index=1, x=0, y=0` |

`sheet_type` accepts `horizontal`, `vertical`, `rows`, `columns`, and `packed`. `data_format` accepts `json-array` / `json-hash`.

## 13. CLI: Analysis and Inspection, 3

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `render_onion_skin` | Composite a frame and translucent neighboring-frame ghosts into a PNG | `F, I, output_filename` | `before=1, after=1, scale=4, ghost_opacity=100` |
| `compare_frames` | Compare two frames and return changed pixel count, percentage, and bounding box | `F, frame_a, frame_b` | None |
| `get_color_stats` | Report color counts and usage frequencies in a frame | `F` | `frame_index=1, top=16` |

## 14. CLI: Animation Quality and Repair, 4

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `ensure_layers_present` | Ensure specified layers have cels across a frame range | `F, layer_names` | `start_frame=1, end_frame=null` |
| `validate_scene` | Check required layers and cels, returning missing items | `F, required_layers` | `start_frame=1, end_frame=null` |
| `audit_animation` | Check layer overlaps, activity outside allowed frame ranges, and related issues | `F` | See below |
| `animation_sanitize` | Check animation consistency and optionally apply fixes | `F` | See below |

Optional parameters for `audit_animation`:

```text
start_frame=1
end_frame=null
layer_names=null
overlap_pairs=null
layer_frame_ranges=null
report_cels=false
report_bounds=false
max_overlaps=200
max_out_of_range=200
```

Optional parameters for `animation_sanitize`:

```text
start_frame=1
end_frame=null
layer_names=null
layer_order=null
layer_frame_ranges=null
ensure_layers=null
overlap_pairs=null
report_bounds=false
max_overlaps=200
ignore_full_canvas_overlaps=true
out_of_range_action="set_opacity_zero"
out_of_range_opacity=0
report_only=false
include_stats=true
```

Related array formats:

```json
{
  "overlap_pairs": ["Character,Background", "LeftHand:Body"],
  "layer_frame_ranges": ["Character:1-8,17-24", "Clouds:1-12"],
  "layer_order": ["Background", "Character", "Foreground"]
}
```

`out_of_range_action` accepts `set_opacity_zero`, `delete_cels`, and `none`. Set `report_only=true` to inspect without applying fixes. For these tools, `end_frame=null` means the last frame.

## 15. CLI: Slices, 5

Slices mark regions, nine-patch centers, and pivots for use in game engines.

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `create_slice` | Create a named slice | `F, name, B` | None |
| `set_slice_center` | Set the stretchable center region of a nine-patch slice | `F, name, B` | None |
| `set_slice_pivot` | Set a slice's pivot | `F, name, x, y` | None |
| `list_slices` | List slices with bounds, centers, and pivots | `F` | None |
| `delete_slice` | Delete a slice | `F, name` | None |

Center and pivot coordinates are relative to the slice origin.

## 16. CLI: Tilemaps, 5

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `create_tilemap_layer` | Create a tilemap layer with its own tileset | `F, L, tile_width, tile_height` | None |
| `draw_on_tile` | Edit a tile's pixels, appending a tile when applicable | `F, L, tile_index, pixels` | None |
| `set_tiles` | Place tiles at grid positions | `F, L, I, tiles` | None |
| `get_tile_at` | Read the tile index at a grid position | `F, L, I, col, row` | None |
| `get_tilemap_info` | Read tile dimensions, tile count, and map dimensions | `F, L` | None |

Format of `tiles`:

```json
[
  {"col": 0, "row": 0, "tile_index": 1},
  {"col": 1, "row": 0, "tile_index": 2}
]
```

`col/row` start at 0. Tile index `0` represents an empty cell; the first actual tile is `1`. Pixel coordinates for `draw_on_tile` are relative to the tile's top-left corner. `pixels` uses the same `[{"x":0,"y":0,"color":"#FF0000"}]` format.

## 17. CLI/Utilities: Text, 3

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `list_text_fonts` | List available fonts | None | None |
| `measure_text` | Measure text dimensions without drawing | `text, font` | `size=1, letter_spacing=0, bold=0, antialias=false` |
| `draw_text` | Draw text onto a sprite, optionally with outline and shadow | `F, text, x, y, font` | See below |

Optional parameters for `draw_text`:

```text
size=1
color="#FFFFFF"
layer_name=null
frame_index=1
anchor="topleft"
letter_spacing=0
bold=0
outline_color=null
outline_width=1
outline_diagonal=true
shadow_color=null
shadow_dx=1
shadow_dy=1
antialias=false
create_if_missing=true
```

`font` may be a name returned by the font list or a font path. For TrueType fonts, `size` is the pixel size; for bitmap fonts, it is an integer scale factor. `anchor` specifies which point of the text aligns to `(x,y)` and accepts:

```text
topleft, top, topright,
left, center, right,
bottomleft, bottom, bottomright,
baselineleft, baseline, baselineright
```

## 18. CLI: Copying Between Files, 1

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `copy_layers_between_sprites` | Copy selected layers from a source file to a target file | `source_filename, target_filename, layer_names` | `replace=true, create_missing_frames=true` |

## 19. Utilities: HTTP Preview, 2

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `start_preview_server` | Start an HTTP server for browsing a directory of exported images | `directory` | `port=8000` |
| `stop_preview_server` | Stop the preview server on a specified port | None | `port=8000` |

HTTP preview serves exported files; it is a separate interface from the live `get_preview` tool.

## 20. Utilities: Animation Guide, 1

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `animation_workflow_guide` | Return animation workflow advice in English | None | `use_case="character"` |

## 21. CLI: Unified Protocol Entry Point, 1

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `cli_execute` | Read a disk file or execute an atomic drawing batch using protocol v1 | `request` object | Defined by fields inside the request |

Fields inside `request`:

| Field | Required? | Meaning |
|---|---|---|
| `request_id` | Yes | Unique request identifier |
| `target` | Yes | `{"backend":"cli","path":"absolute path to an existing file"}` |
| `action` | Yes | `get_document_info` or `apply_operations` |
| `protocol_version` | No | Defaults to `1` |
| `expected_file_revision` | No | File SHA-256 returned by a previous read, used to detect external changes |

Read example:

```json
{
  "request": {
    "request_id": "read-001",
    "target": {
      "backend": "cli",
      "path": "E:/Art/hero.aseprite"
    },
    "action": {
      "name": "get_document_info"
    }
  }
}
```

For batch editing, use this structure for `action`:

```json
{
  "name": "apply_operations",
  "operations": [
    {"op": "create_layer", "ref": "paint", "name": "Paint"},
    {
      "op": "pixel",
      "layer": {"kind": "ref", "value": "paint"},
      "x": 1,
      "y": 1,
      "rgba": [255, 0, 0, 255]
    }
  ]
}
```

Currently, `cli_execute` supports reads and the four basic drawing operations described above. It does not support `apply_animation`. CLI targets do not use the live `expected_revision` / `expected_context` fields.

## 22. Disabled by Default: Arbitrary Lua

| Tool | Purpose | Required parameters | Optional parameters |
|---|---|---|---|
| `run_lua_script` | Execute Lua source in Aseprite CLI | `script` | `filename=""` |

Requires explicitly setting `ASEPRITE_MCP_ENABLE_RAW_LUA=1` with the `cli` / `all` profile. This tool is not exposed in the current chat and is not included in the 126-tool total above. When `filename` is supplied, the file is opened first. Script changes must be saved explicitly, and output is returned through `print()`. Scripts have Lua file and system access capabilities.

## Common Workflow and Source Files

For creating or editing on the current canvas, the usual sequence is:

```text
get_connection_status
→ list_documents
→ get_document_info
→ apply_operations / apply_animation
→ get_preview
→ save_sprite when saving is needed
```

Palettes, filters, tweening, and tilemaps are currently provided primarily through CLI file tools. CLI changes do not enter the undo history of the document currently open in GUI memory. This list describes registered interfaces; it does not imply that every platform and version has been verified.

Source locations:

- [Live and CLI tool registration](../aseprite_mcp/server.py)
- [Protocol and batch operation parameters](../aseprite_mcp/core/protocol.py)
- [Unified CLI backend](../aseprite_mcp/backends/cli.py)
- [CLI/utility tool implementations](../aseprite_mcp/tools/)
