# Aseprite MCP · 开发执行计划

读取顺序：本文件 → [执行约定](docs/development/README.md) → 当前模块提示词 → 本阶段总结与必要前置交接。

`- [x]`：已实现且验收通过；`- [ ]`：未完成或未验收。默认按阶段与模块顺序，每次处理一个模块。

模块结束：按[交接模板](docs/development/MODULE_REPORT_TEMPLATE.md)生成 `docs/progress/<模块编号>.md`，同步阶段总结与本文件；涉及结构变化时同步[项目结构](docs/PROJECT_STRUCTURE.md)。已验收开发模块默认本地提交，不推送。阶段结束另做集成验收。

当前任务：P2（含用户追加 P2-M3）全部已验收；下一入口 [P3-M1 · 上游工具兼容清单](docs/development/prompts/P3-高级能力迁移.md#p3-m1)，尚未开始。

## P0 · 项目基础

提示词：[P0](docs/development/prompts/P0-项目基础.md)。总结：固定上游、Python 3.13.15、双后端契约及真实 CLI 集成已验收，173 项测试通过；[完整总结](docs/progress/P0.md)。

- [x] [P0-M1 · 上游导入与环境](docs/development/prompts/P0-项目基础.md#p0-m1)
- [x] [P0-M2 · 双后端边界及接口约定](docs/development/prompts/P0-项目基础.md#p0-m2)

## P1 · 实时核心闭环

提示词：[P1](docs/development/prompts/P1-实时核心闭环.md)。总结：实时连接、未保存文档编辑、PNG 图片反馈及撤销/重做已真实验收，179 项全量回归通过；[完整总结](docs/progress/P1.md)。

- [x] [P1-M1 · 扩展连接](docs/development/prompts/P1-实时核心闭环.md#p1-m1)
- [x] [P1-M2 · 文档及事务编辑](docs/development/prompts/P1-实时核心闭环.md#p1-m2)
- [x] [P1-M3 · 图片预览与集成](docs/development/prompts/P1-实时核心闭环.md#p1-m3)

## P2 · 稳定性与首版发布

提示词：[P2](docs/development/prompts/P2-稳定性与首版发布.md)。总结：可靠性、自动连接、固定端口及 Windows 隔离安装/真实客户端集成已验收，197 项全量回归通过；[完整总结](docs/progress/P2.md)。

- [x] [P2-M1 · 错误与状态管理](docs/development/prompts/P2-稳定性与首版发布.md#p2-m1)
- [x] [P2-M2 · 安装打包及发布验收](docs/development/prompts/P2-稳定性与首版发布.md#p2-m2)
- [x] [P2-M3 · 自动连接与固定端口](docs/development/prompts/P2-稳定性与首版发布.md#p2-m3)

## P3 · 高级能力迁移

提示词：[P3](docs/development/prompts/P3-高级能力迁移.md)。总结：尚未建立高级工具兼容清单，P2 首发验收后先执行 P3-M1；[完整总结](docs/progress/P3.md)。

- [ ] [P3-M1 · 上游工具兼容清单](docs/development/prompts/P3-高级能力迁移.md#p3-m1)
- [ ] [P3-M2 · 按能力组迁移与回归](docs/development/prompts/P3-高级能力迁移.md#p3-m2)

首发交付点：P2。后续演进：P3 按复核后的能力清单分批迁移。P0/P1/P2 已验收，0.2.0 自动连接候选已验收但尚未发布；P0 基线已按用户授权初始化并入库，P1/P2 按模块本地提交；未进行软件分发或 GitHub 推送；首版不要求全部上游工具实时可用，也不承诺未验收平台。
