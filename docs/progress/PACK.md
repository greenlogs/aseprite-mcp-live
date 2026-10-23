# 分发维护总结

| 模块 | 状态 | 交接 |
|---|---|---|
| PACK-M1 · 精简分发清单与首次推送 | 打包已验收；用户授权本模块提交后首次推送main | [PACK-M1](PACK-M1.md) |
| PACK-M2 · 0.4.1 TestPyPI发布 | 已发布并核对公开摘要及索引安装 | [PACK-M2](PACK-M2.md) |
| PACK-M3 · 修复干净检出 CI 临时目录 | 本地干净副本复现及修复验收通过；待推送后远程重跑 | [PACK-M3](PACK-M3.md) |
| PACK-M4 · 限定 MCP SDK 主版本 | 依赖/锁文件及元数据检查、34项契约通过；stdio完整回归未完成，未发布 | [PACK-M4](PACK-M4.md) |

2026-10-22：wheel、源码包和扩展统一禁止docs/、提示词、AGENTS/SKILL、执行计划和CONTRIBUTING；sdist只保留运行与重建需要的文件及许可。真实三归档检查、6种污染拒绝、无docs的源码独立重建、隔离安装真实Aseprite/MCP/动画/CLI回归通过。origin指向用户指定的greenlogs/aseprite-mcp-live，提交后普通推送main，不发布Release/PyPI。完整命令、证据与未提交修改边界见PACK-M1。


0.4.1服务/扩展/握手已统一；71项契约检查、真实隔离安装、严格元数据/分发检查通过。wheel与sdist发布到TestPyPI，未上传正式PyPI或GitHub Release。

PACK-M3：下载日志显示远程 Windows CI 因 `.work/` 不存在而在夹具初始化时产生71个错误。工作流新增幂等目录准备；本地 HEAD 干净源码副本复现原错，修复后71项通过、10项排除，文档/能力/打包检查通过。尚未推送或远程重跑，不代表真实 Aseprite GUI 回归。

PACK-M4：MCP SDK 依赖增加 `<2` 上限，锁定版本仍为1.6.0；34项契约/工具注册及安装元数据检查通过，stdio子进程检查等待未结束后中止，未完成完整回归。修改尚未进入PyPI，需要后续单独发布修复版。
