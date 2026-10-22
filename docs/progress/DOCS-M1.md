# DOCS-M1 · 中英 README 整理

## 状态

- 更新日期：2026-10-22。
- 状态：已通过文档验收。
- 前置：[P3 总结](P3.md)及[P3-M2 交接](P3-M2.md)，均已验收。
- 根计划：文档检查通过，已勾选。

## 实际完成了什么

按用户要求参考 [MCP for Blender README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md) 的居中标题、简介、快速开始、功能表格、组件、自然语言示例、故障排查及许可组织方式，重写根 README.md 为中文入口，新增 README.en.md 为独立英文入口，互相提供语言切换。未复制参考项目的安装命令、赞助、社区、下载或功能声明。

两种语言均说明已验收的实时核心、显式可选动画、CLI 文件边界、Windows/API28 验证范围及 0.4.0 候选未发布状态。JSON 示例采用通用 mcpServers 格式与占位路径，完整安装等细节链接到现有中文文档。208 项测试引用原 P3 验收，不表示本轮重新运行。

pyproject.toml 的源码分发清单增加 README.en.md，避免源码包缺少语言切换目标。

## 验收证据

环境：Windows PowerShell，复用项目现有 .venv Python，不安装依赖。

| 验收项 | 实际命令或步骤 | 结果 |
|---|---|---|
| 参考风格 | 首次 PowerShell/系统 curl 获取参考失败；改用项目 Python 的标准库 urllib.request 读取用户指定仓库的 raw README | 成功读取；按实际结构改写，不执行远程内容 |
| 本地链接与索引 | `.venv/Scripts/python.exe -B scripts/check_docs.py` | `Checked 38 Markdown files, entry point and module index` |
| 示例与结构 | PowerShell here-string 管道传入项目 Python：标准库 re 提取两版 json 围栏并用 json.loads 解析；核对标题层级、围栏数与 details/div 配对 | 两版各 2 个 JSON 示例有效；14 个标题层级对应，示例内容一致，HTML 块及围栏配对 |
| 文档分发配置 | 同一标准库脚本用 tomllib 读取 pyproject.toml，断言 sdist.include 包含 `/README.en.md` | 通过，仅配置检查，未构建源码包 |
| 差异空白 | `git diff --check` | 通过，退出码 0 |

证据为本次命令输出与本报告；未产生验收临时文件。

本轮只维护文档与文档打包清单：模拟测试、真实 Aseprite 测试、实际客户端显示及构建安装均未执行；未安装依赖、启动产品或导入产品包。

## 接口与兼容变化

公共工具、协议、依赖、版本和运行入口无变化；源码分发清单只增加英文文档。

## 结构变化及同步情况

- 新增根 README.en.md、本文档交接与 DOCS.md 维护总结。
- PROJECT_STRUCTURE.md 同步中英入口职责、维护报告和文档分发清单变化，复核日期为 2026-10-22；保留已有工作区清理记录。
- EXECUTION_PLAN.md 增加文档维护状态；P0～P3 产品阶段验收不变。
- 架构与开发提示词无公共接口变动，无需修改。

## 遗留与阻塞

文档验收无阻塞。尚无本项目远程地址，未编造克隆地址、Release、PyPI 安装、下载或 Issue 链接；扩展安装使用本地构建路径。其他平台和版本保持未验收声明。

## 下一模块该做什么

没有新产品模块。仓库地址和发布方式确定后，核对实际地址再更新中英 README 的源码获取与下载入口；在此之前沿用现有源码构建步骤。能力开发继续从[兼容清单](../development/CAPABILITIES.md)和[P3 提示词](../development/prompts/P3-高级能力迁移.md)评估下一独立范围。

## 状态同步与提交

- [x] 维护总结和根计划与实际文档检查状态一致。
- [x] 已同步结构文档和源码文档分发清单。
- 产品阶段集成验收不适用：本轮为独立文档维护。
- 本地 Git：本轮为文档维护，未提交、未推送。开始时 .gitignore、EXECUTION_PLAN.md、PROJECT_STRUCTURE.md 和 P0 总结已有修改；保留这些修改，不混入文档提交。
