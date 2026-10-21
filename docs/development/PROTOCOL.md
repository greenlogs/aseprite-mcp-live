# 协议 v1 与执行接口（P0-M2 冻结）

实施位置：`aseprite_mcp/core/protocol.py` 为类型及校验唯一来源；`config.py` 为运行上限，`execution.py` 为路由、会话及去重，`backends/cli.py` / `cli.lua` 为真实磁盘适配器，`server.py` 为 MCP 暴露。可校验[样例](protocol-v1.examples.json)，由 `tests/test_protocol.py` 持续验收。

## 当前实现与后续实现

P0 已实现类型、认证/协商函数、执行接口、单会话路由、去重、CLI 纵向路径和 stdio MCP。`Backend` 提供 `capabilities: frozenset[str]` 与 `async execute(Request) -> Result`。公共入口为 `Executor.execute(JSON str/bytes) -> Result`，业务参数经严格 JSON 校验；未知字段、错误类型均拒绝。

P0 当时没有 WebSocket listener、Lua 扩展或真实实时编辑后端；P1 已真实实现连接、文档/事务及图片。P1 在 `create_server` 生命周期把实际连接的 Backend 绑定同一个 Executor；禁止另起无法被工具访问的 Executor。实时工具已接通；没有编辑器时返回 `NOT_CONNECTED`，状态工具返回 `connected: false`。P0 对实时修订、断连及超时仅模拟错误契约，真实实现和验证在 P1。

## 传输、握手与对象

MCP 使用 stdio；内部消息每个 WebSocket text frame 对应一个 UTF-8 JSON 对象，不使用 JSON-RPC 或二进制图片帧。内部监听只允许 `127.0.0.1` / `::1`，默认端口 0（由系统分配，P1 显示实际端口）；每次启动 `RuntimeConfig` 产生 32 随机字节的 token，不写入日志/来源文件。P1 提供本机配置入口给扩展，不把示例 token 用于真实启动。

扩展先发 `Handshake`：`type: hello`、`protocol_version: 1`、`token`、新 `session_id`、`aseprite_version`、`api_version`、`capabilities`。`negotiate` 比较 token、拒绝版本不符或 API < 28，返回与核心能力的交集。扩展仍需实际探测 API，版本号不证明每项能力可用。

服务器回 `Welcome`：`type: welcome`、协议版本、原 session_id、已协商能力及完整 Limits 默认值。握手失败返回统一 Result 错误（`request_id: null`）并关闭；P1 负责线上的收发和握手超时。第二个活动会话明确拒绝。重连创建新会话，旧文档/图层标识一律失效。

实时文档/图层标识是扩展分配的不透明字符串，最大 128 字符，不使用名称或新版持久 UUID。文档关闭、图层删除即失效，重名/改名不改变标识。文档内容 `revision` 从 0 单调递增，人工编辑、撤销、重做都更新；活动文档/帧/图层/选区变更更新单独的 `context_revision`，标识不能因用户切换活动文档而重定向。具体事件监听由 P1 实现。

CLI `target` 是 `{backend: cli, path: 绝对磁盘文件路径}`。CLI 不接受实时修订和上下文。图层 `id` 是本次磁盘树的 1 起始索引路径，如 `1`、`2/1`；只用于这一文件结构，不保证外部结构编辑后仍有效。实时标识不能用于 CLI。CLI 读入和提交之间检测源文件 SHA-256 变化并拒绝覆盖；这不提供对外部编辑器的文件锁，文件检查与原子替换之间仍有短竞态窗口。

## 请求、结果与错误

Request：`protocol_version` 默认 1；`request_id` 必填；`target` 必填；`action` 为按 `name` 区分的联合类型；可选 `expected_revision` / `expected_context` 为非负整数。

| action.name | 参数与目标 |
|---|---|
| list_documents | live 会话目标，不带 document_id |
| create_sprite | live 会话目标；width、height > 0；RGB，不保存 |
| get_document_info | live 文档目标，或 CLI 文件目标 |
| apply_operations | live 文档或 CLI 文件目标；operations 非空 |
| get_preview | live 文档；frame 默认 1、scale 默认 1（1–64）；可选 region `{x,y,width,height}` |
| save_sprite | live 文档；path 可省略（未命名文档必须提供），overwrite 默认 false |
| undo / redo | live 文档；执行最新历史动作 |

除 list/create 外，live 请求必须带 document_id；编辑、预览、保存、撤销/重做必须带 expected_revision。元数据读取返回当前修订；内容操作执行前由后端再次检查修订。expected_context 可选，若提供，依赖的活动状态不符必须拒绝。CLI 适配器只支持 info/apply，其余返回能力不支持。

Result：`protocol_version`、`request_id`（畸形请求可为 null）、`ok`、实际 `target`、`revision`、`context_revision`、`data`、`error`。成功不带 error；失败必须带 `{code,message}` 且不带成功 data。请求/响应 id 或目标不匹配视为 RESULT_UNKNOWN。未取得目标当前修订时 revision 为 null，不伪造 0。

info 的 data 提供 width、height、color_mode、frames 数量、layers（id/name/is_group/opacity/visible）、aseprite_version 和 api_version；实时实现还需提供 document_id、active、saved、path、帧时长及上下文信息。list 的 data 为 documents 列表及 active_document_id；create 为新 document_id 与基本信息；apply 为 layer_refs 映射及变更统计；save 为实际 path；undo/redo 为 applied 与实际修订。实时字段的填充在 P1 验证，不能用 CLI 结果冒充实时对象。

| 错误码 | 含义 |
|---|---|
| INVALID_REQUEST / LIMIT_EXCEEDED | 格式、取值、越界 / 上限 |
| VERSION_MISMATCH / SESSION_MISMATCH | 协议不兼容 / token、旧会话或第二连接 |
| NOT_CONNECTED | 没有编辑器连接，禁止回退磁盘 |
| INVALID_TARGET | 文档/图层/帧失效、CLI 文件不存在或非绝对路径 |
| REVISION_CONFLICT / CONTEXT_CONFLICT | 内容修订 / 活动上下文或磁盘文件发生变化 |
| UNSUPPORTED_CAPABILITY | 协商未支持、CLI 未实现、非普通 RGB 绘制目标 |
| EXECUTION_FAILED | 明确执行失败、Lua 异常、缺少回执或本次产物 |
| TIMEOUT | CLI 被终止，或实时只读请求超时 |
| RESULT_UNKNOWN | 实时变更超时/断连/无匹配确认，可能已经发生 |
| REQUEST_CONFLICT | 同一 request_id 携带不同请求 |

公共执行错误和新增 MCP 核心/cli_execute 工具使用结构化错误，MCP 通过 ToolError 转成 `isError: true`。为保留上游调用兼容，115 个旧 CLI 工具仍返回原来的文本结果；它们尚未全部迁移到公共执行层，不承诺具备新适配器的回执/原子提交保证，P3 按清单迁移。

## 批次、坐标和传参

坐标从 (0,0) 起，画布坐标，帧从 1 起，RGBA 必须显式给四个 0–255 整数。新图层默认普通图层/不透明度 255；设置 opacity 也是 0–255。

- create_layer：`{op, ref, name}`；ref 在批次内唯一。
- set_opacity：`{op, layer, opacity}`。
- pixel：`{op, layer, frame=1, x, y, rgba}`。
- rectangle：pixel 字段加 `width,height,filled=true`。

layer 结构为 `{kind: id（默认）或 ref, value: 标识}`。ref 只能指向本批先前的 create_layer；不得前向引用或重复定义。真实图层 id 在成功 data.layer_refs 返回。完整批次先校验再事务执行；越界拒绝，不裁剪、不自动拆批。描边矩形也按整个矩形面积保守计算像素预算。

CLI `cli.lua` 是固定脚本，参数写入 UTF-8 JSON 文件，经 `--script-param` 传路径，由 `json.decode` 加载，无新增 Lua 参数字符串插值。目标为 RGB 可编辑普通图层；索引/灰度、组、参考、Tilemap、背景、锁定目标拒绝。图像在副本上修改后赋回 cel.image，处理 Cel 偏移与空 Cel；先存入唯一临时 .aseprite 产物，Python 核对随机 nonce 回执、数据、格式头和源文件摘要后原子替换。退出 0、旧输出存在或仅有 stdout 均不能证明成功。临时目录在成功/失败后清理。

实时事务不能照搬 CLI saveAs；一个成功编辑批次一次撤销，保存独立。协议不允许任意 Lua 或外部副作用进入批次。CLI 工具在受控线程运行，subprocess.run 带超时并清理本次子进程，不阻塞 MCP 事件循环。

## PNG 传输

get_preview 的成功 data 包含 `png: PngPayload`：mime_type 固定 image/png，encoding 固定 base64，data 为无 data-URI 前缀的 base64，width/height 为输出图片尺寸，frame、scale、可选 region 为源画布区域。外层 Result 关联目标和实际 revision。PngPayload.decode 检查体积、PNG 内容和尺寸，禁止返回本地路径替代图片。

P1-M3 已校验 PNG 并包装为 MCP ImageContent，文字元数据与图片一起返回，文字中不重复 base64。scale 为整数最近邻，region 全部在画布内；完整画布或缩放后像素超限时后端必须拒绝。读取/预览不得修改源文档、活动上下文或历史。

## 上限和去重

均可用 `ASEPRITE_MCP_` 加大写字段名配置，严格正值；实例在启动时固定。默认是小批像素编辑的保守起点，没有宣称性能调优结果，P2 依据真实耗时调整。

| Limits 字段 | 默认 | 依据 |
|---|---|---|
| max_message_bytes | 8 MiB | 容纳 4 MiB PNG 的 base64 与元数据，限制单消息内存 |
| max_operations | 256 | 限制 UI 一次事务工作量 |
| max_pixels | 262144（512×512） | 单批绘制、画布创建与预览输出预算 |
| max_png_bytes | 4 MiB | 限制编码图像传输体积 |
| timeout_seconds | 30 | 防止 CLI 挂起；不表示编辑 30 秒可接受 |
| dedup_entries | 256 | 限制会话结果缓存数量 |
| dedup_ttl_seconds | 120 | 提供短期确认重试窗口 |

Executor 串行执行，缓存相同 ID/相同请求的最终结果（包括已确认失败和结果未知），同 ID 不同内容拒绝。在 TTL 内且未被容量淘汰时返回缓存，不重复操作；断开清缓存，新会话不复用旧 id。TTL/淘汰后的请求没有去重保证，因此 RESULT_UNKNOWN 后必须先刷新文档状态，不盲目重发。核心变更 MCP 工具可显式传 request_id；省略时服务器生成 UUID。WebSocket 传输重试必须保留同一 id，不能重新生成。P1 扩展也需有对应去重与最终结果确认，Python 缓存不能替代真实编辑端防重。

## P1-M2 结果细化

实时 info/list 字段已实现；selection 为 bounds 与 empty，active_frame 从 1 起。revision 是内容事件计数，回滚也可能推进，不能当作批次数；context_revision 独立。apply 无新图层时可省略 layer_refs；undo/redo applied=false 表示没有收到历史变更事件。save 仅原生 .aseprite/.ase 绝对路径，存在目标无论是否原路径都需 overwrite=true；不能用保存工具隐式导出图片。

## P1-M3 图片实现

扩展按 v1 data.png 发送 base64；MCP 层返回 TextContent(Result 元数据、png 去掉 data 字段) 与 ImageContent(image/png) 两块。PNG region 填实际区域，完整画布也显式给出原点/尺寸。Lua 内存编码采用存储型 deflate，事先以行字节数和块开销估算体积；消息预留 2048 字节元数据开销，因此很小的自定义消息上限可能提前拒绝。无需临时文件，不改变文档、上下文或历史。
