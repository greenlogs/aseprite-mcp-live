# 第三方来源与导入记录

导入日期：2026-10-21。上游：[diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp)。实际提交：`90d1696a7e41edff89bbd0823ae6a5f86c114bcc`，GitHub 提交 API 与固定提交归档相互核对，未使用浮动分支。

原始 MIT 许可与 `Copyright (c) 2024 Divyansh Singh` 完整保留于根 `LICENSE`。新增代码同样采用 MIT。软件 Aseprite 不在此许可范围，不导入其二进制、资源或用户数据。

导入范围：`aseprite_mcp/` 全部 Python 源码、`tests/` 全部测试、`pyproject.toml`、`uv.lock`、`LICENSE`。原始文件逐项 SHA-256、Git tree 和归档摘要见 [导入清单](upstream-manifest.json)。上游 README、Docker/CI、个人 MCP 配置、示例和维护脚本没有合并；没有复制第三方字体或未许可图片。

本地适配：测试的固定 `/tmp/ase-pytest` 改为 pytest 会话夹具，消费者显式接收 `base_dir`；Lua 临时脚本和进程输出使用 UTF-8；进程增加超时与 OS 错误处理；显式声明 `python-dotenv`，M2 直接依赖 `pydantic`，增加构建与命令入口；锁文件保留上游可解析版本并重新同步。产品文档继续采用现有中文文档。

P0-M2 在此基线上新增协议模型、受控 CLI 适配器和能力暴露配置，不把高级 CLI 工具当作实时功能。后续升级必须记录新 SHA、许可、差异与真实回归。

P2 分发复核：wheel 保留原 MIT 许可，扩展包包含 LICENSE 与自包含 NOTICE.md，源码包保留本来源记录及导入清单。新增实时/可靠性/打包代码同为 MIT；没有引入字体、示例图像或 Aseprite 程序。生产依赖由锁定 requirements.txt 单独安装，不嵌入服务 wheel。

## P3-M1 上游复核（2026-10-22）

GitHub HEAD 实查 a89b205bed31930ee141edf319e78c71ef16bba6，123 项装饰器工具，比导入基线新增 7 项、无删除/更名。固定归档摘要、逐项名称和 MIT 原文见 [兼容矩阵](development/tool-compatibility.json)，范围判断见 [兼容说明](development/CAPABILITIES.md)。保留导入 SHA，不升级或混入新源码；新批次沿用已导入算法与官方 API，继续保留原版权。
