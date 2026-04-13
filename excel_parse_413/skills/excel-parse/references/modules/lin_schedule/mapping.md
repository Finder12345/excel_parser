# LIN 调度表解析参考

本文档是 `lin_schedule_mapping.yaml` 的配套说明，为 Agent 提供**推理指引**。
调度表的结构与常规信号表完全不同，Agent 需要理解其不规则布局后自行提取数据。

---

## 1. Sheet 识别策略

### 目标
从 Excel 文件的所有 sheet 中，筛选出 **LIN 调度表**。

### 判断规则

| 规则 | 说明 |
|------|------|
| 包含关键词 | `调度`、`Schedule`、`schedule` |
| 排除关键词 | `Legend`、`变更`、`履历` |

### 常见 sheet 命名示例

```
✅ 匹配: 调度表, LIN2调度表, LIN1 Schedule, Schedule_LIN1
❌ 排除: LIN1, LIN2（这些是信号表，不是调度表）
❌ 排除: LIN Legend, 变更履历
```

### 与信号表的区别
- **信号表**：sheet 名含 `LIN` 但**不含** `调度`/`Schedule`
- **调度表**：sheet 名含 `调度` 或 `Schedule`
- 如果 sheet 名同时含有 `LIN` 和 `调度`（如 `LIN2调度表`），它是**调度表**

---

## 2. 调度表结构分析

### 核心特点

调度表与信号表的关键区别：

| 对比项 | 信号表 | 调度表 |
|--------|--------|--------|
| 布局 | 标准表格（列=字段，行=记录） | 不规则布局（帧名和时间分散在不同行列） |
| 表头 | 有明确的字段名表头行 | 无标准表头，可能有标签行 |
| 数据方向 | 数据总是水平行展开 | 数据可能水平或垂直排列 |
| 提取方式 | 按列映射批量提取 | 需要整体分析表格结构后定位 |

### 典型布局（水平模式 — 最常见）

```
     A          B           C       D       E       F       G       H       I       J       K       L       M
1  (空)       15ms        15ms    15ms    15ms    15ms    15ms    15ms    15ms    15ms    15ms    15ms    15ms
2  实际调度表  CCU_LIN1_1  RLS_1   RLS_2   RLS_3   CCU_LIN1_1  RLS_1   SSM_1   SSM_2   CCU_LIN1_1  RLS_1   CCU_LIN1_2  Reserved
3  (空)       180ms
```

#### 分析要点
- **行 1**：传输时间行 — 每个时隙的传输耗时（如 `15ms`）
- **行 2**：帧名行 — 每个时隙对应的帧名称
- **行 3**：总耗时行 — 整个调度表的总时间（如 `180ms`）
- **列 A**：标签列 — 可能有描述性文字（如 "实际调度表"），也可能为空
- **列 B 开始**：数据列 — 每列代表一个调度时隙

### 变体情况

#### 变体 1：时间行在帧名行下方
```
1  (空)       CCU_LIN1_1  RLS_1   RLS_2   ...
2  (空)       15ms        15ms    15ms    ...
3  (空)       180ms
```

#### 变体 2：多行标签
```
1  调度表名称  LIN1调度
2  (空)       15ms        15ms    15ms    ...
3  实际调度表  CCU_LIN1_1  RLS_1   RLS_2   ...
4  总耗时     180ms
```

#### 变体 3：多个调度表在同一 sheet
```
1  LIN1调度    15ms       15ms    15ms    ...
2  (空)       CCU_LIN1_1 RLS_1   RLS_2   ...
3
4  LIN2调度    10ms       10ms    10ms    ...
5  (空)       CCU_LIN2_1 DDM_1   DDM_2   ...
```

---

## 3. Agent 数据提取策略

### 推荐流程

由于调度表结构不规则，无法使用 `extract_columns_by_mapping` 等标准工具。
Agent 应使用 `read_sheet` 读取完整数据后，**自行分析并提取**。

#### Step 1: 读取完整数据

```
工具: read_sheet(file_path, sheet_name)
```

获取完整的二维数组数据。

#### Step 2: 识别帧名行

扫描每一行，判断是否为帧名行：
- **帧名特征**：
  - 英文标识符格式，如 `CCU_LIN1_1`、`RLS_1`、`SSM_1`
  - 常见前缀：`CCU`、`RLS`、`SSM`、`SSMF`、`SSMR`、`SRM`、`DDM`、`PSM`
  - `Reserved` 也是合法帧名（表示保留时隙）
  - **不是**：纯数字、带 `ms` 后缀的时间值、中文描述文字
- **判断方法**：如果一行中有 ≥ 3 个单元格符合帧名特征，该行是帧名行

#### Step 3: 识别时间行

扫描帧名行的上方和下方相邻行：
- **时间特征**：
  - 值带有 `ms` 后缀，如 `15ms`、`10ms`
  - 或者是纯数字（隐含单位为 ms）
- **判断方法**：如果一行中有 ≥ 3 个单元格符合时间特征，该行是时间行

#### Step 4: 提取数据对

对帧名行的每个非空单元格，提取对应的帧名和时间：

```python
# 伪代码
for col_idx in range(start_col, end_col):
    frame_name = data[frame_row][col_idx]
    tans_time = data[time_row][col_idx]
    if frame_name and is_valid_frame_name(frame_name):
        entries.append({
            "frame_name": frame_name,
            "tans_time": tans_time,
            "frame_row": frame_row + 1,       # 转为1-based
            "frame_column": col_idx + 1,       # 转为1-based
            "trans_time_row": time_row + 1,    # 转为1-based
            "trans_time_column": col_idx + 1   # 转为1-based
        })
```

#### Step 5: 添加列字母

使用 `col_index_to_letter` 将列号（1-based）转为 Excel 列字母：

```python
from skills._shared_scripts import col_index_to_letter_core

for entry in entries:
    entry["frame_column_name"] = col_index_to_letter_core(entry["frame_column"])
    entry["trans_time_column_name"] = col_index_to_letter_core(entry["trans_time_column"])
```

#### Step 6: 构建 Trace 信封

使用 `add_trace` 为 frame_name 和 tans_time 添加溯源信息：

```json
{
  "frame_name": {
    "value": "CCU_LIN1_1",
    "type": "user",
    "trace": [{"file": "xxx.xlsx", "sheet": "调度表", "row": "2", "col": "B"}]
  },
  "tans_time": {
    "value": "15ms",
    "type": "user",
    "trace": [{"file": "xxx.xlsx", "sheet": "调度表", "row": "1", "col": "B"}]
  }
}
```

---

## 4. 通道匹配

### 目标
将调度表与对应的 LIN 信号 sheet（通道）关联。

### 匹配算法

使用 `match_by_intersection` 工具：

```
工具: match_by_intersection(
    data_a = {schedule_sheet_name: set(帧名列表)},
    data_b = {signal_sheet_name: set(帧名列表)},
    min_rate = 0.0
)
```

**交集率计算**：
```
rate = len(schedule_frames ∩ signal_frames) / len(signal_frames)
```

将调度表分配给交集率最高的信号通道。

### 示例

```
调度表帧名: {CCU_LIN1_1, RLS_1, RLS_2, RLS_3, SSM_1, SSM_2, CCU_LIN1_2, Reserved}
LIN1 信号帧名: {CCU_LIN1_1, RLS_1, RLS_2, RLS_3, SSM_1, SSM_2, CCU_LIN1_2}
LIN2 信号帧名: {CCU_LIN2_1, DDM_1, PSM_1}

LIN1 交集率 = 7/7 = 1.0  ← 最高
LIN2 交集率 = 0/3 = 0.0

→ 调度表分配给 LIN1
```

### 注意事项
- `Reserved` 帧名不会出现在信号表中，但不影响匹配（只看交集，不看差集）
- 如果调度表无法与任何信号通道匹配（所有交集率为 0），可能是调度表独立存在，以其自身 sheet 名为 key

---

## 5. 最终输出结构

### 顶层路径
```
AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSchedule
```

### 结构
```json
{
  "LIN1": {
    "schedule_table_1": [
      {
        "frame_name": {"value": "CCU_LIN1_1", "type": "user", "trace": [{"file": "...", "sheet": "调度表", "row": "2", "col": "B"}]},
        "tans_time": {"value": "15ms", "type": "user", "trace": [{"file": "...", "sheet": "调度表", "row": "1", "col": "B"}]}
      },
      {
        "frame_name": {"value": "RLS_1", "type": "user", "trace": [...]},
        "tans_time": {"value": "15ms", "type": "user", "trace": [...]}
      },
      ...
    ]
  }
}
```

- 外层 key 是**通道名称**（匹配到的信号 sheet 名，如 `"LIN1"`）
- 第二层 key 是 `"schedule_table_1"`（调度表标识）
- 值是调度条目数组，**保持原始列顺序**（反映帧在总线上的传输次序）
- 每个条目只有 `frame_name` 和 `tans_time` 两个字段，均包装为 Trace 信封

---

## 6. 帧名识别规则

### 有效帧名特征
- 英文字母 + 数字 + 下划线组成
- 通常格式为 `ECU_LINx_N` 或 `ECU_N`
- 常见前缀列表：

| 前缀 | 含义 |
|------|------|
| `CCU` | Central Control Unit（车身控制器） |
| `CCURT1/2` | CCU 变体 |
| `RLS` | Rain Light Sensor（雨量光线传感器） |
| `SSM` | Seat Switch Module（座椅开关模块） |
| `SSMF/SSMR` | SSM 前排/后排 |
| `SRM` | Seat Recline Motor（座椅调节电机） |
| `DDM` | Driver Door Module（驾驶门模块） |
| `PSM` | Passenger Seat Module（乘客座椅模块） |
| `Reserved` | 保留时隙（无实际帧传输） |

### 无效值（不是帧名）
- 纯数字：`15`、`180`
- 带 ms 后缀：`15ms`、`180ms`
- 中文文字：`实际调度表`、`总耗时`
- 空单元格

---

## 7. 与 LIN 信号解析的协作

LIN 调度表解析通常与 LIN 信号表解析**协同进行**：

1. **先解析信号表**（`excel-parse-lin-signal` Skill）→ 获取每个通道的帧名集合
2. **再解析调度表**（本 Skill）→ 提取调度数据
3. **通道匹配**：用调度表帧名与信号表帧名的交集率匹配通道
4. **合并输出**：信号数据存储在 `Lin.LinSignal`，调度数据存储在 `Lin.LinSchedule`

如果没有先执行信号表解析（缺少帧名集合），调度表可以独立输出，以 sheet 名为 key。
