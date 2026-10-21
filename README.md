# Aseprite MCP

通过 MCP 让 AI 在 Aseprite 中读取画布、编辑像素并查看结果，支持人与 AI 在同一个文档中继续创作。

项目计划基于 [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp) 改造：复用其 Python 工具和测试，增加 Lua 扩展实时后端，同时保留 CLI 文件批处理能力。

## 当前状态

**P1 开发中：真实 Aseprite 扩展连接已验收；文档编辑及预览正在实施。**

首个可发布版本的目标：连接当前编辑器 → 读取未保存文档 → 批量编辑 → 直接返回预览 → 撤销与重做。该版本以 Windows 为首个验收平台，macOS、Linux 待验证；高级动画、调色板、特效和 Tilemap 在后续阶段逐步迁移。

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

开发环境可用：Python 3.13+ 和 uv，设置 `ASEPRITE_PATH` 后执行 `uv sync --locked`，以 `uv run --locked python -m aseprite_mcp` 启动 stdio 服务。具体配置、测试分层见 [测试说明](docs/TESTING.md)。默认暴露实时核心入口，扩展连接设置见测试说明；使用磁盘工具需配置 `ASEPRITE_MCP_TOOL_PROFILE=cli`。正式安装与发布验收在 P2。

Aseprite 软件需由使用者自行准备，不随项目分发。版本基线及本机位置见[环境与参考资料](docs/REFERENCES.md#本地环境事实)。

## 来源与许可

保留上游 MIT 许可及原始版权，见 [LICENSE](LICENSE) 和 [来源记录](docs/THIRD_PARTY.md)。新增代码同样采用 MIT，Aseprite 软件不随项目分发。

项目仓库地址尚未建立；本文不将参考仓库当作本项目的安装地址或问题反馈入口。
