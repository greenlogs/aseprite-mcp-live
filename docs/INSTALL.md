# Windows 安装与使用

首版基线：Windows、Python 3.13+、uv、自己持有的 Aseprite 1.3.7 / API 28。服务与扩展版本均为 0.1.0，内部协议 v1。macOS/Linux 与其他软件版本尚未验收。没有公开下载地址；不要从上游参考仓库下载本项目扩展。

## 准备安装文件

维护者在项目根执行以下命令生成本地候选包，不会发布到网络：

```powershell
uv sync --locked --python 3.13
uv run --locked python scripts/build_release.py --out-dir dist
```

需要 `aseprite_mcp-0.1.0-py3-none-any.whl`、`requirements.txt`、`aseprite-mcp-live-0.1.0.aseprite-extension` 和 `SHA256SUMS`。源码包用于开发复现，不是使用服务的前提。通过 `Get-FileHash -Algorithm SHA256 <文件>` 与摘要清单比对。

## 安装服务

下面所有路径均为示例占位位置，先替换为自己的路径。PowerShell 中执行；安装目录可以位于项目之外，不依赖源码工作目录：

```powershell
uv venv --python 3.13 'C:/Tools/aseprite-mcp/.venv'
uv pip sync --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --require-hashes 'C:/Downloads/aseprite-mcp/requirements.txt'
uv pip install --python 'C:/Tools/aseprite-mcp/.venv/Scripts/python.exe' --no-deps 'C:/Downloads/aseprite-mcp/aseprite_mcp-0.1.0-py3-none-any.whl'
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

stdio 服务等待 MCP 客户端输入；不要把正常等待当成启动失败。日志写 stderr，stdout 专用于 MCP。无需先在另一个终端启动第二份服务。监听默认回环地址和随机端口，不需要固定端口。

## 安装扩展与连接

在 Aseprite 的 Edit > Preferences > Extensions 使用 Add Extension 选择 `.aseprite-extension`，按软件提示安装/启用并重启。这是标准包安装入口；本阶段自动验收采用下述手动安装方式，未自动点击该对话框。

手动安装方式：扩展文件本身是 ZIP，将其解压到当前 Aseprite 配置目录中的 `extensions/aseprite-mcp-live/`，确保该目录直接包含 `package.json`、四个 `.lua`、`LICENSE`、`NOTICE.md`，不能再嵌套一层。Windows 通常在 `%APPDATA%/Aseprite`；便携版可能不同，使用当前软件实际配置位置。隔离验收通过 `ASEPRITE_USER_FOLDER` 指定全新配置目录，没有修改个人配置。只需这两种安装方式之一。

1. 在 MCP 客户端调用 `get_connection_status`，取得 `connection_file` 路径；也可从服务 stderr 查看该路径。
2. 在 Aseprite 的 File > Scripts > MCP: Connect / Settings 选择这个 JSON 文件并点击 Connect。
3. 首次运行按 Aseprite 权限提示允许扩展读取连接文件和使用本机 WebSocket；成功后显示 Connected。
4. 再读状态，确认 `connected=true`、`service_version=extension_version=0.1.0`、`api_version=28`，并取得新 `session_id`。

发现 JSON 含临时凭据，不上传或分享。默认路径带 PID 和随机 UUID，每次服务启动重新选取；扩展只记住文件路径。客户端重启服务后重新选择当前文件并连接；不自动复用旧会话。固定路径可用 `ASEPRITE_MCP_CONNECTION_FILE` 设置，但必须在启动前不存在，且父目录存在；强杀残留处理见[故障排查](TROUBLESHOOTING.md)。

## 第一条创作闭环

使用 `list_documents(session_id)` 找到未保存文档和 `document_id`，再用 `get_document_info` 读取 `revision` 与图层 `id`。把明确文档、当前修订和可选 `expected_context` 传给 `apply_operations`；动作支持新建普通图层、不透明度、像素和矩形，完整字段见[协议](development/PROTOCOL.md)。每个成功批次一次撤销，文档不会因活动窗口切换而换目标。

`get_preview(session_id,document_id,expected_revision,frame=1,scale=8)` 直接返回 PNG 图片内容。`undo/redo` 操作该文档最新历史，可能包含人工编辑；每次操作后使用返回的新修订。新建和编辑不隐式保存；`save_sprite` 要求原生 `.aseprite/.ase` 绝对路径，已有目标须显式 `overwrite=true`，包括原路径。保存不是导出图片。

默认每批最多 256 操作、262144 绘制像素/累计图像副本像素，事务 CPU 预算 0.25 秒；超预算整批拒绝或回滚，不拆成多次提交。预览最多 262144 输出像素、4 MiB PNG；缩小区域或缩放可降低消耗。上限配置见 `.env.example`（源码包中），只在服务启动时读取。

修订冲突或目标关闭时重新读取目标；`RESULT_UNKNOWN` 表示可能已执行，必须先读状态再决定下一步。不要更换 ID 盲重试；同 ID 缓存只在当前会话 120 秒/未被 256 条容量淘汰期间有效。取消调用方不会取消已接收写入。实时断线明确失败，不切换到 CLI。

CLI 只操作磁盘副本。`cli_execute` 的 info 返回 `data.file_revision`，下一次修改应带 `expected_file_revision`，有变化返回冲突。不要对编辑器正在编辑的文件并发 CLI 写入；最终摘要比较与替换存在短竞态。旧高级 CLI 工具尚未全部迁移到新回执/原子提交契约，使用时独占目标文件，不能把它们当成实时工具。

## 升级、卸载与验证

升级先结束客户端中的服务并断开扩展，用新候选的 requirements.txt 同步同一环境，再以 `uv pip install --reinstall --no-deps <新 wheel>` 安装；同时更新扩展整个目录/包并重启 Aseprite。协议不符或提供了不匹配的扩展版本时返回 VERSION_MISMATCH；旧开发扩展未上报版本时状态为 null，应换成配套包。升级后重新列文档，不复用旧 ID。

卸载先从 MCP 客户端移除配置、退出服务，并在 Aseprite 扩展列表卸载/禁用该扩展；手动安装则退出 Aseprite 后仅移除对应 `extensions/aseprite-mcp-live` 目录。服务用 `uv pip uninstall --python <安装环境 python.exe> aseprite-mcp` 卸载。仅当确认环境专用且无其他用途时才移除整个安装环境；不要删除个人画布或 Aseprite 本体。

开发者可按[测试说明](TESTING.md#p2-隔离安装与阶段集成)复现隔离安装验收。候选验收和实际发布状态见[发布说明](RELEASING.md)。
