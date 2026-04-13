# -*- coding: utf-8 -*-
"""
单行重解析。

纯函数，零LLM。
"""
import json
import re
from typing import Any, Dict

from langchain.tools import tool

from .add_trace import add_trace_core
from .get_column_letter_mapping import get_column_letter_mapping_core
from .read_source_cell import read_source_cell_core


def _is_col_letter(v: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]+", str(v).strip()))


def reparse_row_core(
    file_path: str,
    sheet_name: str,
    row: int,
    field_mapping: Dict[str, str],
    header_row: int,
) -> Dict[str, Any]:
    title_to_letter = get_column_letter_mapping_core(file_path, sheet_name, header_row)
    out: Dict[str, Any] = {}

    for field, mapped in field_mapping.items():
        col = mapped if _is_col_letter(mapped) else title_to_letter.get(str(mapped), "")
        if not col:
            out[field] = add_trace_core("", "user", file_path, sheet_name, row, "")
            continue
        raw = read_source_cell_core(file_path, sheet_name, row, col).get("raw_value")
        out[field] = add_trace_core(raw, "user", file_path, sheet_name, row, col)

    return out


@tool
def reparse_row(file_path: str, sheet_name: str, row: int, field_mapping_json: str, header_row: int) -> str:
    """Tool wrapper for reparse_row."""
    mapping = json.loads(field_mapping_json)
    result = reparse_row_core(file_path, sheet_name, row, mapping, header_row)
    return json.dumps(result, ensure_ascii=False, default=str)
