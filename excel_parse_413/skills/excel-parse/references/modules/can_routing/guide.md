# CAN Routing Guide

本模块用于解析 CAN 路由矩阵，提取源/目的通道和路由关系。

## 先读文件

- `mapping.yaml`：sheet 规则、字段定义、矩阵标记规则
- `mapping.md`：矩阵布局识别建议、layout_config 最小要求、输出示例

## 流程

1. 用 `list_sheets()` 找到候选 routing sheet。
2. 用 `get_header_sample()` / `sheet_to_column_json()` 分析整体布局。
3. 识别左侧字段区与右侧矩阵区，构建 `layout_config`。
4. 用 `build_routing_metadata()` 扫描矩阵，得到 `gw_mapping` 与 `route_info`。
5. 用 `finalize_routing_metadata()` 完成后处理，生成最终兼容结构。

## 关键规则

- 左侧是固定字段区：如 sourceSignalName、PDU、routeType。
- 右侧是按通道展开的矩阵区，单元格里通常是 `S` / `D` / `S/D`。
- `finalize_routing_metadata()` 是必需步骤，不可跳过。
- 最终输出包含 `routing_result` 和 `pdur_result`。
- 输出路径：`AUTOSAR.RequirementsData.CommunicationStack.GateWayConfiguration`

## 特殊注意

- `routeType` 与最终 `routingType` 的命名对齐在 finalize 阶段完成。
- 一源多目的归并、target 去重、pdur 分流都在 finalize 阶段完成。
- 该模块不是标准列式表，不能直接套标准抽列流程。
