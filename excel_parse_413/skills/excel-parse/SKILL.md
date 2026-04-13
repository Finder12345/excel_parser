---
name: excel-parse
description: >-
  统一编排 CAN/LIN/NVM Excel 解析、全量汇总与错误重解析。
  当用户要求解析 CAN 信号、CAN 路由、LIN 信号、LIN 调度、NVM、全量解析、DaVinci 报错修复时触发此技能。
version: 1.0.0
tools:
  - col_index_to_letter
  - col_letter_to_index
  - save_json
  - load_json
  - extract_json_from_text
  - add_trace
  - normalize_value
  - list_sheets
  - read_sheet
  - get_header_sample
  - get_column_letter_mapping
  - sheet_to_column_json
  - read_cell_range
  - extract_columns_by_mapping
  - build_module_metadata
  - build_routing_metadata
  - finalize_routing_metadata
  - finalize_can_metadata
  - finalize_lin_metadata
  - finalize_lin_schedule
  - finalize_nvm_metadata
  - assemble_full_metadata
  - match_by_intersection
  - locate_trace
  - read_source_cell
  - reparse_field
  - reparse_row
  - reparse_module_fields
  - patch_metadata
  - diff_metadata
  - export_diagnostic_report
  - validate_field_mapping
  - validate_metadata_schema
  - check_consistency
  - simplify_metadata
---
# Excel Parse

**输入**: Excel 文件路径、元数据路径、错误描述或字段路径（按场景不同）
**输出**: 模块级解析结果、全量 AUTOSAR 元数据、或诊断/重解析结果

## 脚本位置

- 本 Skill 的可执行工具脚本统一位于 `scripts/_shared_scripts/`。
- 调用工具前，先根据当前任务类型读取对应 `references/` 下的 guide 和 mapping 文件。

## 支持的工作模式

### 1. module_parse
解析单个模块：
- CAN 信号
- CAN 路由
- LIN 信号
- LIN 调度
- NVM

### 2. full_parse
对同一批 Excel 执行全量解析，最终汇总到统一 AUTOSAR 结构。

### 3. diagnostic_reparse
针对下游报错做字段溯源、重解析、局部修补与差异验证。

## 模块路由

- CAN 信号解析 → `references/modules/can_signal/guide.md`
- CAN 路由解析 / Gateway → `references/modules/can_routing/guide.md`
- LIN 信号解析 → `references/modules/lin_signal/guide.md`
- LIN 调度解析 → `references/modules/lin_schedule/guide.md`
- NVM 解析 → `references/modules/nvm/guide.md`
- 全量解析 → `references/overview.md` + `references/workflow_overview.md`
- 错误诊断 / 重解析 / DaVinci 报错修复 → `references/diagnostics/guide.md`

## 通用执行规则

1. 先判断当前任务属于哪种模式，再进入对应 guide。
2. 先读取 guide，再读取同目录下的 `mapping.yaml` / `mapping.md` 或诊断 reference。
3. 所有脚本从 `scripts/_shared_scripts/` 调用，不再跨 skill 跳转。
4. 通用 Trace 信封格式：`{value, type, trace:[{file, sheet, row, col}]}`。
5. 枚举字段默认保持 Excel 原值，除非模块 guide 明确要求额外处理。
6. 标准列式表优先走 `get_header_sample -> get_column_letter_mapping -> extract_columns_by_mapping`。
7. 非标准布局（如 CAN routing、LIN schedule、NVM 双区结构）优先按模块 guide 的特殊流程处理。

## 工具分组

### Excel I/O
- `list_sheets`
- `read_sheet`
- `get_header_sample`
- `get_column_letter_mapping`
- `sheet_to_column_json`
- `read_cell_range`

### 数据组装
- `extract_columns_by_mapping`
- `build_module_metadata`
- `build_routing_metadata`
- `finalize_routing_metadata`
- `finalize_can_metadata`
- `finalize_lin_metadata`
- `finalize_lin_schedule`
- `finalize_nvm_metadata`
- `assemble_full_metadata`
- `match_by_intersection`

### 验证
- `validate_field_mapping`
- `validate_metadata_schema`
- `check_consistency`
- `simplify_metadata`

### 诊断与修补
- `locate_trace`
- `read_source_cell`
- `reparse_field`
- `reparse_row`
- `reparse_module_fields`
- `patch_metadata`
- `diff_metadata`
- `export_diagnostic_report`

## Full parse 约定

1. 读取 `references/overview.md` 和 `references/workflow_overview.md`。
2. 用 `list_sheets()` 获取所有 sheet 并分类。
3. 按模块 guide 执行：CAN signal → CAN routing → LIN signal → LIN schedule → NVM；其中：
   - CAN signal 汇总前使用 `finalize_can_metadata()`
   - LIN signal 汇总前使用 `finalize_lin_metadata()`
   - LIN schedule 归属和清理使用 `finalize_lin_schedule()`
   - NVM 汇总前使用 `finalize_nvm_metadata()`
4. 用 `assemble_full_metadata()` 汇总到 `references/output_schema.yaml`。
5. 用 `validate_metadata_schema()` 和 `check_consistency()` 做校验。
6. 用 `simplify_metadata()` 生成简化输出。

## Diagnostic 约定

1. 读取 `references/diagnostics/guide.md`、`error_field_mapping.yaml`、`reparse_strategies.md`。
2. 先 `locate_trace()`，再 `read_source_cell()`。
3. 根据问题粒度选择 `reparse_field()` / `reparse_row()` / `reparse_module_fields()`。
4. 用 `patch_metadata()` 应用修补。
5. 用 `diff_metadata()` 验证范围，必要时用 `export_diagnostic_report()` 输出报告。
