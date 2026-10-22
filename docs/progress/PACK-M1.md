# PACK-M1 · 精简分发清单与首次推送

## 状态

2026-10-22，打包变更已实现并验收通过。前置[P3-M2](P3-M2.md)已验收。用户本次明确授权配置并推送到 `git@github.com:greenlogs/aseprite-mcp-live.git`；远程读取成功且当前为空，提交本模块后执行普通main推送，不强制覆盖、不发布Release或上传PyPI。

## 实际完成了什么

源码包白名单收紧为运行源码、Lua扩展、build_release.py、构建/锁文件、环境样例、README和MIT许可。Hatch强制附带的.gitignore与PKG-INFO属于构建元数据，仍允许。docs/、测试、CI、其他维护脚本、提示词、AGENTS.md、SKILL.md、执行计划和CONTRIBUTING不分发。仓库中保留这些维护文件。

构建器同时检查wheel/sdist/扩展的禁用路径，兼容归档POSIX路径及反斜杠变体，并对sdist施加精确文件白名单；保留LICENSE与扩展NOTICE中的原版权/上游SHA。产品版本仍0.4.0，运行代码/协议/能力未改。

现有未提交的README整理、作者信息、twine依赖、忽略规则及历史清理记录保留；为避免混入分发，构建使用HEAD归档加本次打包修改的独立快照，pyproject和uv.lock采用同一已提交基线。提交时对共享文件只暂存本模块差异。

## 验收证据

Windows、Python3.13.15、uv0.12.3；安装验证沿用隔离环境的锁定生产依赖、SDK1.6.0、Aseprite1.3.7/API28。软件路径仅由ASEPRITE_PATH提供。

| 验收项 | 真实命令/步骤 | 实际结果 | 证据 |
|---|---|---|---|
| 远程核实 | git -c core.sshCommand='ssh -o BatchMode=yes -o ConnectTimeout=15' ls-remote <用户SSH地址> | SSH访问成功，远程无分支；首次沙箱不能读取known_hosts，使用本机授权访问成功 | 本报告、命令输出 |
| 构建与检查 | 项目Python -B执行.work/pack-source/scripts/build_release.py，--out-dir <工作区dist绝对路径>，再加--check-only；项目内uv缓存 | wheel/sdist/扩展/requirements/manifest/SHA256SUMS齐全，三个归档均无禁用文件 | .work/pack-build-final.log；dist/manifest.json、SHA256SUMS |
| 内容回归 | Python复制真实归档后分别注入docs/INSTALL.md、nested/AGENTS.md、prompts/task.md、CONTRIBUTING.md、EXECUTION_PLAN.md、docs/development/plan.md，再调用inspect_artifacts | 6种实际归档污染全部拒绝；原归档检查通过 | .work/pack-content-evidence.json |
| 源码独立重建 | 安全解压sdist，项目Python -B运行其中scripts/build_release.py --out-dir <.work/pack-rebuilt绝对路径> | 没有docs/测试/维护脚本仍可构建wheel、sdist、扩展及锁定依赖，清单检查通过 | .work/pack-rebuild.log |
| 最终安装回归 | uv pip install --python .work/p3-install/service/Scripts/python.exe --reinstall --no-deps dist/<0.4.0 wheel>；同环境python -I执行隔离verify_install.py，--python <同python> --extension dist/<0.4.0扩展> --work-dir .work/pack-install-evidence --port 18768 --animation | site-packages启动，126项、真实ZIP直连、核心/动画事务及撤销重做/PNG/中文保存/CLI/重连、console116项通过 | .work/pack-install.log、pack-installed.log；pack-install-evidence/acceptance.json |
| 文档与空白 | 项目Python -B执行scripts/check_docs.py；git diff --check及暂存区检查 | 本地文档链接/入口/结构与差异检查通过 | 本报告与命令输出 |

初轮构建因Hatch自动加入.gitignore而被新白名单拒绝；核对Hatch源码确认强制元数据行为后明确允许.gitignore，再构建通过。模拟归档污染与真实安装结果分开；本轮没有修改运行代码，因此未重复P3全量208项测试，也未重新执行浏览器显示验证。真实安装回归验证MCP实际PNG内容。

## 接口与兼容变化

工具/协议/版本/运行依赖无变化；sdist不再携带完整开发环境，开发测试需克隆Git仓库。源码包仍支持安装和独立构建，wheel/扩展运行资源及MIT来源完整。

## 结构变化及同步情况

新增PACK.md与本交接；更新PROJECT_STRUCTURE、RELEASING、ARCHITECTURE和根计划，区分Git仓库文件与分发文件。origin配置为用户指定仓库。临时构建快照/污染归档/重复解包产物在验证后清理，保留dist正式候选、日志/归档清单/安装证据；未删除本地软件或个人文件。

## 遗留与阻塞

打包验收无阻塞。其他平台未验证，未声称新增产品能力；未授权也未执行Release/PyPI上传。现有未提交改动不包含在此次推送的新增提交中。

## 下一模块该做什么

按用户授权提交并推送main，随后用ls-remote核对远程SHA等于本地HEAD。后续实际发布使用dist摘要对应产物，另按当次授权处理；完整开发资料与测试从Git仓库读取。产品维护仍见[兼容清单](../development/CAPABILITIES.md)。

## 状态同步与提交

- [x] 分发规则、归档内容、独立重建与真实安装验收通过。
- [x] 根计划、维护总结、结构与实际分发内容同步。
- 本地Git预定主题：`build: exclude development docs and prompts from distributions`；显式选择本模块文件。本次推送已获用户授权，提交后正常推送main并核对远程SHA。
