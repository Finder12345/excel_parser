# NVM Guide

本模块用于解析 Excel 中的 NVM 配置表，提取公共参数区与 block 列表区。

## 先读文件

- `mapping.yaml`：sheet 识别规则、区域特征、字段定义、校验规则
- `mapping.md`：双区域识别建议、Block 区提取注意事项、常见问题

## 解析流程

### Step 1: 识别 NVM sheet

1. 用 `list_sheets()` 获取全部 sheet。
2. 按 `mapping.yaml` 中的 `sheet_patterns` 找到候选 NVM sheet。

### Step 2: 识别双区域边界

1. 用 `get_header_sample()` 读取上部样本。
2. 找到公共参数区与 block 列表区的边界。
3. 找到 block 列表区的 `header_row`。

### Step 3: 提取公共参数区

1. 用 `read_cell_range()` 读取上部 key-value。
2. 对每个参数值补 `add_trace()`。
3. 公共参数区保持在 `common` 下。

### Step 4: 提取 block 列表区

1. 先建立字段映射。
2. 用 `extract_columns_by_mapping()` 提取 block 列表。
3. 对每个字段值补 trace。
4. 保持 block 列表的扁平结构。

### Step 5: 汇总输出

1. 最终结构保持原有 `nvm_datas -> main_data -> sheet_name -> common/block` 语义。
2. `NvRamManager` 顶层保持 list，每个元素保留 `file_path` 与 `main_data`。
3. 输出路径：`AUTOSAR.RequirementsData.Storage.NvRamManager`

## 关键规则

- NVM 是双区域结构：上部 common，下部 block list。
- 不要对 block 列表使用 `build_module_metadata()` 做 message/signal 分组。
- 最终 key 保持 `common` 与 `block`，不要重命名为新模型。
- 布尔字段保持 Excel 原值。
- 公共参数区应用 key-value 方式读取，而不是强行按标准表格处理。
