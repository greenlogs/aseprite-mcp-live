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

契约和进程故障模拟不代表已连接编辑器；真实 CLI 也不代表访问了其他进程的未保存文档。实时扩展、客户端图片显示和干净安装/发布验收分别属于 P1/P2。每次实际结果见 [P0 阶段交接](progress/P0.md)。


## P0-M2 配置与专项验证

默认 core 配置枚举 9 个实时核心入口，P0 没有连接，除状态外返回 NOT_CONNECTED。只需要磁盘 CLI 时设置 `$env:ASEPRITE_MCP_TOOL_PROFILE = 'cli'`；枚举 115 个原名兼容工具和新增 cli_execute。all 配置为 125 个；原始 Lua 需额外显式设置 `ASEPRITE_MCP_ENABLE_RAW_LUA=1`。工具错误的兼容差异和全部上限见 [协议 v1](development/PROTOCOL.md)，环境变量见 `.env.example`。

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

开发扩展安装：将 extension 文件夹复制到 Aseprite 用户配置目录的 extensions/aseprite-mcp-live，重启后使用 File > Scripts > MCP: Connect / Settings。从 MCP get_connection_status 或服务 stderr 获取 connection_file 路径，在对话框选择此 JSON 并连接；首次按 Aseprite 权限对话框允许读取配置和回环连接。正式打包/安装验收在 P2。配置文件含临时凭据，不入库、不分享；服务退出后清理。
