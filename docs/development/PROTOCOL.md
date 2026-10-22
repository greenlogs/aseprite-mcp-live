# 协议v1与执行接口

当前服务/扩展0.4.1。业务Request/Result维持v1；hello已移除token，原0.1/0.2发现文件和认证握手必须配套升级。模型唯一来源core/protocol.py；[可校验样例](protocol-v1.examples.json)由test_protocol验证。实际架构见[ARCHITECTURE](ARCHITECTURE.md)，历史契约见各版本交接，不用于当前安装。

## 连接与握手

MCP客户端使用stdio；Python与扩展使用回环WebSocket text消息，每帧一个UTF8 JSON对象，图片编码在成功Result中，不使用二进制帧。默认127.0.0.1:8765，--host/--port > ASEPRITE_MCP_HOST/PORT > 默认；localhost规范化IPv4回环，另支持::1，端口1–65535，端口0/非回环明确拒绝。

扩展直接连接配置地址，不创建/读取连接JSON、运行目录、token、配对文件；旧CONNECTION_FILE/RUNTIME_DIR环境不读取。设置无选文件入口。仅允许无Origin或目标原生ws://Origin，普通http/https/nullOrigin在HTTP握手拒绝403。没有共享密钥认证，来源限制、版本检查均不证明本机程序身份；用户启用扩展表示允许该本机端点实时编辑，可Disconnect停用。

hello：`{type:"hello",protocol_version:1,session_id,aseprite_version,api_version,extension_version?,capabilities}`。标识非空且最长128字符；版本字段严格类型。protocol不等于1或提供的extension_version不等于服务版本为VERSION_MISMATCH，api<28为UNSUPPORTED_CAPABILITY。未知能力忽略，协商取核心能力加显式启用能力集与编辑器能力的交集。旧hello含token等多余字段拒绝INVALID_REQUEST；不悄悄跳过旧认证。

welcome：`{type:"welcome",protocol_version:1,session_id,capabilities,limits}`。握手失败发送Result（request_id=null）后关闭。第二个活动编辑器拒绝SESSION_MISMATCH；每个socket OPEN新会话，断开清实时注册与缓存，旧文档/图层ID不复用。negotiate(hello,capability_sets=frozenset())、Executor.attach_live(backend,hello)不接收token。

传输保活：扩展Timer每秒发`{"type":"ping"}`，服务回`{"type":"pong"}`，均不作为业务请求或去重回执；5秒无回应或socket CLOSE/ERROR释放旧socket，由下一Timer tick重新连接。等待OPEN也受此期限；手动停止关闭Timer/socket，自动恢复需在设置中启用。保活不重发业务修改、不将未知结果变成功。

状态工具返回connected/session_id/service_version/extension_version/protocol_version/capabilities/enabled_capability_sets/aseprite_version/api_version/url，以及`connection_mode:"direct"`、`authentication:"none"`；没有connection_file或automatic_discovery。

## 目标、修订和公共入口

Backend提供`capabilities:frozenset[str]`及`async execute(Request)->Result`，公共执行入口`Executor.execute(JSON str/bytes)->Result`。协议层不导入后端。实时断线禁止静默转CLI。

live目标`{backend:"live",session_id,document_id?}`；list/create不能带document_id，其余文档动作必须明确指定。标识为会话注册的不透明字符串，不使用名称唯一或依赖新版UUID；删除图层、关闭文档即失效。revision为内容事件计数，人工编辑/撤销/重做/回滚也可能推进；context_revision独立跟踪活动图层/帧/选区/命令。不能假定每个批次revision只+1。

cli目标`{backend:"cli",path:绝对磁盘路径}`；仅支持info/apply，不接受实时修订或上下文。图层id为本次磁盘树1起始索引路径，如1、2/1，不保证外部改结构后有效，不能用实时id代替。

Request字段：protocol_version默认1，request_id必填，target必填，action按name区分严格联合；expected_revision/expected_context可选非负整数；expected_file_revision可选64位小写SHA256，仅CLI。

| action.name | 参数和语义 |
|---|---|
| list_documents | live会话，无document_id；返回documents及active_document_id |
| create_sprite | live会话，width/height>0；RGB未保存文档 |
| get_document_info | live文档或CLI文件；返回当前信息/修订 |
| apply_operations | live文档或CLI文件，operations非空；live须expected_revision |
| get_preview | live文档，expected_revision，frame默认1，scale整数1–64，可选region{x,y,width,height} |
| save_sprite | live文档，expected_revision，path可省略（未命名需给绝对路径），overwrite默认false |
| undo/redo | live文档，expected_revision；作用于最新历史，可能包括人工编辑 |

编辑、预览、保存、历史在实际执行前再核对修订，expected_context若提供也必须匹配；可显式定位原文档的动作不因活动文档切换而漂移。CLI info/apply成功data.file_revision返回摘要，后续编辑应携带expected_file_revision；不传保持老调用，但只检查执行期间变化。最终摘要比较与替换仍有外部进程短竞态，不能同时用CLI写编辑器正在保存的同一文件。

<a id="p2-m1-故障与兼容补充"></a>
## 结果与错误

Result：protocol_version、request_id（坏请求可null）、ok、target、revision、context_revision、data、error。成功无error，失败必须error{code,message}且data=null；未知当前修订用null，不伪造0。后端回执ID/目标不匹配为RESULT_UNKNOWN。MCP失败同时isError=true和JSON Result；ContractServer解包SDK1.6.0额外文本前缀，参数校验错误映射INVALID_REQUEST。

| 错误码 | 含义 |
|---|---|
| INVALID_REQUEST / LIMIT_EXCEEDED | 参数/取值/越界错误或消息/队列/批次预算超限 |
| VERSION_MISMATCH | 协议或提供的扩展版本不匹配 |
| SESSION_MISMATCH / NOT_CONNECTED | 旧会话或第二活动编辑器 / 未连接 |
| INVALID_TARGET | 内存对象失效，磁盘路径不存在或不是绝对路径 |
| REVISION_CONFLICT / CONTEXT_CONFLICT | 文档内容/活动上下文或磁盘文件变化 |
| UNSUPPORTED_CAPABILITY | 协商不支持、非普通可编辑RGB图层或CLI不支持动作 |
| EXECUTION_FAILED | Lua/OS/解码失败、非零退出、缺少nonce回执/新产物 |
| TIMEOUT | 排队未发送、实时只读超时或CLI超时进程已终止 |
| RESULT_UNKNOWN | 实时写入发送后断线/超时/没有匹配确认，可能已经发生 |
| REQUEST_CONFLICT | 相同request_id携带不同内容 |

info返回尺寸、color_mode、frames、layers、软件/API版本；实时另有document_id、saved/path/modified、active、帧时长、活动帧/图层、selection{empty,x,y,width,height}和修订。create返回新文档信息；apply返回operations和可选layer_refs；save返回实际path；undo/redo返回applied（无事件时false）和修订。PNG结果见后文。

## 批次、历史与保存

坐标为画布坐标、帧1起始，RGBA四个0–255整数。layer引用为`{kind:"id"或"ref",value}`，默认id；ref只能引用同批前序create_layer，不能重复或前向引用。

- create_layer：op/ref/name，新建普通图层。
- set_opacity：op/layer/opacity，0–255。
- pixel：op/layer/frame默认1/x/y/rgba。
- rectangle：pixel加width/height/filled默认true，描边也按矩形面积保守预算。

完整批次先校验，真实app.transaction内用Cel图像副本赋回支持撤销，任一支持操作失败整批回滚，一个成功批次一次撤销。累计绘制面积、逐次Cel副本面积和CPU预算；超限拒绝/回滚，不拆批。保存/导出/网络/任意Lua不进入批次。临时切换活动目标后恢复可恢复上下文。

保存仅原生.aseprite/.ase绝对路径，未命名必须给path，存在的目标（包括原路径）须overwrite=true。不隐式保存；图片导出和CLI磁盘操作不搬入实时编辑。索引/灰度、参考/Tilemap/背景/锁定或祖先锁定图层编辑拒绝。

CLI固定Lua从临时业务参数JSON加载（不是连接配置），产物先存同卷临时文件，匹配nonce、回执字段、格式头/文件摘要再os.replace。退出0或旧文件存在不证明成功。CLI及旧MCP工具在线程执行共享路径锁，超时清理本次进程/临时资源；Windows输出捕获bytes再严格UTF8解码，非零退出保留证据。旧高级工具参数/成功文本保留，常见失败转JSON/isError，但尚未迁移全部事务/回执契约，P3按清单处理。

## PNG内容

get_preview成功data.png为`{mime_type:"image/png",encoding:"base64",data,width,height,frame,scale,region}`。region为实际源画布区域，width/height为缩放输出。独立RGB Image.drawSprite合成，内存PNG使用存储型deflate/CRC32/Adler32，整数最近邻；先估算字节/像素再分配，编码后复核。Python验证base64/PNG/尺寸与预算。

MCP返回TextContent（Result元数据，png去掉data）和ImageContent(image/png)，文字不重复base64；不能以本地路径代替图像。预览不修改源文档、活动上下文或历史，不产生磁盘中间文件。收到ImageContent与客户端实际显示需分别验收。

## 上限、取消与去重

Limits启动时固定，环境名ASEPRITE_MCP_加大写字段名，全部正值：

| 字段 | 默认 |
|---|---|
| max_message_bytes | 8MiB |
| max_operations | 256 |
| max_pixels | 262144（绘制/累计图像副本/创建/预览输出） |
| max_png_bytes | 4MiB |
| max_batch_seconds | 0.25秒实时事务CPU预算 |
| timeout_seconds | 30秒 |
| dedup_entries | 256（也限制不同ID在途队列） |
| dedup_ttl_seconds | 120秒 |

Executor按实时会话/规范化磁盘路径独立排队。调用方取消只取消等待，已接收任务由shield保护直到确认，执行中同ID合并，不同内容立即拒绝；排队超时明确未发送。缓存最终结果（含失败和结果未知），同ID同内容在TTL内且未淘汰时直接返回，扩展也保留会话去重。断开清实时缓存，不清CLI回执；旧会话完成不污染新缓存。TTL/容量/重连后无去重保证，RESULT_UNKNOWN必须先读状态再决定，不换ID盲重发。迟到回执丢弃，不自动undo或重试修改。

## P3 可选动画增量（0.4.0）

业务协议仍v1；服务/扩展配套0.4.0，未匹配版本明确拒绝。RuntimeConfig.capability_sets与Executor同名关键字默认空，环境ASEPRITE_MCP_CAPABILITY_SETS仅识别animation，未知组启动失败。核心八动作不变；LiveBackend知道可选apply_animation，但仅双方握手且服务启用时路由。默认工具9/116/125，启用后core/all为10/126，CLI仍116；公共CLI不支持该动作，无降级。

apply_animation要求显式文档、expected_revision，可选expected_context与request_id；operations非空，数量受max_operations限制。严格模型额外字段拒绝；数字不接受bool/字符串。

| op | 字段 |
|---|---|
| add_frames | count 1–255，duration_ms默认100；末尾复制最后帧，操作后总帧数≤256 |
| delete_frame | frame≥1且存在；不得删除唯一帧 |
| set_frame_duration | from_frame/to_frame从1开始、闭区间，duration_ms 1–65535整数 |
| set_tag | tag长度1–256，from_frame/to_frame闭区间，direction默认forward，可为reverse/pingpong/pingpong_reverse |
| delete_tag | tag精确名称，缺失或重名INVALID_TARGET |

先模拟顺序帧数/标签存在性并验证预算，再一个app.transaction执行。原生删帧可调整/删除标签；若后续操作因此失效，整个事务回滚。复制预算采用每层最大Cel面积乘追加帧数保守累计，CPU预算超限也回滚；不拆批。RGB普通可编辑层和组受支持，锁层/背景/参考/Tilemap/灰度/索引拒绝。运行时探测AniDir与Sprite方法，不把新版API存在当作API28可用证据。

成功data为operations/frames/frame_durations_ms/tags，tag条目name/from_frame/to_frame/direction。get_document_info也增补frame_durations_ms和tags，原frame_durations秒数组保留。sync补充时间轴指纹，帧时长/标签变化即使没有change事件也使旧revision失效。所有成功写入使用新revision；未知写入同核心返回RESULT_UNKNOWN。

临时目标切换恢复原活动文档/层/帧；删除原活动帧时恢复到存活帧，原帧号超过末帧则取末帧。未启用时扩展仍可报告只读动画元数据，但不接受动画写入。完整范围与逐工具矩阵见[能力清单](CAPABILITIES.md)。
