# Aseprite MCP · 开发执行计划

读取顺序：本文件 → [执行约定](docs/development/README.md) → 当前模块提示词 → 本阶段总结与必要前置交接。

`- [x]`：已实现且验收通过；`- [ ]`：未完成或未验收。默认按阶段与模块顺序，每次处理一个模块。

模块结束：按[交接模板](docs/development/MODULE_REPORT_TEMPLATE.md)生成 `docs/progress/<模块编号>.md`，同步阶段总结与本文件；涉及结构变化时同步[项目结构](docs/PROJECT_STRUCTURE.md)。已验收开发模块默认本地提交，不推送。阶段结束另做集成验收。

当前任务：[P1-M3 · 图片预览与集成](docs/development/prompts/P1-实时核心闭环.md#p1-m3)。前置：P1-M2 已验收。

## P0 · 项目基础

提示词：[P0](docs/development/prompts/P0-项目基础.md)。总结：固定上游、Python 3.13.15、双后端契约及真实 CLI 集成已验收，173 项测试通过；[完整总结](docs/progress/P0.md)。

- [x] [P0-M1 · 上游导入与环境](docs/development/prompts/P0-项目基础.md#p0-m1)
- [x] [P0-M2 · 双后端边界及接口约定](docs/development/prompts/P0-项目基础.md#p0-m2)

## P1 · 实时核心闭环

提示词：[P1](docs/development/prompts/P1-实时核心闭环.md)。总结：实时连接、文档与事务编辑已验收，39 项专项通过，下一模块 P1-M3；[完整总结](docs/progress/P1.md)。

- [x] [P1-M1 · 扩展连接](docs/development/prompts/P1-实时核心闭环.md#p1-m1)
- [x] [P1-M2 · 文档及事务编辑](docs/development/prompts/P1-实时核心闭环.md#p1-m2)
- [ ] [P1-M3 · 图片预览与集成](docs/development/prompts/P1-实时核心闭环.md#p1-m3)

## P2 · 稳定性与首版发布

提示词：[P2](docs/development/prompts/P2-稳定性与首版发布.md)。总结：尚未进行可靠性加固及安装发布验收，等待 P1 集成验收；[完整总结](docs/progress/P2.md)。

- [ ] [P2-M1 · 错误与状态管理](docs/development/prompts/P2-稳定性与首版发布.md#p2-m1)
- [ ] [P2-M2 · 安装打包及发布验收](docs/development/prompts/P2-稳定性与首版发布.md#p2-m2)

## P3 · 高级能力迁移

提示词：[P3](docs/development/prompts/P3-高级能力迁移.md)。总结：尚未建立高级工具兼容清单，P2 首发验收后先执行 P3-M1；[完整总结](docs/progress/P3.md)。

- [ ] [P3-M1 · 上游工具兼容清单](docs/development/prompts/P3-高级能力迁移.md#p3-m1)
- [ ] [P3-M2 · 按能力组迁移与回归](docs/development/prompts/P3-高级能力迁移.md#p3-m2)

首发交付点：P2。后续演进：P3 按复核后的能力清单分批迁移。P0 开发已完成，后续按用户单独授权初始化 Git 并将 P0 基线纳入一次首次本地提交；未进行软件分发或 GitHub 推送；首版不要求全部上游工具实时可用，也不承诺未验收平台。
