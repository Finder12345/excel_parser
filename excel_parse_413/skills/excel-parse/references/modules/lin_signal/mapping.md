# LIN 信号表字段映射参考

本文档是 `lin_signal_mapping.yaml` 的配套说明，为 Agent 提供 **推理指引**。
Agent 应先读取 yaml 获取结构化配置，再参考本文档理解字段语义和解析策略。

---

## 1. Sheet 识别策略

### 目标
从 Excel 文件的所有 sheet 中，筛选出 **LIN 信号表**（不含调度表、图例、变更记录等）。

### 判断规则

| 规则 | 说明 |
|------|------|
| 包含关键词 | `LIN`、`lin`、`Lin`、`信号表` |
| 排除关键词 | `调度`、`Schedule`、`schedule`、`Legend`、`变更`、`履历` |

### Agent 推理要点
- 一个 Excel 中可能有多个 LIN 信号 sheet（如 `LIN1`、`LIN2`、`Tx_LIN1`、`Rx_LIN2`）
- sheet 名含 `调度` 或 `Schedule` 的是调度表，**不是**信号表
- sheet 名含 `Legend`、`变更`、`履历` 的是辅助说明页，**跳过**
- 如果 sheet 名同时含有 `LIN` 和 `调度`（如 `LIN2调度表`），则**排除**（排除优先）

### 常见 sheet 命名示例

```
✅ 匹配: LIN1, LIN2, Tx_LIN1, Rx_LIN2, LIN信号表, Lin_Signals
❌ 排除: 调度表, LIN2调度表, LIN Schedule, LIN Legend, 变更履历
```

---

## 2. 表头行检测策略

### 目标
找到信号表的 **表头行**（column header row），即包含字段名称的那一行。

### Agent 推理要点
1. 使用 `get_header_sample` 读取前 10 行 × 20 列的样本数据
2. 表头行通常具备以下特征：
   - **非空单元格数量最多**（字段名称几乎占满一整行）
   - 包含多个**已知关键词**（如 "Signal Name"、"Frame Name"、"LIN ID" 等）
   - 表头行上方通常是标题/说明性文字或空行
   - 表头行下方紧接着是数据行
3. LIN 信号表**几乎都是水平方向**（horizontal）：行 = 信号记录，列 = 字段
4. 表头行索引一般在第 1~5 行（0-based），极少超过第 10 行

### 判断方法
```
对前 10 行逐行扫描：
  1. 统计每行中与 yaml parameters.keywords 匹配的单元格数量
  2. 匹配数最多的行 = 表头行
  3. 如果最高匹配数 < 3，可能是非标格式，需人工确认
```

---

## 3. 字段映射策略

### 目标
将 yaml 中定义的 AUTOSAR 标准字段名映射到 Excel 表头中的实际列名。

### 字段分级

字段分为两级（参见 yaml 中的 `level` 属性）：

| 级别 | 含义 | 字段示例 |
|------|------|----------|
| `message` | 帧级字段，每帧唯一 | EcuName, FrameName, LinId, ProtectedId, FrameLength, MsgSendType, FrameSendType, FrameCycleTime |
| `signal` | 信号级字段，每信号一个值 | ShortName, BitPosition, BitSize, SignalType, SignalEndianness, SignalInitValue, SignalMinValue, SignalMaxValue, SignalDefaultValue, TimeoutValue, SignalDataInvalidValue, SignalValueDescription, Remark |

### 匹配规则

对每个 yaml parameter，按优先级依次尝试匹配：

1. **精确匹配**：Excel 列标题 == keyword（忽略首尾空格、换行符）
2. **大小写不敏感匹配**：`.lower()` 后比较
3. **包含匹配**：keyword 是 Excel 列标题的子串（或反之）
4. **语义匹配**（Agent 推理）：根据 AUTOSAR 领域知识判断语义等价

### 匹配注意事项

- `LinId` ≠ `ProtectedId`：它们是不同概念，**绝对不能混淆**
  - LIN ID 范围：0x00 ~ 0x3F（6 bit）
  - Protected ID 是 LIN ID + 奇偶校验位（8 bit）
- `BitSize` 和 `SignalLength` 是**别名关系**（alias），映射到同一列即可
- `MsgSendType` 和 `FrameSendType` 是**别名关系**，**两者都需要映射到同一个 Excel 列**（确保 FrameSendType 也有正确的 trace 信息）
- `FrameLength` 的 keyword 中包含 `Length`，但 `Signal Length` 也含 `Length`，需注意**不能错配**：
  - `FrameLength` 描述帧长度（1~8 字节）
  - `Signal Length` / `BitSize` 描述信号位长度（1~64 位）
  - 区分方法：看列中的数据值范围，帧长度值通常 ≤ 8，信号长度值可能 > 8
- 如果某字段在 Excel 中找不到对应列，映射值留空 `""`

### 必填字段

以下字段**必须映射成功**，否则解析结果不可用：

| 字段 | 理由 |
|------|------|
| `FrameName` | 分组依据，缺失则无法构建消息结构 |
| `ShortName` | 信号唯一标识 |
| `BitPosition` | ARXML 配置必需 |
| `BitSize` | ARXML 配置必需 |
| `LinId` | LIN 帧标识 |

### 映射完整性校验

使用 `validate_field_mapping` 工具检查：
- **覆盖率阈值**：≥ 80%（即 22 个字段中至少 18 个需映射成功，不含别名字段）
- **必填字段**：上述 5 个字段全部必须映射成功
- 未达标时 Agent 应重新分析表头，尝试更宽松的匹配

---

## 4. 数据提取与类型转换

### 数据行范围
- **起始行**：表头行 + 1（0-based index）
- **结束行**：到数据结束（全空行表示数据结束）
- **跳过条件**：
  - 整行所有字段值都为空
  - 空值率 >80% 的行（即超过 80% 的字段为空值或缺失）
  - FrameName 为空或含中文字符的行

### 类型转换规则

| format | 转换方法 | 示例 |
|--------|----------|------|
| `string` | 原样保留，`str()` | `"CCU_LIN1_1"` |
| `int` | `int()` 取整 | `8` → `8`，`"8"` → `8` |
| `hex` | 保持 Excel 原始值 | `"0x3D"` → `"0x3D"` |
| `number` | `float()` | `"3.14"` → `3.14` |
| `enum` | **不做转换**，保持原始值 | `"UF"` → `"UF"`（原样保留） |

### 空值处理
- 空字符串 `""` 在 Trace 封装时自动转为 `null`（即 `{"value": null, ...}`）
- 这与原始代码行为一致：`val == "" → None`

### 枚举标准化

> **重要：为与原始解析结果保持一致，枚举类型字段不做自动标准化转换，保持 Excel 中的原始值。**
> 
> 以下表格仅供 Agent 理解各枚举值的含义，**不用于自动转换**。

#### MsgSendType / FrameSendType（保持原始值，不转换）
| 原始值示例 | 含义 |
|--------|--------|
| `Unconditional`, `UF`, `无条件` | 无条件帧 |
| `Event`, `ET`, `事件` | 事件触发帧 |
| `Sporadic`, `SF`, `偶发` | 偶发帧 |
| `Diagnostic`, `DF`, `诊断` | 诊断帧 |

#### SignalEndianness（保持原始值，不转换）
| 原始值示例 | 含义 |
|--------|--------|
| `Intel`, `Little`, `Little Endian`, `小端` | 小端序 (LITTLE_ENDIAN) |
| `Motorola`, `Big`, `Big Endian`, `大端` | 大端序 (BIG_ENDIAN) |

---

## 5. Trace 溯源

每个提取的字段值都必须包装为 Trace 信封格式，以支持后续的错误诊断和重新解析。

### Trace 信封结构

```json
{
  "value": "CCU_LIN1_1",
  "type": "user",
  "trace": [
    {
      "file": "D:/path/to/file.xlsx",
      "sheet": "LIN1",
      "row": 5,
      "col": "B"
    }
  ]
}
```

### 字段说明
- `value`：提取并转换后的值（可为 null）
- `type`：
  - `"user"` — 值来自 Excel 用户数据
  - `"design"` — 值由 Agent 根据规则推断
  - `"default"` — 使用了 yaml 中定义的默认值
- `trace`：溯源坐标数组
  - `file`：Excel 文件绝对路径
  - `sheet`：Sheet 名称
  - `row`：Excel 行号（1-based），计算公式：`header_row_index + 2 + data_row_index`
    - `header_row_index`：0-based 表头行索引
    - `+2`：跳过表头行本身（+1）+ Excel 行号从 1 开始（+1）
    - `data_row_index`：0-based 数据行索引
  - `col`：Excel 列字母（如 "A"、"B"、"AA"）

---

## 6. 数据分组与组装

### 分组规则
- 按 `FrameName` 分组：同一 `FrameName` 的所有行组成一个 message
- 第一行的 message-level 字段值代表该 message 的帧级属性
- 所有行的 signal-level 字段汇集为 `signals` 数组

### Message 结构示例

```json
{
  "EcuName": {"value": "CCU", "type": "user", "trace": [...]},
  "FrameName": {"value": "CCU_LIN1_1", "type": "user", "trace": [...]},
  "LinId": {"value": "0x10", "type": "user", "trace": [...]},
  "ProtectedId": {"value": "0x50", "type": "user", "trace": [...]},
  "MsgSendType": {"value": "UF", "type": "user", "trace": [...]},
  "FrameLength": {"value": 8, "type": "user", "trace": [...]},
  "FrameSendType": {"value": "UF", "type": "user", "trace": [...]},
  "FrameCycleTime": {"value": 10, "type": "user", "trace": [...]},
  "direction": "TX",
  "signals": [
    {
      "ShortName": {"value": "Sig_WindowPos", "type": "user", "trace": [...]},
      "BitPosition": {"value": 0, "type": "user", "trace": [...]},
      "BitSize": {"value": 8, "type": "user", "trace": [...]},
      "SignalDefaultValue": {"value": "0x00", "type": "user", "trace": [...]},
      ...,
      "index": 0
    },
    {
      "ShortName": {"value": "Sig_WindowCmd", "type": "user", "trace": [...]},
      ...,
      "index": 1
    }
  ]
}
```

---

## 7. 方向判断 (TX/RX)

### 规则
根据 `EcuName` 字段值判断每条消息的传输方向：

| 条件 | 方向 |
|------|------|
| `EcuName` 的值在 `["CCU", "CCURT1", "CCURT2"]` 中 | `TX`（主节点发送） |
| 其他值 | `RX`（从节点发送，主节点接收） |

### 说明
- CCU = Central Control Unit（车身控制器），通常是 LIN 主节点
- CCURT1/CCURT2 = CCU 变体
- **方向判断是逐行进行的**，因为同一个 sheet 可能混合 TX 和 RX 消息
- 如果 `EcuName` 字段未映射或值为空，默认为 `RX`

---

## 8. 最终输出结构

### 顶层路径
```
AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSignal
```

### 结构
```json
{
  "LIN1": {
    "TX": [
      { /* message 1 */ },
      { /* message 2 */ }
    ],
    "RX": [
      { /* message 3 */ },
      { /* message 4 */ }
    ]
  },
  "LIN2": {
    "TX": [...],
    "RX": [...]
  }
}
```

- 每个 message 在最终输出中不保留 `direction` 字段；方向仅用于分流到 `TX/RX`。
- 每个 signal 在最终输出中不保留临时 `index` 字段；该字段仅用于 trace 行号回推。

---

## 9. 数据校验规则

解析完成后，对每条消息和信号执行以下校验：

| 规则 | 级别 | 说明 |
|------|------|------|
| `0x00 <= LinId <= 0x3F` | error | LIN ID 范围限制（6 bit） |
| `1 <= FrameLength <= 8` | error | LIN 帧最大 8 字节 |
| `BitPosition < FrameLength * 8` | error | 起始位不能超出帧长度 |
| `BitPosition + BitSize <= FrameLength * 8` | error | 信号不能溢出帧边界 |
| `FrameName` 匹配 `^[A-Za-z_][A-Za-z0-9_]*$` | warning | AUTOSAR 标识符规范 |
| `ShortName` 匹配 `^[A-Za-z_][A-Za-z0-9_]*$` | warning | AUTOSAR 标识符规范 |

### 无效数据过滤
- 如果一行数据中 **FrameName 为空或包含中文字符**，该行将被跳过
- 如果一行数据中 **>80% 的字段为空**，该行被视为无效行并跳过

---

## 10. 特殊情况处理

### 合并单元格
- Excel 中帧级字段（如 FrameName、LinId）常常使用**合并单元格**
- `read_sheet` 工具已内置合并单元格展开逻辑：将合并区域的值填充到所有被合并的单元格
- Agent 无需额外处理

### 多 Sheet 场景
- 同一个 Excel 文件可能有多个 LIN 信号 sheet（`LIN1`、`LIN2` 等）
- 每个 sheet 独立解析，最终以 sheet 名称为 key 汇总

### 别名字段
- `BitSize` 和 `SignalLength` 是同一概念的不同命名
- `MsgSendType` 和 `FrameSendType` 是同一概念的不同命名
- **别名字段也需要映射到同一个 Excel 列**：原始代码中 `FrameSendType` 和 `MsgSendType` 都映射到 `"Frame Send Type"` 列，确保两者都有正确的 trace 信息
- 如果 primary 和 alias 都在 Excel 中找到了不同的列，以 primary 为准
