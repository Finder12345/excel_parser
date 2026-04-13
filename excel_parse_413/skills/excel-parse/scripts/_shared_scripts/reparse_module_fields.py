# -*- coding: utf-8 -*-
"""
模块指定字段批量重解析。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Optional

from langchain.tools import tool

from .add_trace import add_trace_core
from .extract_columns_by_mapping import extract_columns_by_mapping_core
from .get_column_letter_mapping import get_column_letter_mapping_core


def reparse_module_fields_core(
    file_path: str,
    sheet_name: str,
    field_names: List[str],
    field_mapping: Dict[str, str],
    header_row: int,
    start_row: Optional[int] = None,
) -> List[Dict[str, Any]]:
    sub_mapping = {f: field_mapping.get(f, "") for f in field_names}
    rows = extract_columns_by_mapping_core(file_path, sheet_name, sub_mapping, header_row, start_row)
    title_to_letter = get_column_letter_mapping_core(file_path, sheet_name, header_row)

    out: List[Dict[str, Any]] = []
    for row in rows:
        excel_row = int(row.get("_row_index", 0)) + 1
        obj: Dict[str, Any] = {}
        for f in field_names:
            title = sub_mapping.get(f, "")
            col = title_to_letter.get(title, "") if title else ""
            obj[f] = add_trace_core(row.get(f, ""), "user", file_path, sheet_name, excel_row, col)
        out.append(obj)
    return out


@tool
def reparse_module_fields(
    file_path: str,
    sheet_name: str,
    field_names_json: str,
    field_mapping_json: str,
    header_row: int,
    start_row: int = 0,
) -> str:
    """Reparse selected fields across a module worksheet."""
    field_names = json.loads(field_names_json)
    field_mapping = json.loads(field_mapping_json)
    st = start_row if start_row > 0 else None
    result = reparse_module_fields_core(file_path, sheet_name, field_names, field_mapping, header_row, st)
    return json.dumps(result, ensure_ascii=False, default=str)
