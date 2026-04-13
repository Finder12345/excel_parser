# CAN 信号表字段映射参考

本文档是 `can_signal_mapping.yaml` 的配套说明，为 Agent 提供 **推理指引**。
Agent 应先读取 yaml 获取结构化配置，再参考本文档理解字段语义和解析策略。

---

## 1. Sheet 识别策略

### 目标
从 Excel 文件的所有 sheet 中，筛选出 **CAN 信号表**（不含路由表、LIN 表等）。

### 判断规则

| 规则 | 说明 |
|------|------|
| 包含模式 | `Tx_*`、`Rx_*`、`*_CAN*`、`*Can*` |
| 排除关键词 | `Gateway`、`路由`、`LIN` |

### 常见 sheet 命名示例

```
✅ 匹配: Tx_CAN_FLZCU_BD, Rx_Public_CANFD2, Tx_CAN1, Rx_CAN1, CAN_Signals
❌ 排除: Gateway_Config, 路由表, LIN1, LIN2
```

### Agent 推理要点
- CAN 信号表的 sheet 名通常以 `Tx_` 或 `Rx_` 开头
- `Tx_` 表示发送方向，`Rx_` 表示接收方向
- 去掉前缀后的部分是 **通道名 (channel_name)**，如 `Tx_CAN_FLZCU_BD` → `CAN_FLZCU_BD`
- 多个 sheet 如 `Tx_CAN1` 和 `Rx_CAN1` 应合并到同一个通道 `CAN1` 下

---

## 2. 表头行检测策略

与 LIN 信号表类似：
1. 使用 `get_header_sample` 读取前 10 行 × 20 列的样本数据
2. 逐行扫描，统计每行中与 yaml `parameters[*].keywords` 匹配的单元格数量
3. 匹配数最多的行 = 表头行（header_row）
4. 验证：匹配数应 ≥ 3，否则可能是非标格式

---

## 3. 字段映射策略

### 字段分级

字段分为两级（参见 yaml 中的 `level` 属性）：

| 级别 | 含义 | 字段 |
|------|------|------|
| `message` | 帧级字段，每帧唯一 | EcuName, MsgName, MsgId, MsgLength, MsgSendType, MsgCycleTime, MsgDelayTime, Offset, MsgNrOfReption, MsgType |
| `signal` | 信号级字段，每信号一个值 | ShortName, BitPosition, BitSize, SignalType, SignalEndianness, SignalInitValue, SignalMinValue, SignalMaxValue, SignalDefaultValue, TimeoutValue, SignalDataInvalidValue, TransferProperty, UpdateBitPosition, SystemTemplateSystemSignalRef, Remark |

### 匹配规则

对每个 yaml parameter，按优先级依次尝试匹配：

1. **精确匹配**：Excel 列标题 == keyword（忽略首尾空格、换行符）
2. **大小写不敏感匹配**：`.lower()` 后比较
3. **包含匹配**：keyword 是 Excel 列标题的子串（或反之）
4. **语义匹配**（Agent 推理）：根据 AUTOSAR 领域知识判断语义等价

### 匹配注意事项

- `MsgName` 即原始代码的消息名/帧名，是 **分组依据**
- `MsgId` 是 CAN 报文 ID（hex 格式），`MsgLength` 是报文长度（DLC，字节数）
- `BitSize` 描述信号位长度，`MsgLength` 描述帧字节长度，**不能混淆**
- 如果 Excel 中有 `Length` 列，需根据上下文判断：帧长度值通常 ≤ 64（CANFD），信号长度值可能 > 8
- 如果某字段在 Excel 中找不到对应列，映射值留空 `""`

### 必填字段

| 字段 | 理由 |
|------|------|
| `MsgName` | 分组依据，缺失则无法构建消息结构 |
| `MsgId` | CAN 报文标识 |
| `ShortName` | 信号唯一标识 |
| `BitPosition` | ARXML 配置必需 |
| `BitSize` | ARXML 配置必需 |

---

## 4. 数据提取与类型转换

### 类型转换规则

| format | 转换方法 | 示例 |
|--------|----------|------|
| `string` | 原样保留，`str()` | `"BCM_Status"` |
| `int` | `int()` 取整 | `8` → `8`，`"8"` → `8` |
| `hex` | 保持 Excel 原始值 | `"0x123"` → `"0x123"` |
| `number` | `float()` | `"3.14"` → `3.14` |
| `enum` | **不做转换**，保持原始值 | `"Cyclic"` → `"Cyclic"`（原样保留） |

### 空值处理
- 空字符串 `""` 在 Trace 封装时自动转为 `null`（即 `{"value": null, ...}`）
- 这与原始代码行为一致：`val == "" → None`

### 枚举标准化

> **重要：为与原始解析结果保持一致，枚举类型字段不做自动标准化转换，保持 Excel 中的原始值。**
>
> 以下表格仅供 Agent 理解各枚举值的含义，**不用于自动转换**。

#### MsgSendType（保持原始值，不转换）
| 原始值示例 | 含义 |
|--------|--------|
| `Cyclic`, `cyclic`, `cycle`, `周期` | 周期帧 |
| `Event`, `event`, `on change`, `事件` | 事件触发帧 |
| `None`, `none`, `no send`, `不发送` | 不发送 |

#### SignalEndianness（保持原始值，不转换）
| 原始值示例 | 含义 |
|--------|--------|
| `Intel`, `Little`, `LSB`, `小端` | 小端序 (LITTLE_ENDIAN) |
| `Motorola`, `Big`, `MSB`, `大端` | 大端序 (BIG_ENDIAN) |

#### SignalType（保持原始值，不转换）
| 原始值示例 | 含义 |
|--------|--------|
| `uint`, `unsigned`, `无符号` | 无符号整数 |
| `int`, `signed`, `有符号` | 有符号整数 |
| `float`, `浮点` | 浮点数 |

### 无效数据过滤
- FrameName（MsgName）为空或含中文字符的行应跳过
- 空值率 >80% 的行自动过滤（`extract_columns_by_mapping` 内置）

---

## 5. 方向判断 (TX/RX) — 双模式

CAN 信号表使用 **双模式** 判断方向，与原始代码 `get_channel_name_by_sheet_name()` + `process_can_sheet()` 一致：

### 主规则：Sheet 名前缀（优先）

| 条件 | 方向 | 通道名 |
|------|------|--------|
| Sheet 名含 `Tx_` 前缀 | `TX` | 去掉 `Tx_` 前缀后的部分 |
| Sheet 名含 `Rx_` 前缀 | `RX` | 去掉 `Rx_` 前缀后的部分 |

**示例**：
- `Tx_CAN_FLZCU_BD` → direction=TX, channel_name=`CAN_FLZCU_BD`
- `Rx_Public_CANFD2` → direction=RX, channel_name=`Public_CANFD2`

### 回退规则：EcuName 字段值

当 sheet 名 **没有** `Tx_`/`Rx_` 前缀时，根据 `EcuName` 字段值判断：

| 条件 | 方向 |
|------|------|
| `EcuName` 的值在 `["CCU", "CCURT1", "CCURT2"]` 中 | `TX` |
| 其他值 | `RX` |

### 通道名推导
- **有前缀时**：channel_name = sheet 名去掉 `Tx_`/`Rx_` 前缀
- **无前缀时**：channel_name = sheet 名本身
- 同一 channel_name 下的 TX 和 RX 消息应合并到同一 channel 对象

---

## 6. 数据分组与组装

### 分组规则
- 按 `MsgName`（消息名/帧名）分组：同一 MsgName 的所有行组成一个 message
- 第一行的 message-level 字段值代表该 message 的帧级属性
- 所有行的 signal-level 字段汇集为 `signals` 数组

### Message 最终结构示例（与原始代码一致）

```json
{
  "msg_name": {"value": "BCM_Status", "trace": [...], "type": "user"},
  "signals": [
    {
      "ShortName": {"value": "VehicleSpeed", "trace": [...], "type": "user"},
      "BitPosition": {"value": 0, "trace": [...], "type": "user"},
      "BitSize": {"value": 16, "trace": [...], "type": "user"},
      "ComTransferProperty": {"value": "TRIGGERED", "trace": [], "type": "default"},
      "ComSignalEndianness": {"value": "BIG_ENDIAN", "trace": [], "type": "default"},
      "ComUpdateBitPosition": {"value": null, "trace": [], "type": "default"},
      "ComSystemTemplateSystemSignalRef": {"value": "...", "trace": [], "type": "design"},
      "index": 0
    }
  ],
  "group_ref": {"value": "CAN1", "trace": [], "type": "design"},
  "delay_time": {"value": null, "trace": [...], "type": "user"},
  "offset": {"value": null, "trace": [...], "type": "user"},
  "reption": {"value": null, "trace": [...], "type": "user"},
  "send_type": {"value": "Cyclic", "trace": [...], "type": "user"},
  "msg_id": {"value": "0x123", "trace": [...], "type": "user"},
  "msg_length": {"value": 8, "trace": [...], "type": "user"},
  "cycle_time": {"value": 100, "trace": [...], "type": "user"},
  "msg_type": {"value": null, "trace": [...], "type": "user"}
}
```

注意：
- 最终 message **不保留** `direction` 字段，方向由外层 `TX` / `RX` 数组表达
- `group_ref` 是设计推导字段，不来自 Excel 原列
- `ComSystemTemplateSystemSignalRef` 也是后处理推导字段，不应直接等同于 Excel 原始列值

### 中间结构说明

`build_module_metadata` 的输出仅用于中间分组，不能直接作为 CAN 最终 JSON。必须再映射到上述 `build_can_message()` 结构。


### Signal 默认值字段

原始代码 `build_can_message()` 在组装后为每个 signal 补充以下默认属性：

| 字段 | 默认值 | type |
|------|--------|------|
| `ComTransferProperty` | `"TRIGGERED"` | `"default"` |
| `ComSignalEndianness` | `"BIG_ENDIAN"` | `"default"` |
| `ComUpdateBitPosition` | `null` | `"default"` |

Agent 在 `build_module_metadata` 组装完成后，需为每个 signal 使用 `add_trace` 添加这 3 个默认值字段（type="default"，trace 为空数组）。

---

## 7. 最终输出结构

### 顶层路径
```
AUTOSAR.RequirementsData.CommunicationStack.Can
```

### 结构
```json
{
  "CAN_FLZCU_BD": {
    "TX": [
      { /* message 1 with direction, signals, defaults */ },
      { /* message 2 */ }
    ],
    "RX": [
      { /* message 3 */ }
    ]
  },
  "Public_CANFD2": {
    "TX": [...],
    "RX": [...]
  }
}
```

- 外层 key 是 **通道名 (channel_name)**（从 sheet 名去掉 Tx_/Rx_ 前缀得到）
- 第二层分为 `"TX"` 和 `"RX"`
- 每个 direction 下是 message 对象数组
- 每个 message 包含帧级字段 + `"direction"` 字段 + `signals` 数组
- 每个 signal 包含信号级字段 + 3 个默认值字段 + `"index"` 字段（数据区行偏移，0-based）

### RT1/RT2 回环路由特殊处理

原始代码包含 RT1/RT2 回环路由的特殊处理逻辑：
```
如果同时存在 RT1_RollBack_CANFD 和 RT2_RollBack_CANFD 通道：
  RT1_RollBack_CANFD.RX = RT2_RollBack_CANFD.TX
  RT2_RollBack_CANFD.RX = RT1_RollBack_CANFD.TX
```
Agent 在汇总输出时需检查并执行此交叉引用。

---

## 8. Trace 溯源

### Trace 信封结构

```json
{
  "value": "BCM_Status",
  "type": "user",
  "trace": [
    {
      "file": "D:/path/to/file.xlsx",
      "sheet": "Tx_CAN1",
      "row": 5,
      "col": "B"
    }
  ]
}
```

### 行号计算公式
`excel_row = _row_index + 1`，等价于 `header_row_index + 2 + data_row_index`
