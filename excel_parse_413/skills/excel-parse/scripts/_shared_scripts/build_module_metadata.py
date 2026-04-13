# -*- coding: utf-8 -*-
"""
通用模块元数据组装工具。

将提取的行数据按分组配置组装为结构化元数据，自动添加 trace 溯源信息。

纯函数，零LLM。
"""
import json
import re
from typing import Any, Dict, List, Optional, Set

from langchain.tools import tool

from .add_trace import add_trace_core
from .column_utils import col_index_to_letter_core
from .get_column_letter_mapping import get_column_letter_mapping_core


# ── 核心纯函数 ──

def build_module_metadata_core(
    rows_data: List[Dict[str, Any]],
    group_by: List[str],
    message_level_fields: List[str],
    signal_level_fields: Optional[List[str]] = None,
    file_path: str = "",
    sheet_name: str = "",
    header_row: int = 0,
    column_mapping: Optional[Dict[str, str]] = None,
    direction_config: Optional[Dict] = None,
) -> Dict:
    """将提取的行数据按分组配置组装为模块元数据。

    Args:
        rows_data: extract_columns_by_mapping 的输出，每个元素含 _row_index
        group_by: 分组字段列表（如 ["FrameName", "LinId"]）
            按第一个字段的值分组，相同值的行聚合为一条消息/帧
        message_level_fields: 消息/帧级别的字段（每组取第一行的值）
            如 ["EcuName", "FrameName", "LinId", "ProtectedId", "FrameLength", ...]
        signal_level_fields: 信号级别的字段（每行一条，聚合为列表）
            如 ["ShortName", "BitPosition", "BitSize", ...]
            None 时自动取 rows_data 中除 message_level_fields 和元字段之外的所有字段
        file_path: 源文件路径（用于 trace）
        sheet_name: 源 sheet 名（用于 trace）
        header_row: 表头行号 0-based（用于计算 Excel 行号）
        column_mapping: {字段名: 列字母} 映射（用于 trace 的 col 字段）
            None 时 trace 中不包含 col 信息
        direction_config: 方向判断配置（可选）
            {
                "field": "EcuName",                    # 根据哪个字段判断方向
                "tx_values": ["CCU", "CCURT1", "CCURT2"],  # 这些值表示 TX
                "default": "RX"                        # 其他值默认方向
            }

    Returns:
        分组后的结构化元数据，带 trace。
        若配置了 direction_config，返回 {"TX": [...], "RX": [...]}
        否则返回消息列表 [msg1, msg2, ...]
    """
    meta_fields = {"_row_index", "_data_index"}

    if signal_level_fields is None:
        all_fields = set()
        for row in rows_data:
            all_fields.update(row.keys())
        signal_level_fields = [
            f for f in all_fields
            if f not in set(message_level_fields) and f not in meta_fields
        ]

    # ── 辅助函数 ──
    _chinese_re = re.compile(r'[\u4e00-\u9fff]')

    def _contains_chinese(s: str) -> bool:
        """含中文判断（原始代码跳过含中文 FrameName 的行）"""
        return bool(_chinese_re.search(str(s)))

    def _to_none_if_empty(val: Any) -> Any:
        """与原始代码对齐：仅空字符串 → None"""
        if val is None:
            return None
        if isinstance(val, str) and val == "":
            return None
        return val

    # 分组聚合
    group_key = group_by[0] if group_by else None
    groups: Dict[str, Dict] = {}  # group_value → {"message": {...}, "signals": [...]}
    group_order: List[str] = []

    for row in rows_data:
        key_value = str(row.get(group_key, "")) if group_key else str(row.get("_data_index", ""))
        if not key_value or not key_value.strip():
            continue

        # 原始代码：跳过 FrameName 含中文字符的行
        if group_key and _contains_chinese(key_value):
            continue

        row_index = row.get("_row_index", 0)
        data_index = row.get("_data_index", 0)
        excel_row = row_index + 1  # 转为 1-based Excel 行号

        if key_value not in groups:
            group_order.append(key_value)
            # 构建消息级字段（取第一行的值）
            msg = {}
            for field in message_level_fields:
                val = row.get(field, "")
                col = column_mapping.get(field, "") if column_mapping else ""
                msg[field] = add_trace_core(_to_none_if_empty(val), "user", file_path, sheet_name, excel_row, col)
            groups[key_value] = {"message": msg, "signals": []}

        # 构建信号级字段
        signal = {}
        for field in signal_level_fields:
            if field in meta_fields:
                continue
            val = row.get(field, "")
            col = column_mapping.get(field, "") if column_mapping else ""
            signal[field] = add_trace_core(_to_none_if_empty(val), "user", file_path, sheet_name, excel_row, col)

        short_name_trace = signal.get("ShortName", {})
        short_name_val = short_name_trace.get("value") if isinstance(short_name_trace, dict) else short_name_trace
        if short_name_val:
            signal["index"] = data_index
            groups[key_value]["signals"].append(signal)

    # 组装输出
    messages = []
    for key in group_order:
        group = groups[key]
        msg = group["message"]
        msg["signals"] = group["signals"]
        messages.append(msg)

    # 方向分组
    if direction_config:
        dir_field = direction_config.get("field", "")
        tx_values = set(direction_config.get("tx_values", []))
        default_dir = direction_config.get("default", "RX")

        result = {"TX": [], "RX": []}
        for msg in messages:
            field_val = msg.get(dir_field, {})
            val = field_val.get("value", "") if isinstance(field_val, dict) else field_val
            direction = "TX" if str(val) in tx_values else default_dir
            msg["direction"] = direction
            result[direction].append(msg)
        return result

    return messages


# ── LangChain @tool 包装 ──

@tool
def build_module_metadata(
    rows_data_json: str,
    group_by_json: str,
    message_level_fields_json: str,
    signal_level_fields_json: str = "",
    file_path: str = "",
    sheet_name: str = "",
    header_row: int = 0,
    column_mapping_json: str = "{}",
    direction_config_json: str = "",
) -> str:
    """Build grouped module metadata from extracted row data."""
    rows_data = json.loads(rows_data_json)
    group_by = json.loads(group_by_json)
    message_level_fields = json.loads(message_level_fields_json)
    signal_level_fields = json.loads(signal_level_fields_json) if signal_level_fields_json else None
    column_mapping = json.loads(column_mapping_json) if column_mapping_json else None
    direction_config = json.loads(direction_config_json) if direction_config_json else None

    result = build_module_metadata_core(
        rows_data=rows_data,
        group_by=group_by,
        message_level_fields=message_level_fields,
        signal_level_fields=signal_level_fields,
        file_path=file_path,
        sheet_name=sheet_name,
        header_row=header_row,
        column_mapping=column_mapping,
        direction_config=direction_config,
    )
    return json.dumps(result, ensure_ascii=False, default=str)
