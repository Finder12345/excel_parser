# -*- coding: utf-8 -*-
"""
溯源信息（trace）添加工具。

为从 Excel 提取的值添加标准化的溯源信息，支持下游定位错误源头。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Optional, Union

from langchain.tools import tool


# ── 核心纯函数 ──

def add_trace_core(
    value: Any,
    value_type: str = "user",
    file: str = "",
    sheet: str = "",
    row: Union[int, str] = 0,
    col: str = "",
) -> Dict:
    """为一个值添加标准化的溯源信息。

    Args:
        value: 原始值（任意类型）
        value_type: 值的来源类型
            - "user": 来自 Excel 用户输入（有明确的 trace 位置）
            - "design": 由程序推导/计算得出
            - "default": 使用了预设默认值
        file: 源 Excel 文件路径
        sheet: 源 sheet 名称
        row: 源行号（1-based Excel 行号）
        col: 源列字母（如 "A", "AA"）

    Returns:
        标准 trace 包装:
        {
            "value": <原始值>,
            "type": "user" | "design" | "default",
            "trace": [{"file": "...", "sheet": "...", "row": 15, "col": "G"}]
        }
    """
    trace_entry = {}
    if file:
        trace_entry["file"] = file
    if row:
        trace_entry["row"] = int(row) if isinstance(row, str) else row
    if col:
        trace_entry["col"] = col
    if sheet:
        trace_entry["sheet"] = sheet

    return {
        "value": value,
        "trace": [trace_entry] if trace_entry else [],
        "type": value_type,
    }


def add_trace_batch_core(
    row_data: Dict[str, Any],
    field_to_col: Dict[str, str],
    file: str,
    sheet: str,
    row: int,
    value_type: str = "user",
) -> Dict[str, Dict]:
    """为一行数据的所有字段批量添加 trace。

    Args:
        row_data: {field_name: value} 一行的数据
        field_to_col: {field_name: col_letter} 字段到列字母的映射
        file: 源文件路径
        sheet: 源 sheet 名
        row: 源行号
        value_type: 值来源类型

    Returns:
        {field_name: {value, type, trace}} 每个字段都包装了 trace
    """
    result = {}
    for field_name, value in row_data.items():
        col = field_to_col.get(field_name, "")
        if col:
            result[field_name] = add_trace_core(value, value_type, file, sheet, row, col)
        else:
            result[field_name] = add_trace_core(value, value_type)
    return result


# ── LangChain @tool 包装 ──

@tool
def add_trace(
    value: str,
    value_type: str = "user",
    file: str = "",
    sheet: str = "",
    row: int = 0,
    col: str = "",
) -> str:
    """为值添加溯源信息。返回包含 {value, type, trace} 的 JSON 字符串。

    Args:
        value: 原始值
        value_type: 来源类型（user=Excel输入, design=推导, default=默认值）
        file: 源 Excel 文件路径
        sheet: 源 sheet 名
        row: 源行号（1-based）
        col: 源列字母（如 "A", "G"）
    """
    result = add_trace_core(value, value_type, file, sheet, row, col)
    return json.dumps(result, ensure_ascii=False)
