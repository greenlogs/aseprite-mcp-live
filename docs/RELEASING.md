# 本地候选构建与发布检查

本文件说明可重复构建和验收，不授权上传、推送或发布 Release。本项目尚无远程仓库/下载地址，不能用参考上游地址代替。

## 构建入口

```powershell
uv sync --locked --python 3.13
uv run --locked python scripts/check_docs.py
uv run --locked python scripts/build_release.py --out-dir dist
uv run --locked python scripts/build_release.py --out-dir dist --check-only
```

0.4.0 候选包含 wheel、源码 tar.gz、`.aseprite-extension`、生产依赖 requirements.txt、manifest.json 和 SHA256SUMS。扩展为确定时间戳、排序后的 ZIP，根部直接为 manifest/五个 Lua/许可与 NOTICE；构建器核对 manifest、Lua 握手和 Python 服务版本对应协议 v1。requirements.txt 来自 uv.lock，不包含源码编辑安装或开发依赖。

wheel 只含 aseprite_mcp 包、元数据及 MIT 许可，必须包含 backends/cli.lua 和 stdio 脚本入口。源码包白名单包含源码/扩展/测试/构建脚本/文档/锁文件，保留上游来源及许可。构建器逐一检查包清单，拒绝本地软件、可执行程序、个人 .env/.codex/.agents、恢复会话和缓存；本地 Aseprite/ 不分发。扩展 NOTICE 记录上游固定提交，未打包字体/图片资源；Python 依赖按各自许可从包索引安装，不打入本项目 wheel。

## 验收顺序

1. 运行全量真实 Windows 回归（含 CLI 与 UI），失败则撤回相关勾选。
2. 按[安装文档](INSTALL.md)用分发包建立全新 uv 环境；不可 editable 安装，不给服务设置源码 PYTHONPATH。真实服务应从 site-packages 导入。
3. 按[隔离验收](TESTING.md#p2-隔离安装与阶段集成)从扩展 ZIP 安装到全新配置目录，真实 MCP SDK 客户端完成未保存文档、批次/去重、图片、撤销/重做、中文保存、覆盖拒绝、CLI 与重连；用浏览器实际渲染收到的图片并检查截图。
4. 核对全部 Markdown 链接、结构入口与安装命令；重新构建最终分发包，确认最后代码对应已安装验收的包，更新阶段交接和清单摘要。

`.github/workflows/check.yml` 为 Windows 的模拟契约/进程故障、文档检查与打包工作流。它没有 Aseprite，也不执行 GUI 验收；此阶段仅在本地复现同样命令，未上传或运行 GitHub Actions，不宣称远程 CI 已通过。

已验收平台只能写 Windows Aseprite 1.3.7/API 28。客户端验收使用 Python MCP SDK 1.6.0 与 HTML 图片视图，不能写成其他客户端均兼容。旧高级工具不自动获得实时支持；能力边界见[README](../README.md)与[协议](development/PROTOCOL.md)。

## 候选与发布状态

本次构建、干净安装与阶段集成结果以 [P3-M2 交接](progress/P3-M2.md) 和 [P3 总结](progress/P3.md) 为准；构建成功本身不足以认定可发布。维护者未来获得当次远程授权后，再设置仓库地址、上传审核后的相同摘要文件及说明。没有自动发布步骤。

2026-10-21 本地结论：0.1.0/协议 v1 候选已完成 Windows 隔离安装、真实 MCP 图片与阶段集成验收，191 项回归通过；尚未发布，也未执行远程 CI。实际候选及摘要保留 .work/release，结果详见 P2-M2 交接。

0.2.0 候选新增固定端口、命令行参数与扩展自动发现，实际结果见 [P2-M3](progress/P2-M3.md)。verify_install.py 使用产品自动连接流程，不再由测试注入 connect() 或读取凭据。

0.2.0 最终本地结论：197项完整回归、自动发现/强杀重启与新环境安装真实闭环通过；候选在 .work/release-auto，尚未远程发布。历史 .work/release 的0.1.0包保留为旧验收证据，安装新版本使用0.2.0配套服务和扩展。

0.3.0 改用固定端点直接握手，移除发现文件、token和扩展选JSON入口；服务/扩展必须配套升级。当前追加验收见 [P2-M4](progress/P2-M4.md)。历史0.1/0.2候选记录保留，不代表当前连接流程。

2026-10-22：0.3.0无文件直连候选已验收，197项全量/61项无软件检查/独立安装真实闭环与显示通过。当前候选.work/release-direct；旧release/release-auto保留历史，尚未远程发布。

2026-10-22 P3：0.4.0基础动画候选已验收，208项完整回归、71项无软件检查、矩阵与注册一致；新uv环境从wheel/锁定生产依赖安装，真实配套ZIP/SDK/CLI双入口、动画历史和图片显示通过。候选.work/release-p3，证据.work/p3-evidence与.work/p3-installed-final-evidence。依赖/软件版本基线未变，未推送、发布或运行远程CI。
