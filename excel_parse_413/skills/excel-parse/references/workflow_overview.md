# Workflow Overview

该模式用于编排同一批 Excel 的全量解析。

## 推荐顺序

1. 用 `list_sheets()` 获取全部 sheet。
2. 依据各模块 `mapping.yaml` 中的 `sheet_patterns` 对 sheet 分类。
3. 依次执行：
   - CAN 信号解析（汇总前用 `finalize_can_metadata()`）
   - CAN 路由解析（必要时用 `finalize_routing_metadata()`）
   - LIN 信号解析（汇总前用 `finalize_lin_metadata()`）
   - LIN 调度解析（归属和清理用 `finalize_lin_schedule()`）
   - NVM 解析（汇总前用 `finalize_nvm_metadata()`）
4. 用 `assemble_full_metadata()` 按 `output_schema.yaml` 汇总。
5. 用 `validate_metadata_schema()` 校验结构。
6. 用 `check_consistency()` 执行跨源一致性检查。
7. 用 `simplify_metadata()` 生成简化版输出。

## 说明

- 建议优先保证单模块流程可独立跑通，再启用全量汇总。
- LIN 调度解析如需通道匹配，应优先依赖 LIN 信号解析结果。
- full 模式不再跨 skill 引用其他目录，统一从本 skill 的 `references/modules/*` 获取规则。
