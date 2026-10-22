# DOCS-M2 · PyPI 与 Release 使用入口

## 状态

- 日期：2026-10-22；已通过文档验收。
- 前置：[DOCS-M1](DOCS-M1.md)、[PACK-M2](PACK-M2.md)及[PACK-M3](PACK-M3.md)。
- 用户当次说明：正式 PyPI 已发布，扩展已上传 Release；README 不得引用 docs/ 或内部执行计划、提示词，可按需使用根 assets/。
- 根计划和[维护总结](DOCS.md)已同步。

## 实际完成了什么

同步中文 README.md 与英文 README.en.md，提供 Windows 官方 PowerShell 安装脚本、WinGet、官方 uv Release 手动下载；补充 Python 3.13 管理步骤。

提供 `uvx --python 3.13 aseprite-mcp`、匹配扩展的 `aseprite-mcp==0.4.1` 固定版本及 MCP JSON 配置。另保留真实仓库克隆、本地锁定同步、build_release.py 打包、源码启动与 MCP 绝对目录配置。区分 stdio 等待与后台运行，说明由客户端启动、避免重复占用端口。

扩展安装改为 origin 对应的 GitHub Release 列表入口，要求服务/扩展版本一致；不编造标签或附件直链。README 全部移除 docs/、内部计划、开发提示词、贡献流程和自然语言提示示例，所需使用信息直接写在两版 README 中，无需新建 assets/。

更新 PyPI 徽章及包链接，去掉 TestPyPI 测试版和候选未发布的旧状态。继续说明已验证平台与实时/CLI 边界。

## 验收证据

环境：Windows PowerShell、现有项目 Python 3.13、现有 uv/uvx；仅使用标准库与只读命令。

| 检查 | 实际命令或步骤 | 结果 |
|---|---|---|
| 正式 PyPI | 项目 Python urllib.request 读取 `https://pypi.org/pypi/aseprite-mcp/json` | 公开元数据确认 name=aseprite-mcp、version=0.4.1、requires_python >=3.13 |
| 仓库入口 | `git remote -v` | origin 为 `git@github.com:greenlogs/aseprite-mcp-live.git`，据此生成网页、Release、Issue 与 HTTPS 克隆入口 |
| Release 核查 | urllib.request 读取 GitHub releases API 和网页 | 均为 HTTP 404；记录用户已发布事实，但未确认匿名可见性或具体附件 |
| uv 安装入口 | urllib.request 读取官方 install.ps1 | 重定向后 HTTP 403；未执行安装脚本。README 同时给出 WinGet、官方 Release 手动下载和官方安装文档 |
| uvx 语法 | `uvx --help`，静态核对本地 `__main__.py` 与 pyproject 入口 | uvx 为工具运行入口，包脚本为 aseprite-mcp；版本与扩展清单均为 0.4.1 |
| JSON 与中英一致性 | 标准库脚本提取两版 JSON 围栏，用 json.loads 解析；比较示例与标题层级，并核对围栏与 HTML 配对 | 各 4 个 JSON 示例有效、14 个标题层级一致；版本固定配置和源码启动配置核对通过 |
| 公开内容边界 | 同一脚本断言不存在 docs/、EXECUTION_PLAN、AGENTS.md、CONTRIBUTING、prompts/、执行计划、提示词、TestPyPI 与候选状态 | 两版通过 |
| 内链与结构 | `.venv/Scripts/python.exe -B scripts/check_docs.py` | 新增本报告前 42 份 Markdown 检查通过；最终数量见本轮工具输出 |
| 空白检查 | `git diff --check` | 通过；Git 报 LF/CRLF 提示，不影响退出结果 |

证据为本轮命令输出与本报告。未安装依赖、实际运行 uvx 包、执行本地构建或启动服务；模拟测试、真实 Aseprite 验证与客户端显示均未重跑，不把静态检查当作安装验收。

## 接口与兼容变化

无产品代码、协议、版本、依赖或分发清单变化。只新增公开文档中的 PyPI 启动方式，沿用现有 console script。

## 结构变化及同步情况

新增本文档交接；PROJECT_STRUCTURE 同步公开 README 职责、PyPI 启动入口与发布事实，根计划及 DOCS 总结同步。本轮不新建 assets/，不在 README 引用内部维护报告。既有工作区修改全部保留。

## 遗留与阻塞

文档检查无阻塞。仓库 Release 匿名访问 404，可能需要用户确认可见性或访问权限；未改仓库设置。官方 uv 脚本下载在本环境被 403 拒绝，不影响提供官方安装命令及替代安装方式。文档更新不会修改已发布的 PyPI 包说明，也未执行再次上传或 GitHub 推送。

## 下一模块该做什么

用户确认公开 Release 可访问后，可将列表链接细化为已核对的版本页或扩展附件链接。若需 PyPI 页面采用本次 README，后续按用户授权处理版本和发布；本轮不重复发布现有版本。

## 状态同步与提交

- [x] 中英 README、模块交接、维护总结、根计划和结构职责已同步。
- [x] 文档检查、JSON 示例与内部引用排除检查通过。
- 产品阶段集成不适用：独立文档维护。
- 本地 Git：本轮不提交、不推送，保持既有文档维护边界，不夹带开始时已有修改。
