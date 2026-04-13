# CAN Signal Guide

本模块用于解析 Excel 中的 CAN 信号表，提取报文和信号元数据。

## 先读文件

- `mapping.yaml`：字段定义、sheet 识别规则、分组规则、方向规则、校验规则
- `mapping.md`：字段语义、易错点、兼容性说明

## 解析流程

### Step 0: 加载配置

从 `mapping.yaml` 提取：
- `sheet_patterns`
- `parameters`
- `enum_mappings`
- `grouping`
- `direction_config`
- `signal_defaults`
- `validation_rules`

### Step 1: 识别 CAN signal sheet

1. 用 `list_sheets()` 获取全部 sheet。
2. 按 `sheet_patterns.include` 选入，按 `sheet_patterns.exclude` 排除。
3. 排除优先。
4. 同时从 sheet 名推断：
   - `Tx_XXX` → `channel_name=XXX`, `direction=TX`
   - `Rx_XXX` → `channel_name=XXX`, `direction=RX`
   - 无前缀 → `channel_name=sheet_name`, `direction` 留空，后续由 `EcuName` 回退判断

### Step 2: 判断表头

1. 用 `get_header_sample()` 获取样本。
2. 找到与 `parameters[*].keywords` 匹配数最多的行作为表头。
3. 一般为水平表格。

### Step 3: 建立字段映射

1. 用 `get_column_letter_mapping()` 获取 `{列标题 -> 列字母}`。
2. 用 `mapping.yaml.parameters[*].keywords` 与列标题做匹配：
   - 精确匹配
   - 大小写不敏感
   - 包含匹配
   - 语义推断
3. 用 `validate_field_mapping()` 验证映射完整性。
4. 必填字段至少应覆盖：`MsgName`, `MsgId`, `ShortName`, `BitPosition`, `BitSize`

### Step 4: 抽取数据

1. 用 `extract_columns_by_mapping()` 批量抽取。
2. 工具会自动跳过全空行和空值率过高的行。
3. 每行会带 `_row_index` 和 `_data_index`。

### Step 5: 类型处理

- 数值字段做必要转换。
- hex 字段保持 Excel 原值。
- 枚举字段保持 Excel 原值，不做自动归一化。

### Step 6: 生成中间结构

1. 用 `build_module_metadata()` 按 `MsgName` 分组。
2. 有 `Tx_/Rx_` 前缀时，方向已由 sheet 名确定。
3. 无前缀时，再按 `EcuName` 回退判断 TX/RX。
4. 这一步输出仅是中间结构，不能直接作为最终结果。

### Step 7: 重组为最终 CAN message 结构

根据原始 CAN 输出语义继续重组：
- message 应落到 `TX` / `RX` 数组中
- 最终 message 不保留 `direction` 字段
- 补充 `group_ref`
- 补充信号默认值字段
- 保留信号 `index`

### Step 8: 按通道汇总

1. 将同一通道的 Tx/Rx sheet 合并为同一个 channel 对象。
2. 兼容 RT1/RT2 rollback 特殊合并逻辑。
3. 使用 `finalize_can_metadata()` 统一补 `group_ref`、补 signal 默认字段并移除 message `direction`。
4. 最终输出路径：`AUTOSAR.RequirementsData.CommunicationStack.Can`

## 关键规则

- `MsgName` 是消息分组依据。
- 同一 channel 下的 `Tx_CAN1` / `Rx_CAN1` 必须合并。
- 枚举字段保持 Excel 原值。
- `group_ref` 属于 design trace 字段，不直接来自 Excel。
- 最终 message 不能直接复用通用中间结构原样输出。
