# NVM Mapping 说明

## 目标

- 解析 NVM 配置 Excel，输出两部分：
  - `common_parameters`: 公共参数区 key-value
  - `blocks`: 每个 NVM Block 的结构化字段

## 结构特征

- 公共参数区通常位于上方，表现为不规则键值对。
- Block 列表区通常位于下方，存在明确表头。

## 识别建议

- 先通过 `get_header_sample()` 找到包含 `Block Name/Block ID/Block Length` 的表头行。
- 表头行以上优先作为公共参数区扫描范围。

## 常见问题

- `Length` 可能有多个列，优先映射与 Block 列表相邻的列。
- 布尔字段可能写成 `Y/N`、`Yes/No`、`1/0`，统一映射到 `true/false`。

## 输出示例

```json
{
  "common_parameters": {
    "NvMBlockBaseNumber": 1,
    "NvMConfigClass": "NVM_API_CONFIG_CLASS_3"
  },
  "blocks": [
    {
      "NvMBlockName": "VehicleConfig",
      "NvMBlockId": 10,
      "NvMNvBlockLength": 64
    }
  ]
}
```
