# Windows 安装与使用

首版基线：Windows、Python 3.13+、uv、自己持有的 Aseprite 1.3.7 / API 28。服务与扩展版本均为 0.3.0，内部协议 v1。macOS/Linux 与其他软件版本尚未验收。没有公开下载地址；不要从上游参考仓库下载本项目扩展。

## 准备安装文件

维护者在项目根执行以下命令生成本地候选包，不会发布到网络：

```powershell
uv sync --locked --python 3.13
uv run --locked python scripts/build_release.py --out-dir dist
```

需要 `aseprite_mcp-0.3.0-py3-none-any.whl`、`requirements.txt`、`aseprite-mcp-live-0.3.0.aseprite-extension` 和 `SHA256SUMS`。源码包用于开发复现，不是使用服务的前提。通过 `Get-FileHash -Algorithm SHA256 <文件>` 与摘要清单比对。

## 安装服务

下面所有路径均为示例占位位置，先替换为自己的路径。PowerShell 中执行；安装目录可以位于项目之外，不依赖源码工作目录：

```powershell
uv venv --python 3.13 'C:/Tools/aseprite-mcp/.venv'
uv pip sync --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --require-hashes 'C:/Downloads/aseprite-mcp/requirements.txt'
uv pip install --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --no-deps 'C:/Downloads/aseprite-mcp/aseprite_mcp-0.3.0-py3-none-any.whl'
```

依赖清单由 uv.lock 导出，含锁定版本和哈希，不含开发依赖或本地源码路径。依赖安装需要网络或相应的 uv 缓存。uv 会拒绝不满足 Python 版本的环境；不要用系统旧版 Python 替代新环境。

在支持 stdio 的 MCP 客户端中添加以下配置（具体配置文件位置由客户端决定）：

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "C:/Tools/aseprite-mcp/.venv/Scripts/aseprite-mcp.exe",
      "args": [],
      "env": {
        "ASEPRITE_PATH": "C:/Apps/Aseprite/Aseprite.exe",
        "ASEPRITE_MCP_TOOL_PROFILE": "core"
      }
    }
  }
}
```

也可用同环境 `python.exe` 加 `args: ["-I", "-m", "aseprite_mcp"]`，验收使用这种隔离启动方式。`core` 暴露 9 个实时入口；`cli` 暴露 116 个磁盘工具、不监听实时连接；`all` 为 125 个。原始 Lua 默认关闭，只有明确设置 `ASEPRITE_MCP_ENABLE_RAW_LUA=1` 并启用 CLI 配置才开放。

stdio 服务等待 MCP 客户端输入；不要把正常等待当成启动失败。日志写 stderr，stdout 专用于 MCP。无需先在另一个终端启动第二份服务。默认监听 `127.0.0.1:8765`，扩展自动连接，无需查找或选择 JSON。

## 安装扩展与连接

在 Aseprite 的 Edit > Preferences > Extensions 使用 Add Extension 选择 `.aseprite-extension`，按软件提示安装/启用并重启。这是标准包安装入口；本阶段自动验收采用下述手动安装方式，未自动点击该对话框。

手动安装方式：扩展文件本身是 ZIP，将其解压到当前 Aseprite 配置目录中的 `extensions/aseprite-mcp-live/`，确保该目录直接包含 `package.json`、四个 `.lua`、`LICENSE`、`NOTICE.md`，不能再嵌套一层。Windows 通常在 `%APPDATA%/Aseprite`；便携版可能不同，使用当前软件实际配置位置。隔离验收通过 `ASEPRITE_USER_FOLDER` 指定全新配置目录，没有修改个人配置。只需这两种安装方式之一。

1. 安装并启用配套扩展后，打开 Aseprite 和 MCP 客户端即可；两者启动顺序不限。
2. 首次按 Aseprite 权限提示允许扩展使用本机回环 WebSocket。扩展随后每秒自动等待服务；服务启动后自动连接。
3. 服务重启后扩展直接重新连接、建立新会话。无需查找文件或再次选择 JSON；旧文档/会话 ID 仍然失效，要重新列文档。
4. File > Scripts > MCP: Connect / Settings 可查看状态、设置 Host/Port 和 Connect automatically；默认 `127.0.0.1`、`8765`。Disconnect 会停用自动连接，Apply / Connect 并勾选自动连接可恢复；设置由扩展偏好保存。

状态工具可核对 `connected=true`、`service_version=extension_version=0.3.0`、`connection_mode=direct` 和 API 28，然后取得 `session_id`；它是诊断入口，不再是连接的必需步骤。

## 命令行与多实例

默认无需参数。需要另一个端口时，在 MCP 客户端将启动程序的 args 改为：

```json
["--host", "127.0.0.1", "--port", "8766"]
```

也可直接运行 `aseprite-mcp --host 127.0.0.1 --port 8766`；stdio 仍需由 MCP 客户端驱动。Python 模块入口为 `python -I -m aseprite_mcp --port 8766`。优先级：命令行 → ASEPRITE_MCP_HOST/ASEPRITE_MCP_PORT → 默认值。`localhost` 规范化为 `127.0.0.1`；只允许回环地址 `127.0.0.1` 和 `::1`。

然后在对应 Aseprite 实例的连接设置中把 Port 改为 `8766`。每个服务使用独立端口和会话；同一端口被占用会明确失败，不随机换端口或降级 CLI。同配置目录的多个 Aseprite 进程共用偏好文件，应分别设置对应端口或使用独立配置目录，避免退出时互相覆盖偏好。

连接只使用 Host/Port，通过内存中的 WebSocket 握手建立会话；不创建、读取或选择任何连接 JSON，不需要共享运行目录或配对文件。设置窗口只有地址、端口、自动连接和断开选项，旧的 Legacy JSON 入口已移除。

服务仅监听回环地址，并拒绝网页 http/https/null Origin；允许 Aseprite 原生客户端发送的目标 ws:// Origin 或不带 Origin 的原生连接。此模式没有令牌/共享密钥认证，不能证明本机连接程序的身份；启用扩展表示允许本机端点进行实时编辑，需停止时使用 Disconnect。单编辑器会话、版本校验和目标/修订检查仍保留。

0.3.0 不再使用 `ASEPRITE_MCP_CONNECTION_FILE` 和 `ASEPRITE_MCP_RUNTIME_DIR`，已有值会被忽略；旧文件不会被读取或自动删除。端口必须为1–65535，`--port 0` 明确拒绝。升级时服务与扩展一起更新，选择默认端口即可。

## 第一条创作闭环

使用 `list_documents(session_id)` 找到未保存文档和 `document_id`，再用 `get_document_info` 读取 `revision` 与图层 `id`。把明确文档、当前修订和可选 `expected_context` 传给 `apply_operations`；动作支持新建普通图层、不透明度、像素和矩形，完整字段见[协议](development/PROTOCOL.md)。每个成功批次一次撤销，文档不会因活动窗口切换而换目标。

`get_preview(session_id,document_id,expected_revision,frame=1,scale=8)` 直接返回 PNG 图片内容。`undo/redo` 操作该文档最新历史，可能包含人工编辑；每次操作后使用返回的新修订。新建和编辑不隐式保存；`save_sprite` 要求原生 `.aseprite/.ase` 绝对路径，已有目标须显式 `overwrite=true`，包括原路径。保存不是导出图片。

默认每批最多 256 操作、262144 绘制像素/累计图像副本像素，事务 CPU 预算 0.25 秒；超预算整批拒绝或回滚，不拆成多次提交。预览最多 262144 输出像素、4 MiB PNG；缩小区域或缩放可降低消耗。上限配置见 `.env.example`（源码包中），只在服务启动时读取。

修订冲突或目标关闭时重新读取目标；`RESULT_UNKNOWN` 表示可能已执行，必须先读状态再决定下一步。不要更换 ID 盲重试；同 ID 缓存只在当前会话 120 秒/未被 256 条容量淘汰期间有效。取消调用方不会取消已接收写入。实时断线明确失败，不切换到 CLI。

CLI 只操作磁盘副本。`cli_execute` 的 info 返回 `data.file_revision`，下一次修改应带 `expected_file_revision`，有变化返回冲突。不要对编辑器正在编辑的文件并发 CLI 写入；最终摘要比较与替换存在短竞态。旧高级 CLI 工具尚未全部迁移到新回执/原子提交契约，使用时独占目标文件，不能把它们当成实时工具。

## 升级、卸载与验证

升级先结束客户端中的服务并断开扩展，用新候选的 requirements.txt 同步同一环境，再以 `uv pip install --reinstall --no-deps <新 wheel>` 安装；同时更新扩展整个目录/包并重启 Aseprite。0.1/0.2 升级至 0.3.0 时将旧 port=0 改为8765，并在扩展中启用自动连接；无需保留旧连接文件。旧版本需配套升级。协议不符或提供了不匹配的扩展版本时返回 VERSION_MISMATCH；旧开发扩展未上报版本时状态为 null，应换成配套包。升级后重新列文档，不复用旧 ID。

卸载先从 MCP 客户端移除配置、退出服务，并在 Aseprite 扩展列表卸载/禁用该扩展；手动安装则退出 Aseprite 后仅移除对应 `extensions/aseprite-mcp-live` 目录。服务用 `uv pip uninstall --python <安装环境 python.exe> aseprite-mcp` 卸载。仅当确认环境专用且无其他用途时才移除整个安装环境；不要删除个人画布或 Aseprite 本体。

开发者可按[测试说明](TESTING.md#p2-隔离安装与阶段集成)复现隔离安装验收。候选验收和实际发布状态见[发布说明](RELEASING.md)。
