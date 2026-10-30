# 实时像素读写与基础绘图

源码 0.6.0 新增；服务与扩展须配套使用。已发布 0.5.1 不包含这些增量。通过 `get_connection_status` 获取 `session_id`，调用 `list_documents` 或 `get_document_info` 获取目标文档、图层及最新修订，再执行编辑或读取。实时操作作用于内存，不自动保存。

## apply_operations

参数：`session_id`、`document_id`、`expected_revision`、非空 `operations`，可选 `expected_context`、`request_id`。一批按顺序执行，全部成功或全部回滚；成功批次一次撤销，收尾刷新一次。

适用普通 RGB 可编辑图层，包含组内普通层；背景、参考、Tilemap、锁定层或锁定祖先不支持。API28 的 Cel 类型时间轴多选无法通过公开 Lua API 无损重建，编辑/保存/历史操作会提前明确拒绝该上下文；清除时间轴 Cel 选择后可继续，read_pixels 不受此限制。坐标为画布坐标，整数且不得越界；帧从 1 开始。绘制不受用户选区限制。RGBA 为四个 0–255 整数，不自动乘图层透明度。

`layer` 使用 `{"kind":"id","value":"l1"}`；同批创建的图层可用 `{"kind":"ref","value":"new"}`，必须先创建再引用。

| op | 必填字段（除 op） | 可选字段 |
|---|---|---|
| create_layer | ref, name | 无 |
| set_opacity | layer, opacity | 无 |
| pixel | layer, x, y, rgba | frame=1 |
| rectangle | layer, x, y, width, height, rgba | frame=1, filled=true |
| pixels | layer, points=[{x,y,rgba},…] | frame=1 |
| write_region | layer, x, y, width, height；pixels 或 runs | frame=1, encoding="rgba", mode="replace" |
| line | layer, x1, y1, x2, y2, rgba | frame=1, thickness=1 |
| ellipse | layer, x, y, width, height, rgba | frame=1, filled=true |
| clear_region | layer, x, y, width, height | frame=1 |

`pixels` 依输入顺序覆盖，重复坐标最后一项生效。`line` 使用 Bresenham 整数直线，包含两端；`thickness` 为方形笔刷边长，偶数宽向右/下多扩展一像素，整条笔刷边界须在画布内。`ellipse` 以矩形内的像素中心判断是否在椭圆内，空心时保留四方向邻居中有任一在椭圆外的边缘像素；不抗锯齿。`clear_region` 将 RGBA 全部清零，空 Cel 也可创建透明区域。

### write_region

区域像素按行优先（从左到右、从上到下）展开，必须正好覆盖 `width*height` 个像素。

- `encoding="rgba"`：提供 `pixels=[[r,g,b,a],…]`，不提供 `runs`。
- `encoding="rle"`：提供 `runs=[{"count":正整数,"rgba":[r,g,b,a]},…]`，不提供 `pixels`。游程可跨行，count 总和必须等于区域面积，不补齐、不截断。
- `mode="replace"`：原样替换，透明像素也覆盖原目标，保留 alpha=0 的 RGB 数值。
- `mode="source_over"`：输入在目标上做直通 alpha 合成，按整数四舍五入；输入 alpha=0 时保留目标原值。忽略图层透明度与混合模式，只修改原始 Cel 像素。

下面的批次创建图层、写入 2×2 图案，再画直线：

```json
[
  {"op":"create_layer","ref":"new","name":"角色"},
  {"op":"write_region","layer":{"kind":"ref","value":"new"},
   "x":2,"y":2,"width":2,"height":2,
   "pixels":[[255,0,0,255],[0,255,0,255],[0,0,255,255],[0,0,0,0]]},
  {"op":"line","layer":{"kind":"ref","value":"new"},
   "x1":2,"y1":5,"x2":7,"y2":5,"rgba":[255,255,255,255]}
]
```

## read_pixels

独立只读工具，参数如下：

```json
{
  "session_id":"会话ID",
  "document_id":"文档ID",
  "expected_revision":3,
  "layer":"图层ID",
  "frame":1,
  "region":{"x":2,"y":2,"width":2,"height":2},
  "encoding":"rgba"
}
```

`frame` 默认 1，`encoding` 默认 `rgba`，也支持 `rle`。注意这里的 `layer` 是 ID 字符串。返回统一 Result，其 `data` 包含 `layer`、`frame`、`region`、`width`、`height`、`encoding`，以及 `pixels` 或 `runs`，格式和 write_region 一致，可用于回写。

读取普通 RGB 图层的原始像素，允许隐藏或锁定层；不合成其他层，不应用图层/Cel透明度、混合模式或选区。区域必须在画布内，Cel 未覆盖或缺失处返回 `[0,0,0,0]`，Cel 偏移会换算为画布坐标。读取不切换活动文档、不刷新、不修改修订、保存状态及撤销历史。显示合成画面仍使用 `get_preview`。

## Cel 复用、预算与兼容

同批同图层同帧使用一份工作图像，预先合并所有操作范围与原 Cel 边界；旧像素仅复制一次，按序绘制后统一赋回。保留画布外旧像素和负 Cel 偏移；不同帧（包括原本关联的 Cel）使用独立工作图像。关联帧使用原生 UnlinkCel 隔离，保留透明度、zIndex、用户数据及其他扩展属性；原生命令内部的解除关联/撤销存储另有成本。

默认最多 256 条操作。绘制工作量与最终 Cel 缓冲面积累计分别受 `max_pixels=262144` 限制：pixel 按 1、pixels 按点数、区域图形按矩形面积，line 按 `(最长轴距离+1)*thickness²` 保守计费。每个 Cel 最终缓冲只计一次，不再按每条操作重复累计副本面积；这不是进程总内存额度。CPU 预算 0.25 秒，覆盖复制、绘制与提交，长循环定期检查。

读取区域同样受像素与 CPU 预算限制；响应预估字节及最终 WebSocket 消息受 `max_message_bytes=8MiB` 限制，预估保守，超限可缩小区域或选择 RLE。错误返回 `LIMIT_EXCEEDED`，写入不自动拆批；回滚后修订可能变化，重试前重新读取文档信息。

协议仍为 v1；新增操作与 read_pixels 仅实时可用，CLI 保留原四操作并明确拒绝新操作。源码服务/扩展为 0.6.0，不与 0.5.1 混用。Windows Aseprite 1.3.7/API28 为验收基线。
