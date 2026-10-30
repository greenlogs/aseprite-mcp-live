# MCP 工具清单

按 2026-10-30 当前源码及本聊天实际暴露的工具核对，共 **126 个**：10 个实时工具（含可选基础动画）和 116 个 CLI/辅助工具。

默认 `core` 配置提供 9 个实时工具；设置 `ASEPRITE_MCP_CAPABILITY_SETS=animation` 后增加 `apply_animation`。`cli` 配置默认提供 116 个 CLI/辅助工具；`all` 配置包含两类，未启用动画时为 125 个，启用后为 126 个。任意 Lua 工具默认关闭，另见文末。

实时工具操作 Aseprite 当前打开的内存文档，包括尚未保存的文档；CLI 工具主要通过文件路径读取、修改或导出磁盘文件。实时连接失败不会自动切换到 CLI。

## 参数阅读约定

“必填参数”必须提供；“可选参数”列出默认值。表格采用以下缩写，实际调用必须使用完整字段名。

| 缩写 | 实际参数 |
|---|---|
| `F` | `filename`：Aseprite 文件路径，建议使用绝对路径 |
| `L` | `layer_name`：图层名称 |
| `I` | `frame_index`：帧号，从 **1** 开始 |
| `B` | `x, y, width, height`：矩形左上角位置及宽高 |
| `R` | `start_frame, end_frame`：起止帧，包含两端 |

坐标通常从 **0** 开始，尺寸单位为像素；`duration_ms` 为毫秒；不透明度通常为 `0–255`。`null` 表示可以省略或传空值。Cel 指某个图层在某一帧上的图像。

下文示例中的字符串 ID 和修订号均为占位值，调用时须替换为实际读取结果。颜色格式以各工具约束为准，常用 `#RRGGBB`；实时批量绘图使用四通道整数数组 `rgba`。

## 1. 实时工具：10 个

这些工具通过 WebSocket 操作明确指定的内存文档。除 `save_sprite` 外，编辑不会自动保存文件。

### 公共参数

| 参数 | 含义 |
|---|---|
| `session_id` | 从 `get_connection_status` 获取的当前编辑器会话 ID |
| `document_id` | 从 `list_documents` 或创建结果获取的文档 ID |
| `expected_revision` | 最近读取结果中的文档修订号，用于发现并发修改 |
| `expected_context` | 可选上下文修订号，用于检查活动图层、帧等上下文 |
| `request_id` | 可选请求 ID；省略时自动生成，用于关联结果和去重 |

会话重新连接后，须重新读取文档 ID 和修订信息；不要推算下一次修订号。

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `get_connection_status` | 查看连接状态、会话、版本、能力及服务模式 | 无 | 无 |
| `list_documents` | 列出编辑器中打开的文档 | `session_id` | 无 |
| `get_document_info` | 读取文档尺寸、图层、帧、标签与修订等信息 | `session_id, document_id` | 无 |
| `create_sprite` | 创建尚未保存的 RGB 文档 | `session_id, width, height` | `request_id=null` |
| `apply_operations` | 原子执行一批绘图/图层操作，整批对应一次撤销 | `session_id, document_id, expected_revision, operations` | `expected_context=null, request_id=null` |
| `apply_animation` | 批量增删帧、调整时长及标签，整批对应一次撤销 | `session_id, document_id, expected_revision, operations` | `expected_context=null, request_id=null` |
| `get_preview` | 直接返回指定帧或区域的 PNG 图片及元数据 | `session_id, document_id, expected_revision` | `frame=1, scale=1, region=null` |
| `save_sprite` | 显式保存原生 Aseprite 文件 | `session_id, document_id, expected_revision` | `path=null, overwrite=false, request_id=null` |
| `undo` | 撤销目标文档的最新历史动作，可能包括人工操作 | `session_id, document_id, expected_revision` | `request_id=null` |
| `redo` | 重做目标文档的历史动作 | `session_id, document_id, expected_revision` | `request_id=null` |

`get_preview.region` 格式为 `{"x":0,"y":0,"width":32,"height":32}`；`scale` 为 `1–64` 的整数，使用最近邻放大，仍受图片像素预算限制。未命名文档保存必须提供 `path`，实时保存限 `.aseprite` / `.ase` 的绝对路径；覆盖已有文件须设置 `overwrite=true`。

### apply_operations 的 operations

当前实时绘图主要支持普通 RGB 图层，包含以下四种操作：

| `op` | 用途 | 必填字段（除 `op` 外） | 可选字段 |
|---|---|---|---|
| `create_layer` | 新建图层 | `ref, name` | 无 |
| `set_opacity` | 设置图层不透明度 | `layer, opacity` | 无 |
| `pixel` | 绘制一个像素 | `layer, x, y, rgba` | `frame=1` |
| `rectangle` | 绘制矩形 | `layer, x, y, width, height, rgba` | `frame=1, filled=true` |

- `layer={"kind":"id","value":"图层ID"}`：引用已有图层。
- `layer={"kind":"ref","value":"本批次引用名"}`：引用同一批次前面创建的图层。
- `rgba=[255,0,0,255]`：红、绿、蓝、透明度，均为 `0–255`。

例如，新建图层并绘制红色方块：

```json
{
  "session_id": "实际会话ID",
  "document_id": "实际文档ID",
  "expected_revision": 3,
  "operations": [
    {"op": "create_layer", "ref": "paint", "name": "绘制层"},
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

### apply_animation 的 operations

| `op` | 用途 | 必填字段（除 `op` 外） | 可选字段 |
|---|---|---|---|
| `add_frames` | 在末尾复制最后一帧，增加指定数量的帧 | `count` | `duration_ms=100` |
| `delete_frame` | 删除指定帧 | `frame` | 无 |
| `set_frame_duration` | 设置指定帧区间的时长 | `from_frame, to_frame, duration_ms` | 无 |
| `set_tag` | 创建或更新动画标签 | `tag, from_frame, to_frame` | `direction="forward"` |
| `delete_tag` | 删除动画标签 | `tag` | 无 |

`direction` 支持 `forward`、`reverse`、`pingpong`、`pingpong_reverse`；时长范围为 `1–65535` 毫秒。`count` 为 `1–255`，当前实时基础动画限制总帧数最多 256 帧，不能删除唯一的一帧。实时动画以 RGB 普通可编辑图层为当前范围。

## 2. CLI：画布与基础上下文，7 个

CLI 操作运行在独立的 Aseprite 进程中，`set_frame`、`set_layer` 的活动状态也属于该进程，不能用于切换当前 GUI 编辑器的活动帧或图层。

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `create_canvas` | 新建画布并保存为文件 | `width, height` | `filename="canvas.aseprite"` |
| `add_layer` | 添加普通图层，可放入组内 | `F, L` | `group=""` |
| `add_group` | 添加图层组，可嵌套 | `F, group_name` | `parent_group=""` |
| `add_frame` | 添加一帧 | `F` | 无 |
| `set_frame` | 设置 CLI 文档活动帧 | `F, I` | 无 |
| `set_frame_duration` | 设置单帧时长 | `F, I, duration_ms` | 无 |
| `set_layer` | 设置 CLI 文档活动图层 | `F, L` | `create_if_missing=false` |

`group` / `parent_group` 可使用组名或 `group/subgroup` 路径，空字符串表示顶层。

## 3. CLI：绘图，14 个

带 `_at` 的工具明确指定图层和帧；不带 `_at` 的基础绘图工具依赖 CLI 加载文档后的活动状态。

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `draw_pixels` | 批量绘制像素 | `F, pixels` | 无 |
| `draw_line` | 绘制直线 | `F, x1, y1, x2, y2` | `color="#000000", thickness=1` |
| `draw_rectangle` | 绘制矩形 | `F, B` | `color="#000000", fill=false` |
| `fill_area` | 从指定点使用油漆桶填充 | `F, x, y` | `color="#000000"` |
| `draw_circle` | 绘制圆形 | `F, center_x, center_y, radius` | `color="#000000", fill=false` |
| `draw_pixels_at` | 在指定图层/帧批量绘制像素 | `F, L, I, pixels` | `create_if_missing=true` |
| `draw_line_at` | 在指定图层/帧画直线 | `F, L, I, x1, y1, x2, y2` | `color="#000000", thickness=1, create_if_missing=true` |
| `draw_rectangle_at` | 在指定图层/帧画矩形 | `F, L, I, B` | `color="#000000", fill=false, create_if_missing=true` |
| `draw_circle_at` | 在指定图层/帧画圆 | `F, L, I, center_x, center_y, radius` | `color="#000000", fill=false, create_if_missing=true` |
| `fill_area_at` | 在指定图层/帧进行油漆桶填充 | `F, L, I, x, y` | `color="#000000", create_if_missing=true` |
| `draw_polygon` | 绘制多边形 | `F, L, I, points` | `color="#000000", fill=false, create_if_missing=true` |
| `draw_path` | 沿多个点绘制折线 | `F, L, I, points` | `color="#000000", thickness=1, create_if_missing=true` |
| `apply_gradient_rect` | 填充普通双色渐变矩形 | `F, L, I, B, color_start, color_end` | `horizontal=true, create_if_missing=true` |
| `draw_ellipse_at` | 绘制椭圆 | `F, L, I, center_x, center_y, radius_x, radius_y` | `color="#000000", fill=false, create_if_missing=true` |

数组格式：

```json
{
  "pixels": [{"x": 1, "y": 2, "color": "#FF0000"}],
  "points": [{"x": 0, "y": 0}, {"x": 8, "y": 8}, {"x": 16, "y": 0}]
}
```

## 4. CLI：动画与 Cel，24 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `add_frames` | 增加多帧，可指定新帧时长 | `F, count` | `duration_ms=null` |
| `set_frame_duration_all` | 设置全部帧的时长 | `F, duration_ms` | 无 |
| `set_layer_visibility` | 显示或隐藏图层 | `F, L` | `visible=true` |
| `set_layer_opacity` | 设置图层不透明度 | `F, L, opacity` | 无 |
| `get_sprite_info` | 读取磁盘精灵的尺寸、颜色模式、帧、图层和标签 | `F` | 无 |
| `duplicate_frame_range` | 复制一段帧，追加到末尾 | `F, R` | `times=1` |
| `set_cel_position` | 设置某个 Cel 的位置 | `F, L, I, x, y` | `create_if_missing=false, source_frame_index=null` |
| `tween_cel_positions` | 对 Cel 位置做线性补间 | `F, L, R, start_x, start_y, end_x, end_y` | `create_missing_cels=false, source_frame_index=null` |
| `offset_cel_positions` | 将一段帧中的 Cel 整体平移 | `F, L, R, dx, dy` | 无 |
| `create_cel` | 在指定图层/帧创建空 Cel | `F, L, I` | `x=0, y=0` |
| `clear_cel` | 删除指定 Cel | `F, L, I` | 无 |
| `copy_cel` | 在同一图层的帧之间复制 Cel | `F, L, source_frame, target_frame` | `replace=true` |
| `copy_frame` | 复制整帧，指定目标或追加 | `F, source_frame` | `target_frame=null, overwrite=true` |
| `propagate_frame_to_range` | 将一帧的全部图层内容复制到帧区间 | `F, source_frame, R` | `overwrite=true` |
| `set_tag` | 创建或更新动画标签 | `F, name, from_frame, to_frame` | `direction="forward"` |
| `set_onion_skin` | 配置洋葱皮参数 | `F` | `enabled=true, before=2, after=2, opacity=128` |
| `propagate_cels` | 将指定图层的 Cel 复制到帧区间 | `F, layer_names, source_frame, R` | `replace=true` |
| `tween_cel_positions_eased` | 对位置做缓动补间 | `F, L, R, start_x, start_y, end_x, end_y` | `easing="smoothstep", create_missing_cels=false, source_frame_index=null` |
| `oscillate_cel_positions` | 让 Cel 按正弦曲线摆动 | `F, L, R` | `amplitude_x=0, amplitude_y=0, cycles=1.0, phase_deg=0.0, create_missing_cels=false, source_frame_index=null` |
| `tween_cel_opacity_eased` | 对 Cel 不透明度做缓动补间 | `F, L, R, start_opacity, end_opacity` | `easing="smoothstep", create_missing_cels=false, source_frame_index=null` |
| `tween_cel_scale_eased` | 对 Cel 缩放比例做缓动补间 | `F, L, R, start_scale, end_scale` | `easing="smoothstep", anchor="center", replace=true, create_missing_cels=true, source_frame_index=null` |
| `delete_frame` | 删除一帧 | `F, I` | 无 |
| `delete_tag` | 删除标签 | `F, name` | 无 |
| `set_cel_opacity` | 设置单个 Cel 的不透明度 | `F, L, I, opacity` | 无 |

`layer_names` 是字符串数组，如 `["人物","阴影"]`。`source_frame_index` 用于为缺失的 Cel 提供复制来源。CLI 的 `set_tag` 使用字段 `name`，实时动画操作则使用 `tag`。

## 5. CLI：图层管理，7 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `delete_layer` | 删除图层 | `F, L` | 无 |
| `rename_layer` | 重命名图层 | `F, L, new_name` | 无 |
| `duplicate_layer` | 复制图层，可指定名称和目标组 | `F, L` | `new_name="", group=""` |
| `reorder_layer` | 调整图层堆叠位置 | `F, L, position` | 无 |
| `set_layer_blend_mode` | 设置图层混合模式 | `F, L, mode` | 无 |
| `merge_layer_down` | 向下合并图层 | `F, L` | 无 |
| `flatten_sprite` | 将精灵图层合并为平面图像 | `F` | 无 |

## 6. CLI：变换，4 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `flip_layer` | 水平或垂直翻转指定 Cel 图像 | `F, L, I` | `direction="horizontal"` |
| `rotate_layer` | 顺时针旋转指定 Cel 图像 | `F, L, I` | `angle=90` |
| `resize_canvas` | 将画布及其内容缩放到新尺寸 | `F, width, height` | 无 |
| `crop_canvas` | 裁剪画布，丢弃区域外内容 | `F, B` | 无 |

`flip_layer.direction` 支持 `horizontal` / `vertical`；`rotate_layer.angle` 支持 `90` / `180` / `270`。

## 7. CLI：区域复制与擦除，4 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `move_region` | 剪切矩形区域并移动，原区域变透明 | `F, L, I, B, dest_x, dest_y` | 无 |
| `copy_region` | 复制矩形区域，可跨图层或帧 | `F, L, I, B, dest_x, dest_y` | `target_layer_name="", target_frame_index=0` |
| `erase_region` | 擦除矩形区域 | `F, L, I, B` | 无 |
| `erase_color` | 将指定颜色变透明 | `F, L, I, color` | `tolerance=0` |

`copy_region` 的默认目标是源图层和源帧；`tolerance` 是颜色匹配容差，`0` 表示精确匹配。

## 8. CLI：调色板，8 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `get_palette` | 读取调色板 | `F` | 无 |
| `set_palette` | 使用颜色列表设置调色板 | `F, colors` | 无 |
| `remap_colors_in_cel_range` | 在指定图层/帧区间按映射替换颜色 | `F, L, R, mappings` | `create_missing_cels=false, source_frame_index=null` |
| `list_palette_presets` | 列出内置复古调色板及其颜色 | 无 | 无 |
| `apply_palette_preset` | 应用内置调色板，仅改变调色板 | `F, preset` | 无 |
| `generate_color_ramp` | 根据基色生成从暗到亮的配色阶梯 | `base_color` | `steps=5, hue_shift_degrees=20, lightness_range=0.5` |
| `quantize_to_palette` | 将像素颜色匹配到调色板最近颜色 | `F` | `layer_name="", start_frame=1, end_frame=0` |
| `set_color_mode` | 转换 RGB、灰度或索引颜色模式 | `F, mode` | 无 |

参数示例：

```json
{
  "colors": ["#000000", "#FFFFFF", "#FF0000"],
  "mappings": [{"from": "#FF0000", "to": "#00FF00"}]
}
```

`preset` 支持 `gameboy`、`monochrome`、`grayscale_4`、`cga`、`pico8`、`c64`、`dawnbringer16`、`dawnbringer32`。`mode` 为 `rgb` / `grayscale` / `indexed`。`quantize_to_palette.end_frame=0` 表示最后一帧；空图层名表示处理全部顶层图层。

## 9. CLI：像素风特效，5 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `outline_cel` | 为 Cel 添加像素描边 | `F, L, I` | `color="#000000", include_diagonals=false` |
| `replace_color` | 替换 Cel 中的颜色 | `F, L, I, from_color, to_color` | `tolerance=0` |
| `adjust_hsl` | 调整色相、饱和度和亮度 | `F, L, I` | `hue_shift=0, saturation_shift=0, lightness_shift=0` |
| `apply_dither_gradient` | 用两种颜色的有序抖动生成渐变 | `F, L, I, B, color_start, color_end` | `horizontal=false, create_if_missing=true` |
| `apply_dither_pattern` | 用两种颜色生成固定比例的抖动纹理 | `F, L, I, B, color_a, color_b` | `density=0.5, create_if_missing=true` |

`hue_shift` 单位为度，范围为 `-360–360`；饱和度和亮度偏移范围为 `-100–100`。`density` 为 `0–1`，表示 `color_b` 的比例。

## 10. CLI：Aseprite 原生滤镜，7 个

表格中的 `N` 表示这一组**可选参数**：

```text
layer_name="", frame_index=1, x=0, y=0, width=0, height=0
```

宽高都大于 0 时限定处理区域，否则不限定该矩形区域。空图层名使用活动图层。

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `outline_native` | 调用原生描边功能 | `F` | `layer_name="", frame_index=1, color="#000000", place="outside", matrix="circle"` |
| `adjust_hsl_native` | 调用原生 HSL 调整 | `F` | `N`，以及 `hue=0, saturation=0, lightness=0` |
| `adjust_brightness_contrast` | 调整亮度与对比度 | `F` | `N`，以及 `brightness=0, contrast=0` |
| `invert_colors` | 反相颜色 | `F` | `N` |
| `apply_convolution` | 应用模糊、锐化、边缘检测等卷积滤镜 | `F, matrix` | `N` |
| `list_convolution_matrices` | 列出可用的内置卷积矩阵名称 | 无 | 无 |
| `extract_palette` | 从图像提取颜色，生成调色板 | `F` | `max_colors=16, with_alpha=false` |

卷积矩阵示例：`blur-3x3`、`sharpen-3x3`、`edges-find`、`misc-emboss`。

## 11. CLI：像素读取，4 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `get_pixel_color` | 读取单图层某点的 RGBA | `F, x, y` | `layer_name="", frame_index=1` |
| `get_pixels_rect` | 读取单图层矩形区域中的全部像素 | `F, B` | `layer_name="", frame_index=1` |
| `get_composite_pixel` | 读取全部可见图层合成后的某点颜色 | `F, x, y` | `frame_index=1` |
| `get_composite_rect` | 读取全部可见图层合成后的矩形像素 | `F, B` | `frame_index=1` |

前两项读取单个图层，空图层名使用活动图层；后两项适合检查最终可见画面的颜色。

## 12. CLI：导出与导入，7 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `export_sprite` | 导出精灵图像 | `F, output_filename` | `format="png"` |
| `copy_sprite` | 将精灵复制保存到另一路径 | `F, output_filename` | `overwrite=false` |
| `export_frame` | 导出指定帧，可整数放大 | `F, I, output_filename` | `scale=1` |
| `export_spritesheet` | 导出精灵表，可附带 JSON 元数据 | `F, output_filename` | `sheet_type="horizontal", data_filename="", scale=1, padding=0, tag_name="", data_format="json-array", list_tags=false` |
| `export_layers` | 分图层导出到目录 | `F, output_directory` | `include_hidden=false` |
| `export_tag` | 导出指定动画标签 | `F, tag_name, output_filename` | `scale=1` |
| `import_image_as_layer` | 将外部图片导入指定图层/帧 | `F, image_path, L` | `frame_index=1, x=0, y=0` |

`sheet_type` 支持 `horizontal`、`vertical`、`rows`、`columns`、`packed`；`data_format` 支持 `json-array` / `json-hash`。

## 13. CLI：分析与检查，3 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `render_onion_skin` | 将当前帧和相邻帧的半透明残影合成为 PNG | `F, I, output_filename` | `before=1, after=1, scale=4, ghost_opacity=100` |
| `compare_frames` | 比较两帧，返回变化像素数量、比例和包围框 | `F, frame_a, frame_b` | 无 |
| `get_color_stats` | 统计帧中的颜色数量及使用频率 | `F` | `frame_index=1, top=16` |

## 14. CLI：动画质量与修复，4 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `ensure_layers_present` | 确保指定图层在帧区间中存在 Cel | `F, layer_names` | `start_frame=1, end_frame=null` |
| `validate_scene` | 检查必需图层及 Cel，返回缺失项 | `F, required_layers` | `start_frame=1, end_frame=null` |
| `audit_animation` | 检查图层重叠、超出允许帧区间的活动等 | `F` | 见下 |
| `animation_sanitize` | 检查动画一致性，并可执行修复 | `F` | 见下 |

`audit_animation` 的可选参数：

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

`animation_sanitize` 的可选参数：

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

相关数组格式：

```json
{
  "overlap_pairs": ["人物,背景", "左手:身体"],
  "layer_frame_ranges": ["人物:1-8,17-24", "云:1-12"],
  "layer_order": ["背景", "人物", "前景"]
}
```

`out_of_range_action` 支持 `set_opacity_zero`、`delete_cels`、`none`。仅检查时将 `report_only` 设为 `true`。这些工具的 `end_frame=null` 表示处理到最后一帧。

## 15. CLI：切片，5 个

切片用于标记游戏引擎可使用的区域、九宫格中心和轴心。

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `create_slice` | 创建命名切片 | `F, name, B` | 无 |
| `set_slice_center` | 设置九宫格可拉伸中心区域 | `F, name, B` | 无 |
| `set_slice_pivot` | 设置切片轴心 | `F, name, x, y` | 无 |
| `list_slices` | 列出切片及其边界、中心和轴心 | `F` | 无 |
| `delete_slice` | 删除切片 | `F, name` | 无 |

中心和轴心的坐标相对于切片原点。

## 16. CLI：Tilemap，5 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `create_tilemap_layer` | 创建带独立 Tileset 的 Tilemap 图层 | `F, L, tile_width, tile_height` | 无 |
| `draw_on_tile` | 修改某个 Tile 的像素，必要时追加 Tile | `F, L, tile_index, pixels` | 无 |
| `set_tiles` | 按网格位置放置 Tile | `F, L, I, tiles` | 无 |
| `get_tile_at` | 读取网格位置上的 Tile 编号 | `F, L, I, col, row` | 无 |
| `get_tilemap_info` | 读取 Tile 尺寸、数量及地图尺寸 | `F, L` | 无 |

`tiles` 格式：

```json
[
  {"col": 0, "row": 0, "tile_index": 1},
  {"col": 1, "row": 0, "tile_index": 2}
]
```

`col/row` 从 0 开始；Tile 编号 `0` 表示空格，第一个实际 Tile 是 `1`。`draw_on_tile` 的像素坐标相对于 Tile 左上角，`pixels` 仍使用 `[{"x":0,"y":0,"color":"#FF0000"}]` 格式。

## 17. CLI/辅助：文字，3 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `list_text_fonts` | 列出可用字体 | 无 | 无 |
| `measure_text` | 测量文字尺寸，不绘制 | `text, font` | `size=1, letter_spacing=0, bold=0, antialias=false` |
| `draw_text` | 将文字绘制到精灵，可加描边和阴影 | `F, text, x, y, font` | 见下 |

`draw_text` 的可选参数：

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

`font` 可使用字体列表中的名称或字体路径。TrueType 字体的 `size` 为像素字号；位图字体的 `size` 为整数放大倍数。`anchor` 表示文字的哪个位置对齐到 `(x,y)`，支持：

```text
topleft, top, topright,
left, center, right,
bottomleft, bottom, bottomright,
baselineleft, baseline, baselineright
```

## 18. CLI：跨文件复制，1 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `copy_layers_between_sprites` | 将源文件的指定图层复制到目标文件 | `source_filename, target_filename, layer_names` | `replace=true, create_missing_frames=true` |

## 19. 辅助：HTTP 预览，2 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `start_preview_server` | 启动 HTTP 服务，浏览已导出的图片目录 | `directory` | `port=8000` |
| `stop_preview_server` | 停止指定端口的预览服务 | 无 | `port=8000` |

这里的 HTTP 预览用于浏览导出文件，与实时 `get_preview` 是不同入口。

## 20. 辅助：动画指南，1 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `animation_workflow_guide` | 返回英文动画工作流建议 | 无 | `use_case="character"` |

## 21. CLI：统一协议入口，1 个

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `cli_execute` | 用协议 v1 读取磁盘文件或执行原子绘图批次 | `request` 对象 | 由内部请求字段决定 |

`request` 内部结构：

| 字段 | 是否必填 | 含义 |
|---|---|---|
| `request_id` | 是 | 请求唯一标识 |
| `target` | 是 | `{"backend":"cli","path":"已有文件的绝对路径"}` |
| `action` | 是 | `get_document_info` 或 `apply_operations` |
| `protocol_version` | 否 | 默认 `1` |
| `expected_file_revision` | 否 | 上次读取返回的文件 SHA-256，用于检查外部修改 |

读取示例：

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

批量编辑时，`action` 使用：

```json
{
  "name": "apply_operations",
  "operations": [
    {"op": "create_layer", "ref": "paint", "name": "绘制层"},
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

当前 `cli_execute` 只支持读取和前述四种基础绘图操作，不支持 `apply_animation`；CLI 目标不使用实时的 `expected_revision` / `expected_context`。

## 22. 默认关闭：任意 Lua 工具

| 工具 | 用途 | 必填参数 | 可选参数 |
|---|---|---|---|
| `run_lua_script` | 在 Aseprite CLI 中执行 Lua 源码 | `script` | `filename=""` |

需要在 `cli` / `all` 配置下显式设置 `ASEPRITE_MCP_ENABLE_RAW_LUA=1`。当前聊天未暴露，所以未计入上述 126 个工具。提供 `filename` 时先打开该文件；脚本的修改需要自行调用保存，输出通过 `print()` 返回。脚本具有 Lua 的文件与系统访问能力。

## 常用调用流程与源码

当前画布上的创作通常使用：

```text
get_connection_status
→ list_documents
→ get_document_info
→ apply_operations / apply_animation
→ get_preview
→ 需要保存时调用 save_sprite
```

调色板、滤镜、补间、Tilemap 等当前主要通过 CLI 文件工具提供；CLI 的修改不会进入当前 GUI 内存文档的撤销历史。工具清单表示已注册接口，不代表所有平台和版本均已验证。

源码位置：

- [实时与 CLI 工具注册](../aseprite_mcp/server.py)
- [协议与批量操作参数定义](../aseprite_mcp/core/protocol.py)
- [CLI 统一后端](../aseprite_mcp/backends/cli.py)
- [CLI/辅助工具实现](../aseprite_mcp/tools/)
