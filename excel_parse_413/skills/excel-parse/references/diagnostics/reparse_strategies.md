# Reparse Strategies

## 粒度选择

1. 单字段：`reparse_field`
2. 单行：`reparse_row`
3. 模块指定字段：`reparse_module_fields`

## 推荐流程

- 先定位（`locate_trace`）
- 再读取源头（`read_source_cell`）
- 决策重解析粒度
- 应用补丁（`patch_metadata`）
- 做差异校验（`diff_metadata`）

## 风险控制

- 每次 patch 后立即做 diff。
- 批量修复前先导出诊断报告，便于回溯。
