# 环境与参考资料

记录日期：2026-10-21。用途：区分本地环境事实、官方能力说明和待导入的上游实现，供开发和兼容验收按需查阅。

## 本地环境事实

| 项目 | 已知状态 | 证据与限制 |
|---|---|---|
| 工作目录 | `E:\CodexProject\aseprite-mcp` | 文档交付前只有本地 `Aseprite/` 软件目录 |
| Aseprite 程序 | `E:\CodexProject\aseprite-mcp\Aseprite\Aseprite.exe` | 仅本机环境说明，不作为通用配置默认值 |
| Aseprite 版本 | 1.3.7，API 28 | 2026-10-20 探索性 CLI/Lua 验证；不代替产品阶段验收 |
| 默认 Python | 3.12.4 | 不满足要求；项目 `uv run --locked python --version` 为 **3.13.15** |
| uv | 0.12.3 | 开发验收已执行；依赖及解释器由 uv 管理 |
| 项目源码 | P0-M1 已导入固定 SHA | Python 双后端服务、Lua 扩展和真实 MCP 图片闭环已在 P1 验收 |
| Git | 已初始化本地仓库，分支 `main` | 2026-10-21 用户单独授权初始化并提交一次 P0 基线；无远程设置或推送 |

2026-10-20 的探索验证发现 `WebSocket`、`Timer`、`json` 可用，并完成临时画布像素编辑、撤销、重做及 PNG 导出；当时仅使用临时脚本，未形成项目测试和持久验收证据。该探索记录不作为产品验收；2026-10-21 的完整 MCP → 扩展 → 当前编辑器链路另由 P1 正式验证。

开发环境由 P0-M1 建立 Python 3.13+ 和 `uv` 依赖管理。运行时通过 `ASEPRITE_PATH` 指定程序；环境示例使用用户自选安装路径，不把上述本机绝对路径写进代码或发布配置。软件和个人数据不随项目分发。

## 官方资料

| 资料 | 用途 |
|---|---|
| [API 总览](https://www.aseprite.org/api/) | Lua 能力入口；这是内嵌脚本 API，不是 HTTP 服务 |
| [插件机制](https://www.aseprite.org/api/plugin) | `package.json`、生命周期、菜单命令和扩展打包 |
| [WebSocket](https://www.aseprite.org/api/websocket) | Aseprite 主动连接外部服务、接收及发送消息 |
| [JSON](https://www.aseprite.org/api/json) | Lua 和桥接消息之间的编解码 |
| [app](https://www.aseprite.org/api/app) | 事务、撤销、重做、活动状态与事件 |
| [Image](https://www.aseprite.org/api/image) | 图像复制、像素访问、合成与导出 |
| [API 版本变化](https://www.aseprite.org/api/Changes) | 对照安装版本确认能力，避免直接套用新版接口 |
| [命令行](https://www.aseprite.org/docs/cli/) | `--batch`、`--script` 和文件导出 |

版本注意：本地 v1.3.7 的 WebSocket 回调与最新文档存在参数差异；部分新版命令参数也不可直接假定可用。兼容判定同时参考 `app.version`、`app.apiVersion` 和实际能力探测。实时回调在 UI 线程执行，大任务须限制单次工作量。

## 上游来源与复用边界

| 项目 | 记录 |
|---|---|
| 参考仓库 | [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp) |
| 已研究快照 | [`90d1696a7e41edff89bbd0823ae6a5f86c114bcc`](https://github.com/diivi/aseprite-mcp/tree/90d1696a7e41edff89bbd0823ae6a5f86c114bcc) |
| 实际导入快照 | `90d1696a7e41edff89bbd0823ae6a5f86c114bcc`；[来源及摘要](THIRD_PARTY.md) |
| 许可 | 研究时为 MIT；正式导入时核对原文、保留原始版权及许可声明 |
| 计划复用 | Python MCP 工具、Lua 算法、文本与图像处理、真实 Aseprite 测试 |
| 需要改造 | 文件加载和保存耦合、执行抽象、预览返回方式、实时状态及撤销适配 |

研究快照通过 `--batch` 操作磁盘文件，不代表能访问另一个编辑器进程的未保存内容。按源码装饰器静态计数有 116 个工具，README 当时标注 104 个；工具数量只说明该快照，不作为本项目首版能力承诺。

P0-M1 默认复核并以该研究快照建立可复现基线；若无法取得或必须更换，记录原因和差异后更新受影响计划，不悄悄改用浮动分支。未来升级另记实际提交、变更范围、许可及测试结果。

项目拟采用 MIT，但该决定不授权重新分发 Aseprite 软件，也不意味着其他第三方资源自动采用同一许可。正式归属记录由 P0-M1 建立，发布前复核。

## P0 实际环境复核（2026-10-21）

Windows，本地程序路径仍见上表；`--version` 返回 `Aseprite 1.3.7-x64`。uv 0.12.3，项目隔离解释器 CPython 3.13.15。`uv sync --locked --python 3.13` 通过；锁定 MCP 1.6.0、Pydantic 2.11.2、Pillow 12.3.0、pytest 9.0.3。开发配置见[测试说明](TESTING.md)。TLS Schannel 下载失败后使用 Python urllib 获取同一固定提交，未更换上游版本。Python 全局链接/注册表写入受限，但隔离解释器可正常运行。

P0-M2 复核：真实公共 CLI 路径返回 `api_version=28`、软件 1.3.7；最终完整回归 173 passed（43.56s）。内部协议和握手为类型/模拟验收，实时 WebSocket 尚未连接，详见 [M2 交接](progress/P0-M2.md)。

## P1 实际环境复核（2026-10-21）

Python 3.13.15、MCP SDK 1.6.0、websockets 15.0.1、真实 Aseprite 1.3.7 / API 28。最终全量回归 179 passed（52.62s），实时内存文档/事务/撤销/PNG 及 CLI 均通过。客户端采用 Python MCP SDK 1.6.0 与接收图片的 HTML 视图，Edge 155.0.4283.62 实际显示四图。版本与测试分类见 [P1-M3](progress/P1-M3.md)，其他平台未验证。

## P2 实际环境复核（2026-10-21）

Windows NT 10.0.26200.0、uv 0.12.3、Python 3.13.15、MCP SDK 1.6.0、Aseprite 1.3.7/API 28；191 项回归通过。独立 uv 环境从 wheel 安装，扩展 ZIP 解压到隔离配置，双 stdio 启动入口及真实图片闭环通过；Edge 155.0.4283.62 显示核验。0.1.0/协议 v1 首版候选已验收未发布，详见 [P2-M2](progress/P2-M2.md)。本机软件路径仍仅见本文件前表。
