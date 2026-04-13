# -*- coding: utf-8 -*-
"""
将 sheet 转为列导向 JSON 结构。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List

from langchain.tools import tool

from .column_utils import col_index_to_letter_core
from .read_sheet import read_sheet_core


def sheet_to_column_json_core(file_path: str, sheet_name: str, max_rows: int = 10) -> Dict[str, Any]:
    """将指定 sheet 的前 N 行转换为列导向结构。"""
    data = read_sheet_core(file_path, sheet_name)
    if not data:
        result = {"json_str": "{}", "row_count": 0, "col_count": 0}
        return result

    row_count = min(len(data), max_rows) if max_rows and max_rows > 0 else len(data)
    sample = data[:row_count]
    col_count = max((len(r) for r in sample), default=0)

    columns: Dict[str, List[Any]] = {}
    for col_idx in range(1, col_count + 1):
        col_letter = col_index_to_letter_core(col_idx)
        col_values: List[Any] = []
        for row in sample:
            value = row[col_idx - 1] if col_idx - 1 < len(row) else ""
            col_values.append(value)
        columns[col_letter] = col_values

    return {
        "json_str": json.dumps(columns, ensure_ascii=False, default=str),
        "row_count": row_count,
        "col_count": col_count,
    }


@tool
def sheet_to_column_json(file_path: str, sheet_name: str, max_rows: int = 10) -> str:
    """Convert a worksheet sample into column-oriented JSON."""
    result = sheet_to_column_json_core(file_path, sheet_name, max_rows)
    return json.dumps(result, ensure_ascii=False, default=str)
