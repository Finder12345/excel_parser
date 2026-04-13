# -*- coding: utf-8 -*-
"""
单字段重解析。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, Optional, Union

from langchain.tools import tool

from .add_trace import add_trace_core
from .normalize_value import normalize_value_core
from .read_source_cell import read_source_cell_core


def _auto_convert(field_name: str, value: Any) -> Any:
    s = "" if value is None else str(value).strip()
    if not s:
        return ""
    lowered = field_name.lower()

    if s.lower().startswith("0x"):
        try:
            return int(s, 16)
        except Exception:
            return s

    if any(k in lowered for k in ["bit", "length", "size", "id", "position"]):
        try:
            return int(float(s))
        except Exception:
            return s

    try:
        if "." in s:
            return float(s)
    except Exception:
        pass

    return s


def reparse_field_core(
    file_path: str,
    sheet_name: str,
    row: int,
    col: Union[int, str],
    field_name: str,
    enum_mappings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src = read_source_cell_core(file_path, sheet_name, row, col)
    raw = src.get("raw_value")

    if enum_mappings:
        value = normalize_value_core(raw, enum_mappings)
    else:
        value = _auto_convert(field_name, raw)

    return add_trace_core(value, "user", file_path, sheet_name, row, str(col))


@tool
def reparse_field(
    file_path: str,
    sheet_name: str,
    row: int,
    col: str,
    field_name: str,
    enum_mappings_json: str = "",
) -> str:
    """Reparse a single field from a source location."""
    enum_map = json.loads(enum_mappings_json) if enum_mappings_json else None
    result = reparse_field_core(file_path, sheet_name, row, col, field_name, enum_map)
    return json.dumps(result, ensure_ascii=False, default=str)
