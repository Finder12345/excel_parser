# CAN Routing Mapping 说明

## 目标

- 从 CAN 路由矩阵中提取源信号到目标通道的路由关系。
- 生成两类结果：
  - `gw_mapping`: 按通道聚合 tx/rx 信号集合
  - `route_info`: 按行记录的细粒度路由明细

## 布局识别建议

- 左侧通常是固定字段区（Signal/PDU/RouteType）。
- 右侧是按通道展开的矩阵列，单元格中出现 `S` / `D` / `S/D`。
- 通道名一般位于矩阵区域上方一行。

## layout_config 最小字段

- `dataContentStartRow`
- `channelNameInfoRow`
- `matrixStartCol`
- `matrixEndCol`
- `identifiers.source_marker`
- `identifiers.destination_marker`
- `identifiers.both_marker`

## 输出示例

```json
{
  "gw_mapping": {
    "CAN1": {"tx": ["SigA"], "rx": ["SigB"]}
  },
  "route_info": [
    {
      "sourceSignalName": "SigA",
      "sourceChannels": ["CAN1"],
      "destinationChannels": ["CAN2"],
      "_row": 12
    }
  ]
}
```
