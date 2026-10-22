# Aseprite MCP

通过 MCP 让 AI 在 Aseprite 中读取画布、编辑像素并查看结果，支持人与 AI 在同一个文档中继续创作。

项目基于 [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp) 改造：复用其 Python 工具和测试，增加 Lua 扩展实时后端，同时保留 CLI 文件批处理能力。

## 当前状态

**P2 已验收：实时核心、故障恢复、服务/扩展打包及 Windows 隔离安装通过；197 项回归通过。0.3.0 无文件直连候选已验收、尚未发布。**

已验证闭环：连接当前编辑器 → 读取未保存文档 → 批量编辑 → 直接返回预览 → 撤销与重做。本地候选包含 Python 服务和 Lua 扩展；当前以 Windows + Aseprite 1.3.7 / API 28 验收，macOS、Linux 待验证；高级动画、调色板、特效和 Tilemap 在后续阶段逐步迁移。

## 从这里开始

| 需要了解的内容 | 入口 |
|---|---|
| 当前任务和开发路线 | [开发执行计划](EXECUTION_PLAN.md) |
| 实际目录及各模块做什么 | [动态项目结构](docs/PROJECT_STRUCTURE.md) |
| 软件位置、官方 API 和参考项目 | [环境与参考资料](docs/REFERENCES.md) |
| 架构及接口边界 | [架构说明](docs/development/ARCHITECTURE.md) |
| 开发、验收与交接方式 | [执行约定](docs/development/README.md) |
| 开发者及 AI 维护规则 | [AGENTS.md](AGENTS.md) |

## 安装与运行

先按[Windows 安装说明](docs/INSTALL.md)安装服务 wheel、锁定依赖和 `.aseprite-extension`，配置一次 stdio MCP 客户端后，打开两边即可自动连接，默认 127.0.0.1:8765；不创建、不读取连接 JSON，也没有选文件入口。自定义端口使用 `--port`，扩展设置中填相同端口。默认 9 个实时入口，不隐式保存；保存、覆盖和撤销规则见安装说明。实时断线不会切换到磁盘 CLI。

[故障排查](docs/TROUBLESHOOTING.md) · [测试与隔离验收](docs/TESTING.md) · [候选构建/发布边界](docs/RELEASING.md) · [贡献](CONTRIBUTING.md)。源码开发仍使用 Python 3.13+、`uv sync --locked` 和 `uv run --locked aseprite-mcp`；磁盘工具通过 cli/all 配置启用，高级旧工具不是实时能力。

Aseprite 软件需由使用者自行准备，不随项目分发。版本基线及本机位置见[环境与参考资料](docs/REFERENCES.md#本地环境事实)。

## 来源与许可

保留上游 MIT 许可及原始版权，见 [LICENSE](LICENSE) 和 [来源记录](docs/THIRD_PARTY.md)。新增代码同样采用 MIT，Aseprite 软件不随项目分发。

项目仓库地址尚未建立；本文不将参考仓库当作本项目的安装地址或问题反馈入口。
