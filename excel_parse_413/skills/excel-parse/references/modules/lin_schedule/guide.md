# LIN Schedule Guide

本模块用于解析 Excel 中的 LIN 调度表，提取帧传输顺序与时间信息。

## 先读文件

- `mapping.yaml`：sheet 识别规则、提取目标、布局参考、通道匹配规则
- `mapping.md`：不规则布局分析方法、帧名识别规则、提取策略

## 解析流程

### Step 0: 加载配置

从 `mapping.yaml` 提取：
- `sheet_patterns`
- `parameters`
- `layout_patterns`
- `channel_matching`

### Step 1: 识别调度表 sheet

1. 用 `list_sheets()` 获取全部 sheet。
2. 按 `sheet_patterns` 找出包含 `调度` / `Schedule` 的 sheet。
3. 排除 Legend、变更记录等非数据页。

### Step 2: 读取完整二维数据

1. 用 `read_sheet()` 读取整个 sheet。
2. 不要把它当作标准列式表。

### Step 3: 自行识别结构

Agent 需要自行推理：
- 哪一行是 frame 行
- 哪一行是 time 行
- 数据从哪一列开始
- 是否存在多个 schedule table 区块

典型做法：
1. 找到帧名密度最高的一行作为 frame 行。
2. 检查其相邻行，找到时间值密度最高的一行作为 time 行。
3. 逐列提取 `(frame_name, tans_time)`。

### Step 4: 逐列提取条目

对每个有效数据列提取：
- `frame_name`
- `tans_time`
- 对应的 1-based 行号与列号
- 对应的列字母

### Step 5: 通道匹配

如已有 LIN signal 结果：
1. 用 `match_by_intersection()` 按 frame_name 交集匹配到通道。
2. 若没有信号结果，则暂时以 sheet 名作为通道 key。

### Step 6: 构建输出

1. 用 `add_trace()` 为 `frame_name` 与 `tans_time` 构建 trace 信封。
2. 清理 helper 字段：`frame_row`、`frame_column`、`frame_column_name`、`trans_time_row`、`trans_time_column`、`trans_time_column_name`。
3. 保持原列顺序。
4. 最终输出路径：`AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSchedule`

## 关键规则

- 不能使用 `extract_columns_by_mapping()`。
- `Reserved` 是合法帧名。
- 输出字段使用历史拼写 `tans_time`。
- Trace 行列号直接使用 Excel 视角（1-based + 列字母）。
- 不要按 frame_name 做排序或分组重排。
