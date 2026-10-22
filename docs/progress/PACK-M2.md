# PACK-M2 · 0.4.1 TestPyPI发布

## 状态

已完成，2026-10-22。前置[PACK-M1](PACK-M1.md)已验收。用户明确要求提升本地版本并发布TestPyPI；本次wheel和sdist已上传至 [aseprite-mcp 0.4.1](https://test.pypi.org/project/aseprite-mcp/0.4.1/)，公开摘要核对及测试索引重新安装均通过。

## 实际完成了什么

pyproject/uv.lock和扩展清单已有部分0.4.1修改，本轮补齐Python包版本、SERVICE_VERSION、Lua握手、协议样例以及当前使用文档；开发环境uv sync --locked后包元数据/导入版本/握手均为0.4.1。协议仍v1、功能范围不变，服务和扩展须配套升级。

基于用户当前本地源码、已准备的作者信息、twine依赖和中英README构建0.4.1。保留PACK-M1白名单，所有产物无docs/、提示词、AGENTS/SKILL、执行计划和CONTRIBUTING；许可/NOTICE保留。最终包与已验收安装环境39个运行源码/资源文件逐字节一致。README仅更新测试版状态后重建并重新执行严格检查，不改运行代码。

## 验收证据

Windows、Python3.13.15、uv0.12.3、SDK1.6.0、Aseprite1.3.7/API28。测试端口18765/18768、独立编辑器配置，不停止个人服务。软件位置仅由ASEPRITE_PATH提供；本地.pypirc用于TestPyPI认证，未打印凭据、未加入归档或Git。

| 验收项 | 实际命令/步骤 | 结果 | 证据 |
|---|---|---|---|
| 版本与锁 | uv lock --check；uv sync --locked --python 3.13；隔离/开发环境断言metadata、__version__、SERVICE_VERSION | 0.4.1一致，55项锁定包解析通过 | .work/041-sync.log及本报告 |
| 契约回归 | 项目Python -B -m pytest -q tests/test_protocol.py tests/test_auto_connection.py tests/test_reliability.py tests/test_live_bridge.py tests/test_live_animation.py tests/test_cli_backend.py tests/test_server.py -m "not real" -k "not real_cli" --basetemp=.work/pytest-041 --junitxml=.work/041-tests.xml | 71 passed、10 deselected in4.58s；模拟/契约，不替代GUI | .work/041-tests.log/XML |
| 构建/清单 | scripts/build_release.py --out-dir .work/release-0.4.1，及--check-only；产物同步dist | wheel/sdist/扩展/依赖/manifest/摘要齐全，禁用文件排除 | .work/041-build-final.log、041-check-final.log；dist/manifest.json、SHA256SUMS |
| 元数据 | python -B -m twine check --strict <0.4.1 wheel> <0.4.1 sdist> | 两包PASSED，README可渲染 | .work/041-twine-check.log及最终命令输出 |
| 真实安装 | 新uv环境041-install/service从锁定requirements安装依赖与wheel；python -I运行复制的verify_install.py，--work-dir .work/041-evidence --port 18768 --animation | site-packages、配套0.4.1、126项、真实核心/动画事务/历史/PNG/保存/CLI/重连与console116项通过 | .work/041-install.log、041-acceptance.log；041-evidence/acceptance.json |
| TestPyPI发布 | python -B -m twine upload --non-interactive --disable-progress-bar --config-file .pypirc --repository testpypi <精确0.4.1 wheel> <精确0.4.1 sdist> | 发布端点经Settings校验为https://test.pypi.org/legacy/；两包上传成功 | .work/041-upload.log |
| 公开校验 | GET https://test.pypi.org/pypi/aseprite-mcp/0.4.1/json，逐文件比对dist manifest SHA256 | 2个公开文件摘要与本地一致 | .work/041-testpypi-evidence.json |
| 索引安装 | uv pip install --python <隔离python> --reinstall --no-deps --index-url https://test.pypi.org/simple aseprite-mcp==0.4.1，再-I核对版本 | 从TestPyPI安装成功；依赖已按生产锁定清单准备 | .work/041-public-install.log |
| 文档 | scripts/check_docs.py、git diff --check与暂存差异检查 | 链接、入口、结构和空白检查通过 | 本报告 |

本轮为版本/发布维护，未重复P3全量208项测试，未重新执行浏览器显示检查；真实安装验证实际MCP PNG内容，模拟检查与真实结果分开记录。TestPyPI仅上传Python wheel/sdist，扩展包、锁定依赖和摘要保留dist；没有上传正式PyPI或创建GitHub Release。

## 接口与兼容变化

功能/协议v1不变，服务和扩展配套版本0.4.1；旧配套版本按既有握手规则明确拒绝。沿用用户已准备的本地元数据/依赖，不在本模块提交中混入作者信息、twine依赖、README整理等原有修改。发布包对应本地完整工作区，提交仅记录本次版本变更和发布事实。

## 结构变化及同步情况

新增本交接，更新PACK总结/根计划/PROJECT_STRUCTURE与当前版本说明。目录/职责/启动入口无变化，分发排除边界不变。凭据仅使用现有本地配置，不入库或打包。

## 遗留与接续

无阻止TestPyPI发布的问题。其他平台/版本未验证；TestPyPI测试版不代表正式PyPI发行。安装依赖优先使用已验收锁定requirements；测试索引可能不提供全部依赖。0.4.1已发布文件不可覆盖，后续更改包内容需另升版本；扩展安装使用本地dist中的0.4.1配套包。

## 状态同步与提交

- [x] 本地版本、严格检查、真实安装、TestPyPI公开摘要和索引安装通过。
- [x] 根计划、维护总结、结构与发布记录同步。
- 本地Git预定主题：`release: bump paired version to 0.4.1 and publish TestPyPI`；选择版本和发布记录文件，原有无关修改保留。不额外执行GitHub推送或正式PyPI发布。
