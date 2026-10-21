# 参与开发

先读 [执行计划](EXECUTION_PLAN.md)、[开发约定](docs/development/README.md)、当前模块提示词和必要交接，再检查代码。目标 Python 3.13+，依赖用 uv 管理；配置和真实命令见 [测试说明](docs/TESTING.md)。

中文说明、英文代码标识。实现与测试和交接同批更新；结构只在 [项目结构](docs/PROJECT_STRUCTURE.md) 维护。每模块真实验收后勾选，模拟和真实 Aseprite 结果分开记录。保留上游许可，升级记录固定提交。

已有 Git 仓库时每个已验收模块默认显式选择本模块文件做一次本地提交，不修改全局身份、不推送。当前已按用户单独授权初始化本地 Git，P0 基线合并为一次首次提交。不要将本地软件、凭据、恢复会话和临时图像入库。

提交前执行 [文档与候选检查](docs/RELEASING.md)。Windows CI 只跑不需要 Aseprite 的契约及打包；真实 GUI/客户端与独立安装步骤见 [测试说明](docs/TESTING.md#p2-隔离安装与阶段集成)，分别报告结果。版本更新需同步 pyproject、package.json、桥接握手/协议常量及兼容样例，不上传 Aseprite 或个人配置。
