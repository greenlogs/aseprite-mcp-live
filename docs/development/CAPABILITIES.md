# 高级能力兼容与冻结批次

2026-10-22 复核。完整逐工具矩阵：[tool-compatibility.json](tool-compatibility.json)，包含全部 116 项的工具名、源码位置、CLI 注册、实时可行性、最低 API 证据、活动状态、保存/撤销、测试和许可。`python scripts/check_capabilities.py` 对照实际 AST 和 MCP 注册，防止漏记；矩阵的未来候选不表示已支持。

## 上游与版本证据

导入仍为 `90d1696a7e41edff89bbd0823ae6a5f86c114bcc`，116 项；GitHub HEAD API 实查为 [`a89b205bed31930ee141edf319e78c71ef16bba6`](https://github.com/diivi/aseprite-mcp/tree/a89b205bed31930ee141edf319e78c71ef16bba6)，提交时间 2026-10-21T23:55:48Z，固定归档 SHA256 `e55499e1a8c7d82ea09a0e9e642f73c6d120eb3a7054b55a06921d366ecbb5b7`。实际源码装饰器为 123 项，无删除/更名，新增 draw_rows/read_rows/draw_iso_box/view_sprite/export_animation/get_bounds/lint_sprite。两份 LICENSE 均为 MIT、原版权保留；没有升级或复制新工具。另对固定基线/新快照函数AST作差异，既有 animation_workflow_guide、compare_frames、export_frame、outline_cel、run_lua_script 有变更，未合并；细目在矩阵 upstream_review.changed_existing_tools。复核不以 README 工具数代替源码。

已验证最低产品基线为 Aseprite 1.3.7/API28；未调查更早版本，矩阵不捏造历史最低 API。官方 [Sprite](https://www.aseprite.org/api/sprite)、[Frame](https://www.aseprite.org/api/frame)、[Tag](https://www.aseprite.org/api/tag)、[版本变化](https://www.aseprite.org/api/Changes) 用于定位，真实 API28 测试与运行时探测决定是否支持。

## 能力组抽查与迁移判断

全部上游工具运行于独立 CLI 进程，activeSprite 是磁盘加载对象。其 app.transaction 不会成为用户编辑器的撤销历史；含 saveAs 的算法须移除自动保存。逐工具 tests 列表示已有测试引用，空列表表示无专门覆盖；CLI 最终回归和真实实时验证另记模块报告。

| 组 / 源码 | 数量 | 抽查与副作用 | 决策 |
|---|---:|---|---|
| [动画](../../aseprite_mcp/tools/animation.py) | 24 | add_frames/newFrame、set_tag/newTag，事务后 saveAs；按名称查层；test_animation.py | 帧/时长/标签重写为显式文档事务，补间/Cel 后续解耦 |
| [画布](../../aseprite_mcp/tools/canvas.py) | 7 | set_frame_duration 使用活动帧并保存；test_animation.py 间接覆盖 | 选定帧时长纳入，切换活动状态工具不照搬 |
| [调色板](../../aseprite_mcp/tools/palette.py) | 8 | set_palette 改 palette 并保存，索引模式需重映射；test_palette.py | 后续独立批次，当前无实时支持 |
| [算法特效](../../aseprite_mcp/tools/fx.py) / [原生特效](../../aseprite_mcp/tools/native_fx.py) | 5 / 7 | outline_cel 图像复制/saveAs；outline_native 依赖活动层/选择/命令；test_fx.py/test_native_fx.py | 算法解耦、命令重写，当前无实时支持 |
| [Tilemap](../../aseprite_mcp/tools/tilemap.py) | 5 | set_tiles 改 tile 图像并保存，tile 位域/tileset 依赖；test_tilemap.py | 后置，不能走普通 RGB Cel 编辑 |
| [绘制](../../aseprite_mcp/tools/drawing.py) | 14 | draw_pixels_at 显式帧但名称查层/saveAs；test_drawing.py | 核心已有 pixel/rectangle，其他候选解耦 |
| [图层](../../aseprite_mcp/tools/layers.py) / [变换](../../aseprite_mcp/tools/transform.py) | 7 / 4 | merge_layer_down/rotate_layer 影响层/Cel、保存；test_layers.py | 后续解耦，不能默认迁移锁层/组行为 |
| [读取](../../aseprite_mcp/tools/pixel_read.py) / [分析](../../aseprite_mcp/tools/analysis.py) | 4 / 3 | get_composite_rect/compare_frames 读磁盘、JSON/图像输出；test_composite_read.py/test_analysis.py | 可复用合成算法，须改内存/图片返回边界 |
| [导出](../../aseprite_mcp/tools/export.py) / [跨文档](../../aseprite_mcp/tools/scene.py) | 7 / 1 | export_tag 写导出文件；copy_layers_between_sprites 双文件保存；test_export.py | 文件授权和双目标单列，不放动画事务 |
| [选择](../../aseprite_mcp/tools/selection.py) / [切片](../../aseprite_mcp/tools/slices.py) | 4 / 5 | move_region/delete_slice 修改并保存；test_selection.py/test_slices.py | 后续解耦，选择需要上下文保护 |
| [文字](../../aseprite_mcp/tools/text.py) / [质量](../../aseprite_mcp/tools/quality.py) | 3 / 4 | draw_text 依赖字体/保存；audit_animation 读取，sanitize 可改写；test_text.py | 字体来源和修改规则先评估 |
| [指南](../../aseprite_mcp/tools/guide.py) / [HTTP预览](../../aseprite_mcp/tools/preview.py) / [Lua](../../aseprite_mcp/tools/script.py) | 1 / 2 / 1 | guide 纯文本；preview 起本地进程；Lua 任意副作用 | 不迁移为实时编辑，Lua 保持 CLI 显式开关 |

## P3-M2 冻结范围与可执行契约

本阶段只纳入基础动画一批；范围有限但包含正常、失败、回滚、历史、预览、CLI 与核心组合验收。后续调色板、特效、Tilemap、补间不属于本阶段，也不预先创建未实现模块或勾选。

- 显式设置 `ASEPRITE_MCP_CAPABILITY_SETS=animation` 才注册 `apply_animation`；默认 core 9 项不变，cli/all 旧工具名及文件语义不变。握手另协商 apply_animation；未协商返回 UNSUPPORTED_CAPABILITY，不降级。
- 输入沿用 session_id/document_id/expected_revision/可选 expected_context/request_id；operations 为非空有界数组。帧号从 1 开始、时长整数毫秒 1–65535；标签名非空且唯一，按精确名称定位，遇到文档中重复同名标签拒绝。
- `add_frames(count,duration_ms=100)`：在末尾逐帧复制最后一帧，最多总计 256 帧；`delete_frame(frame)`：不得删唯一帧；`set_frame_duration(from_frame,to_frame,duration_ms)`：闭区间；`set_tag(tag,from_frame,to_frame,direction)` 创建或更新，四种正向/反向/乒乓方向；`delete_tag(tag)` 缺失拒绝。
- 操作按顺序解释，先模拟所有帧数/标签范围再执行；帧变化后的标签重排沿用原生 Aseprite；原生删帧导致后续标签操作失效时整批回滚。整批一个事务、失败回滚、CPU/复制像素预算保护；RGB 普通可编辑层为首批边界，组内普通层允许，锁层/背景/参考/Tilemap/非RGB拒绝。缺 Cel 保持空，偏移与关联 Cel 使用原生 newFrame/deleteFrame 行为；真实测试须检查独立历史与原像素。
- get_document_info 增补 tags 与整数 frame_durations_ms，原 frame_durations 秒保留。输出 operations 数和刷新后的动画元数据；不自动保存、不改变用户选择的其他文档。CLI 继续走原工具，公共 cli_execute 不支持 apply_animation。
- 正常效果、每种错误、整批无部分写入、一次撤销/重做、各帧 PNG、显式保存后 CLI 读回、未启用与协商不支持、超时 RESULT_UNKNOWN、核心编辑组合都须验证。真实 GUI 使用独立配置/进程，不触碰个人编辑器；模拟测试单列。

接口为协议 v1 的可选增量，核心字段/帧号不变。服务和扩展配套版本为 0.4.0，旧配套因版本校验明确拒绝；最低软件版本保持 API28。基础动画已在Windows Aseprite1.3.7/API28真实验收，208项完整回归通过；实现及验收事实见 [P3-M2交接](../progress/P3-M2.md)。
