# PACK-M4 · 限定 MCP SDK 主版本

## 状态

2026-10-23，依赖范围修正已验收；完整 stdio 回归未完成。依据用户要求修正依赖声明，沿用 [P2-M2](../development/prompts/P2-稳定性与首版发布.md#p2-m2) 的依赖和发布检查约定；前置维护见 [PACK-M3](PACK-M3.md)。

## 实际完成了什么

将 pyproject.toml 中 `mcp[cli]>=1.6.0` 改为 `mcp[cli]>=1.6.0,<2`，防止索引安装解析到未迁移的 SDK 2.x。运行 uv lock 同步元数据，保留 MCP 1.6.0 和全部其他锁定版本；运行代码与项目版本保持不变。

## 验收证据

本地 Windows、Python 3.13.15、uv 0.12.3、MCP SDK 1.6.0；命令在仓库根目录执行。

| 验收项 | 实际命令或步骤 | 结果与证据 |
|---|---|---|
| 锁文件更新 | `uv lock --cache-dir .work/uv-cache`；`git diff -- pyproject.toml uv.lock` | 成功解析 55 包，差异仅两处依赖范围；MCP 保留 1.6.0 |
| 锁定服务导入 | `uv run --locked --offline --cache-dir .work/uv-cache python -c 'import importlib.metadata as m; from aseprite_mcp.server import create_server; print("mcp=" + m.version("mcp")); print(type(create_server("cli")).__name__)'` | 输出 mcp=1.6.0、ContractServer，成功 |
| 服务入口初轮 | `uv run --locked --offline --cache-dir .work/uv-cache pytest -q tests/test_server.py -m 'not real' -k 'not real_cli' --basetemp=.work/pytest-pack-m4 --junitxml=.work/pack-m4.xml` | 前4项完成后 stdio 测试等待未结束，主动中止；不计作通过，未生成最终XML |
| 协议与工具注册 | `uv run --locked --offline --cache-dir .work/uv-cache pytest -q tests/test_protocol.py tests/test_server.py -k 'not stdio' --basetemp=.work/pytest-pack-m4-contract --junitxml=.work/pack-m4-contract.xml` | 34 passed、2 deselected，0.53s；证据 .work/pack-m4-contract.xml |
| 安装元数据 | `uv run --locked --offline --cache-dir .work/uv-cache python -c 'import importlib.metadata as m; from packaging.requirements import Requirement; r = next(Requirement(x) for x in m.requires("aseprite-mcp") if Requirement(x).name == "mcp"); assert "1.6.0" in r.specifier and "2.0.0" not in r.specifier; print(r)'` | 输出 mcp[cli]<2,>=1.6.0，确认构建后元数据允许1.6.0、拒绝2.0.0 |
| 文档与差异检查 | `uv run --locked --offline --cache-dir .work/uv-cache python scripts/check_docs.py`；`git diff --check` | 45份Markdown、服务入口和模块索引通过；差异检查通过 |

初次离线 uv lock 因新缓存缺少 twine 索引元数据而失败；改为正常联网解析后成功，无依赖版本变动。34项为模拟/契约及注册检查，不代表真实 stdio 或 Aseprite 验证。本次只收紧依赖范围，未重复真实 Aseprite GUI/CLI 或客户端图片显示验收。

## 接口与兼容变化

安装依赖声明拒绝 MCP SDK 2.x；1.x 范围内仍需按升级版本复测，本次验证的 SDK 为 1.6.0。公共 MCP 工具、Lua 协议与架构无变化。

## 结构变化及同步情况

无运行目录或入口变化；PROJECT_STRUCTURE 复核并记录依赖范围。新增本交接，同步 PACK 总结和根计划。README.md、README.en.md 及 assets/step6.png 为开始时已有用户修改，不纳入本模块提交。

## 遗留与接续

已发布的 0.4.1 元数据不会随本地修改更新；后续需要单独发布修复版才能影响 PyPI 安装。stdio 等待原因未确定，不据此声明完整服务回归通过，不阻塞本次仅依赖范围和元数据修正的验收。下一维护任务按用户要求定位；若发布，先读本报告及 [发布说明](../RELEASING.md)，确定新版本并完成构建、元数据、stdio和隔离安装验收。本次未推送、上传或发布，不声明已解决现有 PyPI 包的安装行为。

## 状态同步与提交

- [x] 依赖范围与元数据验收、维护总结、根计划与结构同步完成。
- [ ] stdio完整回归，初轮等待后中止，留待发布前完成。
- 阶段集成：独立依赖维护，不重开 P0～P3；本次以锁文件一致性、元数据和协议/工具注册为验收。
- 本地 Git 预定主题：`fix: constrain MCP SDK dependency to version 1`；仅本模块文件，不推送。
