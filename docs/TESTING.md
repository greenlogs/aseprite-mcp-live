# 开发环境与验收

目标 Python 3.13+；Windows、Aseprite 1.3.7 / API 28 是已真实验证基线。macOS/Linux 尚未验证。Python 3.12 不满足要求。先安装 uv 和自己持有的 Aseprite，所有运行通过 `ASEPRITE_PATH` 配置。

## PowerShell 环境

```powershell
$env:UV_CACHE_DIR = "$PWD/.work/uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD/.work/python"
uv python install 3.13
uv sync --locked --python 3.13
$env:ASEPRITE_PATH = 'C:/path/to/Aseprite.exe'
uv run --locked python --version
uv run --locked python -c "import asyncio; from aseprite_mcp.server import create_server; print(len(asyncio.run(create_server().list_tools())))"
uv run --locked python -m aseprite_mcp
```

也可复制 `.env.example` 为 `.env` 设置路径；环境变量优先。服务默认为 MCP stdio，最后一条命令等待客户端输入，不会打印常规启动说明到 stdout。开发隔离目录 `.work/` 和 `.venv/` 已忽略。受限环境中 Python 的全局命令链接/注册表写入可能失败，但只要项目解释器安装和 `uv run` 成功不影响验收。

## 测试分层

```powershell
uv run --locked pytest -q --basetemp=.work/pytest --junitxml=.work/tests.xml
```

导入的上游测试是真实 CLI 测试：创建磁盘文件、图层、帧、绘图、导出、字体、特效与错误传播。每文件有独立画布，依赖同文件执行顺序，完整回归使用上面命令。临时目录由 pytest 管理，勿指向个人数据目录。`test_environment.py` 验证工具枚举及中文空格路径创建/读取/导出，Pillow 核对 PNG 像素。TrueType 字体缺失时相关测试明确跳过。

契约和进程故障模拟不代表已连接编辑器；真实 CLI 也不代表访问了其他进程的未保存文档。实时扩展和客户端图片显示已在 P1 验收，干净安装/发布验收属于 P2。每次实际结果见 [P0 阶段交接](progress/P0.md)。


## P0-M2 配置与专项验证

默认 core 配置枚举 9 个实时核心入口；P1 已接通实时功能，没有连接时除状态外返回 NOT_CONNECTED。只需要磁盘 CLI 时设置 `$env:ASEPRITE_MCP_TOOL_PROFILE = 'cli'`；枚举 115 个原名兼容工具和新增 cli_execute。all 配置为 125 个；原始 Lua 需额外显式设置 `ASEPRITE_MCP_ENABLE_RAW_LUA=1`。工具错误的兼容差异和全部上限见 [协议 v1](development/PROTOCOL.md)，环境变量见 `.env.example`。

```powershell
# 纯契约/故障模拟与真实 stdio；排除需要 Aseprite 的 stdio CLI 用例
uv run --locked pytest -q tests/test_protocol.py tests/test_server.py -k "not real_cli_through_stdio" --basetemp=.work/pytest-contract
# 包含真实 CLI 像素验证、无效批次回滚，以及模拟的假成功/超时/并发文件变化
uv run --locked pytest -q tests/test_cli_backend.py --basetemp=.work/pytest-cli
# 阶段集成：同步、实际解释器、枚举、完整回归（包含真实 CLI 读写/像素核对）
uv sync --locked --python 3.13
uv run --locked python --version
uv run --locked python -c "import asyncio; from aseprite_mcp.server import create_server; print(len(asyncio.run(create_server().list_tools())))"
uv run --locked pytest -q --basetemp=.work/pytest-p0-final --junitxml=.work/P0-final.xml
```

`test_protocol.py` 的实时 Backend 是模拟；`test_cli_backend.py` 前四个参数化用例操作真实 Aseprite，其余故障用例以 monkeypatch 注入进程/回执。`test_server.py` 启动真实 stdio MCP 子进程，完成 initialize、list_tools、status 和 NOT_CONNECTED 的 isError 验证；实时错误测试不连接编辑器；另一个 `test_real_cli_through_stdio` 用例通过真实 MCP 子进程调用真实 Aseprite CLI 读取文件。

P0 另执行 `uv build --out-dir .work/build`，检查 wheel 中的 `backends/cli.lua` 与入口存在，sdist 不含本地软件/私密配置/环境/缓存。这只是包资源检查，P2 的干净安装、扩展打包与正式发布验收尚未执行。

## P1-M1 连接专项

`uv run --locked pytest -q tests/test_live_bridge.py tests/test_protocol.py tests/test_server.py --basetemp=.work/pytest-live`。其中 socket 用例模拟编辑器，real_extension_lifecycle 使用真实非 batch UI 进程与隔离 ASEPRITE_USER_FOLDER，安装 package.json 并验证 init/exit、连接/重连。测试仅对隔离目录夹具脚本预设读/写/socket 权限，不修改个人配置；Windows 隐藏启动测试窗口。

开发扩展安装：将 extension 文件夹复制到 Aseprite 用户配置目录的 extensions/aseprite-mcp-live，0.2.0 起启用后自动等待默认 127.0.0.1:8765，无需选择文件；自定义端口在 File > Scripts > MCP: Connect / Settings 中设置。首次按 Aseprite 权限对话框允许读取配置和回环连接。配置文件含临时凭据，不入库、不分享；服务退出后清理。

## P1-M2 文档专项

`uv run --locked pytest -q tests/test_live_editor.py tests/test_live_bridge.py tests/test_protocol.py tests/test_server.py --basetemp=.work/pytest-editor`。test_live_editor 使用真实 UI、app.useTool 手工动作及真实 transaction 失败注入；live_support 中的本地测试控制文件仅用于夹具，不是产品协议或任意 Lua 工具。验证未保存文档、重名层、偏移/空 Cel、整批历史、修订冲突、去重和中文原生保存。

## P1 实时使用与图片验收

先按前文加载开发扩展，启动 stdio MCP 服务等待扩展自动连接；用 get_connection_status 获得 session_id。list_documents 返回会话 document_id 和 revision；读取后把明确目标及 revision 传给 apply_operations。批次支持 create_layer、set_opacity、pixel、rectangle，字段见[协议](development/PROTOCOL.md)。调用 get_preview(session_id,document_id,expected_revision,frame=1,scale=8) 可直接取得 PNG 图片块；undo/redo 后读取新 revision 再看图。未调用 save_sprite 不保存文件，保存仅支持 .aseprite/.ase 绝对路径，覆盖显式允许。

```powershell
# 专项：真实 MCP 图片、实际 PNG 像素/透明度、历史闭环和体积上限
uv run --locked pytest -q tests/test_live_preview.py --basetemp=.work/pytest-preview
# 阶段集成 + 全部旧 CLI 回归
uv run --locked pytest -q --basetemp=.work/pytest-p1-final --junitxml=.work/P1-final.xml
```

test_live_preview 以真实 MCP SDK 1.6.0 stdio 客户端完成闭环，在对应 pytest 临时目录生成 before/after/undo/redo PNG、client-gallery.html 和 client-evidence.json。用浏览器打开 HTML 确认实际显示；本次 Edge 155.0.4283.62 已实际渲染、截图并检查四图 64×64。像素、协议收到图片和显示成功是分开的验收步骤。最终本地证据保留于 .work/p1-evidence；不将临时图片/配置/凭据入库。

SDK 1.6.0 的 Windows 客户端退出会强杀 stdio 子进程，可能留下发现文件；正常服务退出会清理。0.2.0 默认发现文件按 host/port 自动发布，下次成功绑定后替换残留；使用固定 ASEPRITE_MCP_CONNECTION_FILE 时，若重启提示文件已存在，先确认旧服务已退出，再移除这一个残留 JSON 并重启。不要删除仍在使用的连接配置。异常退出策略和正式安装在 P2 继续验收。

## P2-M1 故障回归

`uv run --locked pytest -q tests/test_reliability.py --basetemp=.work/pytest-reliability`。
前十个用例覆盖真实 socket 的模拟编辑器、取消/迟到/重复/旧会话/磁盘冲突及实际 Python 子进程清理；标记 real 的最后用例使用真实 UI 验证事件风暴、人工切换/修改/撤销、事务超预算回滚及执行后丢回执。完整上游与实时回归仍使用全文的全量命令。0.2.0 默认按 host/port 自动发现；旧显式文件仍不自动清理残留。

## P2 隔离安装与阶段集成

先运行 `uv run --locked python scripts/check_docs.py` 与 `uv run --locked python scripts/build_release.py --out-dir dist`。按 [INSTALL](INSTALL.md) 创建全新 uv 环境、同步 dist/requirements.txt，再以 --no-deps 安装 dist 中 wheel；不能用 editable 安装。

```powershell
# 将路径替换为实际位置；work-dir 必须是尚不存在的私有测试目录。
uv run --locked python scripts/verify_install.py --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --extension 'C:/Downloads/aseprite-mcp/aseprite-mcp-live-0.2.0.aseprite-extension' --work-dir '.work/install-acceptance'
```

也可将该脚本复制到隔离目录，用新安装环境 python.exe 直接执行；脚本只依赖 SDK、Pillow 和分发产物，不导入开发目录产品源码。服务用新环境 `python -I -m aseprite_mcp`、独立 cwd 启动，probe 确认从 site-packages 导入。扩展从 ZIP 精确清单解压至全新 ASEPRITE_USER_FOLDER，测试脚本仅对自身隔离文件预授权读/写/socket，不修改个人配置或绕过实际产品调用。

脚本完成未保存人工笔画、读取、整批编辑/去重、MCP ImageContent、撤销/重做像素相等、中文显式保存/覆盖拒绝、安装后公共 CLI 读写与旧工具读取、新会话拒绝旧 ID；验收使用 SDK 1.6.0 的真实 stdio 客户端。生成 acceptance.json、server-stderr.log、四幅实际收到的 PNG 与 client-gallery.html。用浏览器打开图库确认四图真实显示（64×64），截图与浏览器版本单独记录；收到数据和显示成功分别验收。

全量回归仍用 `uv run --locked pytest -q --basetemp=.work/pytest-p2-final --junitxml=.work/P2-final.xml`。CI 的无 Aseprite 命令见 `.github/workflows/check.yml`；只包含模拟契约/真实 Python 子进程/本地 socket，不能代替真实 UI、干净安装或客户端显示。

## P2-M3 自动连接专项

`uv run --locked pytest -q tests/test_auto_connection.py --basetemp=.work/pytest-auto`。纯契约验证 CLI > 环境 > 默认、参数错误、固定端口占用、凭据原子发布/轮换和旧文件兼容。real 用例在隔离 UI 中验证先开编辑器再开服务、真实 SDK 强杀重启自动恢复、手动停止/恢复、自定义端口与旧会话失效；不在测试脚本中调用 connect() 或选择文件。conftest 给所有测试使用独立 ASEPRITE_MCP_RUNTIME_DIR，不读写个人运行目录。

开发环境若 aseprite-mcp.exe 正被现有客户端占用，uv sync 可能无法替换 Windows 可执行文件。无需终止个人会话；可用既有环境 python.exe -B -m pytest 执行，再将新 wheel 安装到独立环境验证。升级日常环境时先停止客户端对应服务。独立包验收脚本已使用产品自动发现，继续覆盖完整图片/历史/保存与 CLI 链路。
