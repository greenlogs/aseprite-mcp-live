# PACK-M3 · 修复干净检出 CI 临时目录

## 状态

2026-10-22，已实现且本地验收通过。前置 [PACK-M2](PACK-M2.md) 已完成；本次为用户提供 GitHub Actions 日志后的 CI 维护，沿用 [P2-M2 发布检查要求](../development/prompts/P2-稳定性与首版发布.md#p2-m2)。远程修复重跑未执行。

## 实际完成了什么

下载的 `.work/logs_107814523365/0_check.txt` 及 `check/5_Contracts and injected failures (no Aseprite).txt` 显示：依赖同步成功，71个用例均在 tests/conftest.py 的 session/autouse base_dir 夹具中报 FileNotFoundError / WinError 3。全新 checkout 不包含被忽略的 `.work/`，pytest 创建 `--basetemp=.work/ci` 时不递归创建父目录；JUnit XML 在结束时创建目录，不能补救此前失败。Node.js 弃用警告不是本次退出原因；文档、能力、打包和上传步骤未运行。

`.github/workflows/check.yml` 在 pytest 前新增 PowerShell `New-Item -ItemType Directory -Force -Path .work | Out-Null`，兼容首次和重复执行。保留原测试筛选、临时目录与 XML 路径。TESTING 同步父目录前置步骤及能力矩阵命令。

## 验收证据

本地 Windows、Python3.13.15、uv0.12.3、pytest9.0.3；失败的远程 runner 为 Windows / Python3.13.16。从 `git archive --format=zip HEAD`（基线6b066e2）解压独立源码到 `.work/ci-fix-source`，仅覆盖本模块文件，不复制现有 .work、.venv 或未提交的 README/作者/依赖修改。uv 的缓存和解释器目录放在副本外，不提前创建副本内 .work。测试/构建日志位于外层 .work，保留 XML 与清单于 `.work/ci-fix-evidence/`。

| 验收项 | 实际命令或步骤（副本内执行） | 结果 | 证据 |
|---|---|---|---|
| 锁定同步 | `uv sync --locked --python 3.13` | 成功，独立环境 | `.work/ci-fix-sync.log` |
| 原因复现 | 断言副本 .work 不存在；`uv run --locked pytest -q tests/test_protocol.py -x --basetemp=.work/ci` | 首个夹具同样 WinError3，退出1 | `.work/ci-fix-before.log` |
| 修复与契约回归 | 执行新增 New-Item；`uv run --locked pytest -q tests/test_protocol.py tests/test_auto_connection.py tests/test_reliability.py tests/test_live_bridge.py tests/test_live_animation.py tests/test_cli_backend.py tests/test_server.py -m "not real" -k "not real_cli" --basetemp=.work/ci --junitxml=.work/ci.xml` | 71 passed、10 deselected，5.02s；模拟/契约与真实 socket/stdio，不调用 Aseprite | `.work/ci-fix-tests.log`、`ci-fix-evidence/ci.xml` |
| 后续 CI 检查 | `uv run --locked python scripts/check_docs.py`；`uv run --locked python scripts/check_capabilities.py` | 初次干净副本38份 Markdown及116项矩阵/CLI注册通过；交接同步后另复核文档 | 本报告、命令输出 |
| 打包 | `uv run --locked python scripts/build_release.py --out-dir dist` | wheel/sdist/扩展/锁定依赖/摘要清单通过，产物仅在临时副本 | `.work/ci-fix-build.log`、`ci-fix-evidence/manifest.json` |
| 提交边界 | `git diff --check`；暂存区文件和差异检查 | 仅本模块工作流/文档；原有修改保留 | 本次命令输出 |

未修改运行实现，不重复真实 Aseprite GUI、CLI或客户端图片显示验收。未执行远程 workflow、artifact 上传、GitHub 推送或任何发布；本地结果不等同远程 Actions 已恢复。临时源码、隔离环境及重复构建产物验收后清理，保留原下载日志和本次证据。

## 接口与兼容变化

无产品公共接口、协议、依赖或版本变化。准备步骤使用现有 Windows runner 的 PowerShell；无需新增测试包或凭据。

## 结构变化及同步情况

产品目录无变化；工作流增加测试父目录初始化职责。PROJECT_STRUCTURE 同步职责、复核记录及远程 CI 真实失败状态；新增本交接，更新 PACK 总结与根计划。TESTING 同步复现步骤，README、架构无需修改。

## 遗留与接续

本地验收无阻塞。后续获授权推送修复提交后，在 GitHub 上重跑 Contracts and packages，核对测试、文档、能力、构建及 artifact 上传均成功。Node.js 弃用警告留作独立维护，不在本次扩大 action 升级范围。下一维护任务按用户要求定位；优先读取本报告与 check.yml。

## 状态同步与提交

- [x] 已同步模块交接、维护总结、根计划及结构职责。
- [x] 本地干净副本原错复现、修复与全部后续本地 CI 检查通过。
- [ ] 远程修复重跑；未推送，后续单独验证。
- 阶段集成：本次独立维护，以完整本地 CI 检查为验收，不重开 P0～P3 产品阶段。
- 本地 Git 预定主题：`ci: create workspace before pytest on clean checkouts`；只选择本模块差异，不推送。
