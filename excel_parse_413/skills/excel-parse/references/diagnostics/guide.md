# Diagnostics Guide

本模式用于对下游报错字段做溯源、重解析和局部修补。

## 先读文件

- `error_field_mapping.yaml`：错误模式到模块/字段/动作映射
- `error_field_mapping.md`：常见错误解释与修复建议
- `reparse_strategies.md`：单字段 / 单行 / 模块字段批量重解析策略

## 典型场景

### 1. 已知字段路径
1. 用 `locate_trace()` 定位字段来源。
2. 用 `read_source_cell()` 检查 Excel 原始单元格和邻居上下文。
3. 判断应使用 `reparse_field()`、`reparse_row()` 还是 `reparse_module_fields()`。
4. 用 `patch_metadata()` 应用修补。
5. 用 `diff_metadata()` 验证只影响目标范围。

### 2. 已知错误描述
1. 结合 `error_field_mapping.yaml` 识别可能的模块、字段和动作。
2. 批量 `locate_trace()` 找到实际来源。
3. 逐项读取源头并决定重解析策略。
4. 必要时输出 `export_diagnostic_report()`。

### 3. 批量错误修复
1. 先按模块分组错误。
2. 同模块多字段问题优先考虑 `reparse_module_fields()`。
3. 批量 patch 后统一 diff。

## 通用规则

- 每次 patch 后都要做 diff。
- Excel 原值如果本身错误，应优先提示用户修 Excel，而不是强行修补元数据。
- 需要审计留痕时输出诊断报告。
