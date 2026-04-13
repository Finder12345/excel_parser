# Excel Parse Overview

本 Skill 统一覆盖以下能力：

- CAN 信号解析
- CAN 路由解析
- LIN 信号解析
- LIN 调度解析
- NVM 解析
- 全量汇总解析
- 错误定位、重解析与局部修补

## 模块输出路径

- CAN Signal → `AUTOSAR.RequirementsData.CommunicationStack.Can`
- CAN Routing → `AUTOSAR.RequirementsData.CommunicationStack.GateWayConfiguration`
- LIN Signal → `AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSignal`
- LIN Schedule → `AUTOSAR.RequirementsData.CommunicationStack.Lin.LinSchedule`
- NVM → `AUTOSAR.RequirementsData.Storage.NvRamManager`

## 通用约束

- 所有脚本位于 `scripts/_shared_scripts/`。
- 所有值默认使用 Trace 信封：`{value, type, trace:[{file, sheet, row, col}]}`。
- `type` 取值约定：`user` / `design` / `default`。
- 枚举字段默认保持 Excel 原值，不主动做破坏兼容性的归一化转换。
- 标准列式表模块优先复用通用抽列流程；特殊布局模块按各自 guide 执行。
- 行号和列号最终应使用 Excel 视角（1-based 行号，列字母）。

## 模块边界

### 标准列式解析模块
- CAN signal
- LIN signal

这些模块通常遵循：
`list_sheets -> get_header_sample -> get_column_letter_mapping -> extract_columns_by_mapping -> build_module_metadata`

### 特殊结构模块
- CAN routing：矩阵布局，左侧字段区 + 右侧通道路由矩阵
- LIN schedule：不规则二维布局，Agent 自行识别 frame/time 行
- NVM：上部公共参数区 + 下部 block 列表区

### 特殊工作模式
- full_parse：调度所有模块并汇总输出
- diagnostic_reparse：从元数据反查 Excel 源头后局部修补
