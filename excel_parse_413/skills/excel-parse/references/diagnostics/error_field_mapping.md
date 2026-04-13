# Error Field Mapping 说明

该文件维护常见错误模式与字段映射，供 Agent 快速决策重解析动作。

## 决策规则

- `action=reparse_field`：单字段解析错误。
- `action=reparse_row`：同一行多个字段关联错误。
- `action=reparse_module_fields`：整列或多个字段批量错误。

## 输出建议

诊断输出应至少包含：字段路径、错误信息、当前值、trace、修复建议。
