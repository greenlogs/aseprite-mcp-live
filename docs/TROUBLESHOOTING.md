# 故障排查

先查看 MCP 工具的结构化 `error.code/message` 和服务 stderr。`isError=true` 是失败；`RESULT_UNKNOWN` 不能视为“没有执行”。请勿发送含 token 的连接 JSON 或完整 PNG 作为诊断日志。

| 现象 | 原因与处理 |
|---|---|
| Python 版本不满足 / 安装失败 | 运行安装环境 `python.exe --version`，用 `uv venv --python 3.13` 重建专用环境。检查 uv 安装、网络、磁盘权限；用随包 requirements.txt 同步，保留安装错误，不改为未锁版本碰碰运气 |
| CLI 找不到 Aseprite / 无法启动 | 检查客户端 env 的 ASEPRITE_PATH 指向真正的可执行程序，并在终端执行 `& $env:ASEPRITE_PATH --version`。错误包含原始 OS 诊断；Aseprite 本体不随包提供 |
| 服务启动提示端口占用 | 默认端口 0 自动分配；移除固定 ASEPRITE_MCP_PORT 或选择空闲端口，重启客户端服务。启动失败不会自动切换后端 |
| Connection file already exists | 确认旧服务已结束后只移除自己设置的残留文件，或换一个新路径。不删除仍在使用的发现 JSON；默认随机路径通常不会冲突 |
| 无菜单 / 无连接 | 确认扩展目录直接有 package.json，扩展启用并重启；用 core/all 配置启动服务；选择当前状态返回的 JSON；检查读取文件和回环网络权限 |
| NOT_CONNECTED / SESSION_MISMATCH | 读取新状态，在扩展设置重连，再重新 list_documents；旧会话和对象标识失效。不能用旧目标自动重发修改 |
| VERSION_MISMATCH | 配套安装相同版本服务和扩展，协议 v1；状态中的版本应为 0.1.0/API 28。更新软件版本后仍需真实验收，不能假定新版 API 都可用 |
| REVISION_CONFLICT / CONTEXT_CONFLICT | 人工改画、改图层、撤销、切换活动上下文或磁盘被外部修改；重新读取，再由调用者决定新操作，不自动覆盖 |
| INVALID_TARGET | 文档关闭、图层/帧删除或磁盘路径不正确；重新列文档和图层。重名图层必须按 id 定位 |
| TIMEOUT | 排队未发送、只读请求超时或 CLI 子进程已终止；看具体 message。停止大任务或缩小请求；CLI 本次临时目录清理，不清理用户文件 |
| RESULT_UNKNOWN | 发送后断线、UI 繁忙、写入超时或回执失配。先读文档/历史与预览；不要根据超时自动 undo，也不要换 ID 重发。迟到回执不会触发再次写入 |
| LIMIT_EXCEEDED | 缩小批次、Cel 复制范围、预览区域或缩放；事务超预算整批回滚，可重新读取实际修订后调整请求。队列满先等在途请求结束 |
| 保存拒绝 | 未命名文档提供绝对原生 .aseprite/.ase 路径；覆盖现有文件需 overwrite=true。确认目标和权限，保存与像素编辑分开 |
| EXECUTION_FAILED | 查看 Lua/OS/返回码/nonce 回执诊断；退出码 0 或旧输出存在都不是成功。UTF-8 解码失败明确报错，非零退出保留 stderr 或 stdout |
| 客户端没有展示图片 | 确认支持 MCP ImageContent，工具返回 text+image/png；有文字或 base64 不等于实际显示。已验收 SDK 客户端加 HTML 视图，其他客户端需单独确认 |

正常服务退出清理自己的发现文件；Windows MCP SDK 1.6.0 强杀子进程可能留下文件。默认文件名含随机 UUID 防止误复用，不自动遍历临时目录删除残留。运行多个服务时，每个服务有独立发现文件和会话；扩展一次只连接一个。

高级 CLI 工具继承上游部分文本错误与磁盘语义，不具备全部核心事务保障；原始 Lua 仅显式 CLI 开关开放。当前不建议对同一个文件混用实时保存和并发 CLI 写入。测试分层和复现入口见[TESTING](TESTING.md)，公共字段与错误细节见[协议](development/PROTOCOL.md)。
