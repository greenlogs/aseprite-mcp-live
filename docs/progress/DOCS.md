# 文档维护总结

本维护批次独立于已验收的 P0～P3 产品阶段，不新增产品能力。

| 模块 | 状态 | 交接 |
|---|---|---|
| DOCS-M1 · 中英 README 整理 | 已通过文档验收 | [DOCS-M1](DOCS-M1.md) |
| DOCS-M2 · PyPI 与 Release 使用入口 | 已通过文档验收 | [DOCS-M2](DOCS-M2.md) |
| DOCS-M3 · 按中文版同步英文 README | 已通过文档验收 | [DOCS-M3](DOCS-M3.md) |

2026-10-22 DOCS-M3：按用户调整后的中文版同步英文，包含快速开始、五图、all + animation 和路径占位符。15 个标题层级、13 个代码块对应，4 个 JSON 示例和全部 PowerShell 命令一致（路径说明占位符正常翻译）；44 份 Markdown 内链与差异检查通过，中文 README 摘要未变化。

2026-10-22：参考用户指定的 MCP for Blender README 组织方式，整理中文入口并新增独立英文入口，保留能力与验证范围。38 份 Markdown 本地链接、入口和模块索引检查通过；两版各 2 个 JSON 示例有效、14 个标题层级对应，围栏与 HTML 块配对；git diff --check 通过。详细文档继续使用中文，本轮未重跑产品测试。

2026-10-22 DOCS-M2：用户已发布正式 PyPI 和扩展 Release；公开 PyPI JSON 确认 0.4.1。中英 README 增加 Windows uv 安装、uvx 和本地构建，使用实际 origin 对应的 Release 入口；不再引用内部 docs、开发计划或提示词。两版各 4 个 JSON 示例和 14 个标题层级一致，内链与差异检查通过。Release 匿名访问 404，未核实具体附件，未编造附件直链；本轮没有安装依赖、构建或产品测试。
