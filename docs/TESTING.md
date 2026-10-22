# 开发环境与验收

当前服务与扩展0.4.1，业务协议v1。目标Python3.13+、uv，Windows Aseprite1.3.7/API28为真实基线；其他平台未验证。软件路径通过ASEPRITE_PATH配置，本机位置仅记录在[REFERENCES](REFERENCES.md)。

## 环境和完整回归

```powershell
$env:UV_CACHE_DIR = "$PWD/.work/uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD/.work/python"
uv sync --locked --python 3.13
$env:ASEPRITE_PATH = 'C:/path/to/Aseprite.exe'
uv run --locked pytest -q --basetemp=.work/pytest --junitxml=.work/tests.xml
```

如果Windows现有客户端占用项目aseprite-mcp.exe，uv同步可能无法替换它。不要终止无关个人会话；可直接用现有`.venv/Scripts/python.exe -B -m pytest`运行，并在独立环境验证新wheel。升级日常环境时先停止对应服务。依赖版本变化需重新同步，不能把旧依赖测试冒充新环境通过。

上游工具测试实际启动CLI，覆盖创建、绘图、图层/帧、导出、文本、特效及错误。每测试文件使用独立画布，文件内可能有先后依赖；完整回归使用全文命令。中文/空格路径及Pillow像素核对见test_environment/test_cli_backend。所有临时输出位于明确的pytest目录或.work，不使用个人画布；缺失字体时测试会明确跳过。

## 测试分层

- test_protocol：严格模型、错误/预算、模拟后端、去重/取消及冻结样例。
- test_server：真实MCP SDK stdio子进程，枚举core/cli/all、错误JSON/isError，另有真实MCP→CLI读取。
- test_cli_backend：真实Aseprite读写/像素、批次失败不改文件；monkeypatch进程/回执/文件修改故障单独模拟。
- test_live_bridge：真实socket配模拟编辑器，真实非batch UI加载/退出扩展生命周期。
- test_live_animation：严格参数/能力开关/协商/未知回执；真实MCP/UI/CLI五种动画操作、逐帧预览、事务/CPU/复制预算回滚、偏移/缺失/关联Cel、元数据修订、上下文和拒绝边界。
- test_live_editor/test_live_preview：真实未保存文档、事务、人工工具、历史、保存、直接ImageContent和PNG像素/区域/限制。
- test_reliability：模拟取消/超时/迟到/重复、实际Python子进程终止、文件摘要及独立路径；real用例验证真实编辑器故障回滚和写入后丢回执。
- test_auto_connection：CLI优先级、无文件直连、普通网页Origin拒绝与原生Origin放行；real用例验证服务强杀重启、手动停止/恢复、编辑器先开和自定义端口。连接模块io.open被替换为报错函数后仍须通过。

模拟结果不能替代真实GUI，真实CLI不能证明访问了内存文档；SDK接到图片与客户端实际显示也是两种验收。夹具只对独立ASEPRITE_USER_FOLDER中的测试脚本预授权，不修改个人配置。测试控制JSON只用于驱动手工GUI动作；产品连接不读取这些文件、不注入凭据或连接配置。

默认core为9项、cli为116项、all为125项；原始Lua需要额外显式开关。当前默认连接直接到127.0.0.1:8765，扩展启用后自动等待；不再有连接JSON/运行目录。共享固定端口的测试必须串行执行，不同时运行全量回归和独立安装验收。

## 无Aseprite的CI检查

```powershell
uv run --locked pytest -q tests/test_protocol.py tests/test_auto_connection.py tests/test_reliability.py tests/test_live_bridge.py tests/test_live_animation.py tests/test_cli_backend.py tests/test_server.py -m "not real" -k "not real_cli" --basetemp=.work/ci
uv run --locked python scripts/check_docs.py
uv run --locked python scripts/build_release.py --out-dir dist
```

实际Windows工作流见.github/workflows/check.yml；本地复现不代表远程CI已执行。real标记和筛选明确排除软件用例，不能据此宣布WindowsGUI验收通过。

## P2 隔离安装与阶段集成

按[INSTALL](INSTALL.md)先建立新uv环境、用分发requirements.txt同步依赖、--no-deps安装wheel，不能editable安装。scripts/verify_install.py可复制到隔离目录，用安装环境直接执行，产品从site-packages启动：

```powershell
# 路径替换为实际位置，work-dir应为尚不存在的私有目录。
C:/Tools/aseprite-mcp/.venv/Scripts/python.exe -I scripts/verify_install.py --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --extension 'C:/Downloads/aseprite-mcp/aseprite-mcp-live-0.4.0.aseprite-extension' --work-dir '.work/install-acceptance'
```

脚本用python -I -m aseprite_mcp和console两条真实入口，在全新编辑器配置中解压扩展ZIP，依靠产品Host/Port直接连接；没有连接文件、运行目录或token。验证未保存人工笔画、读取、原子批次/去重、MCP PNG、撤销/重做逐像素相等、中文显式保存/覆盖拒绝、CLI副本读写/旧工具、重连后旧会话失效与CLI回执保留。

生成acceptance.json、server-stderr.log和实际收到的四张PNG/client-gallery.html；浏览器实际加载图库后检查complete与自然尺寸64²，截图单独记录。不能从源文件另外导出图来替代客户端收到的图片。安装包与被验收的wheel/扩展/依赖摘要必须一致，文档更新后重建源码包仍需检查。

## 历史验证

P0/P1早期手选JSON和0.2.0自动读取凭据的流程已被0.3.0无文件直连替换；相关真实命令/证据按当时版本留在[阶段交接](progress/P2.md)，不能复制旧连接步骤作为当前安装方法。

<a id="p1-实时使用与图片验收"></a>
当前实时操作说明见[安装与使用](INSTALL.md#第一条创作闭环)。实时断线不切换CLI，未知写入先刷新状态再决策，保存独立且覆盖明确允许。

## P3 动画及隔离端口验收

已有服务占用默认8765时，为本轮串行测试设置以下两个相同环境值，无需停止个人服务：

```powershell
$env:ASEPRITE_MCP_TEST_PORT = '18765'
$env:ASEPRITE_MCP_PORT = '18765'
uv run --locked pytest -q --basetemp=.work/pytest-p3 --junitxml=.work/p3.xml
uv run --locked python scripts/check_capabilities.py
```

TEST_PORT只由测试夹具读取，产品默认仍8765。固定默认值/参数优先级契约仍测真实默认；custom-port用例独立测试8766/8767。不要并发运行占用同一测试端口的命令。

复制verify_install.py到隔离目录后，安装环境用 `python -I <复制脚本> --python <新环境python> --extension <0.4.0扩展包> --work-dir <新目录> --port 18768 --animation`，可在独立端口验收完整核心加动画组合。未加--animation仍验证默认125项all；加入后126项，cli仍116。端口和能力集仅是测试脚本选项，不改个人客户端配置。

P3最终：208项完整回归、71项无软件检查（10项排除）、116项矩阵/实际注册及启用后高级入口一致。新环境site-packages/配套ZIP/SDK1.6.0和Edge实际图片显示通过；命令、失败修正和证据见[P3-M2](progress/P3-M2.md)。没有执行远程CI。
