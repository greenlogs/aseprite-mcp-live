# 分发维护总结

| 模块 | 状态 | 交接 |
|---|---|---|
| PACK-M1 · 精简分发清单与首次推送 | 打包已验收；用户授权本模块提交后首次推送main | [PACK-M1](PACK-M1.md) |
| PACK-M2 · 0.4.1 TestPyPI发布 | 已发布并核对公开摘要及索引安装 | [PACK-M2](PACK-M2.md) |

2026-10-22：wheel、源码包和扩展统一禁止docs/、提示词、AGENTS/SKILL、执行计划和CONTRIBUTING；sdist只保留运行与重建需要的文件及许可。真实三归档检查、6种污染拒绝、无docs的源码独立重建、隔离安装真实Aseprite/MCP/动画/CLI回归通过。origin指向用户指定的greenlogs/aseprite-mcp-live，提交后普通推送main，不发布Release/PyPI。完整命令、证据与未提交修改边界见PACK-M1。


0.4.1服务/扩展/握手已统一；71项契约检查、真实隔离安装、严格元数据/分发检查通过。wheel与sdist发布到TestPyPI，未上传正式PyPI或GitHub Release。
