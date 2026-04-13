# LIN Signal Guide

本模块用于解析 Excel 中的 LIN 信号表，提取帧和信号元数据。

## 先读文件

- `mapping.yaml`：字段定义、sheet 识别规则、分组规则、方向规则、校验规则
- `mapping.md`：字段语义、易错点、LIN 特有规则

## 解析流程

### Step 0: 加载配置

从 `mapping.yaml` 提取：
- `sheet_patterns`
- `parameters`
- `enum_mappings`
- `grouping`
- `direction_config`
- `validation_rules`

### Step 1: 识别 LIN signal sheet

1. 用 `list_sheets()` 获取全部 sheet。
2. 按 `sheet_patterns.include` 选入，按 `sheet_patterns.exclude` 排除。
3. 排除调度表、Legend、变更记录等非信号 sheet。

### Step 2: 判断表头

1. 用 `get_header_sample()` 获取样本。
2. 找到与 `parameters[*].keywords` 匹配数最多的行作为表头。
3. 该模块通常是标准水平表格。

### Step 3: 建立字段映射

1. 用 `get_column_letter_mapping()` 获取 `{列标题 -> 列字母}`。
2. 按 keyword 做精确 / 忽略大小写 / 包含 / 语义匹配。
3. 用 `validate_field_mapping()` 校验覆盖率。
4. 重点字段至少应覆盖：`FrameName`, `ShortName`, `BitPosition`, `BitSize`, `LinId`

### Step 4: 抽取数据

1. 用 `extract_columns_by_mapping()` 批量抽取。
2. 工具会自动跳过全空行和空值率过高的行。
3. 每行会带 `_row_index` 和 `_data_index`。

### Step 5: 类型处理

- 数值字段做必要转换。
- hex 字段保持 Excel 原值。
- 枚举字段保持 Excel 原值，不做自动归一化。

### Step 6: 生成中间结构

1. 用 `build_module_metadata()` 按 `FrameName` 分组。
2. 方向依据 `EcuName` 逐行判断，而不是逐 sheet 判断。
3. 中间 message 会带 `direction`。
4. 写入最终 `TX/RX` 数组前，应移除 `direction`。

### Step 7: 汇总输出

1. 汇总成 `sheet/channel -> TX/RX -> message -> signals`。
2. 最终输出路径：`AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSignal`

## 关键规则

- `FrameName` 是消息分组依据。
- `LinId` 与 `ProtectedId` 必须严格区分。
- `BitSize/SignalLength` 与 `MsgSendType/FrameSendType` 是别名对，需要保持映射一致。
- 枚举字段保持 Excel 原值。
- 最终 message 不保留中间态的 `direction` 字段。
- signal 的 `index` 仅用于 trace 行号回推，最终输出不保留。
