# -*- coding: utf-8 -*-
"""确定性枚举标准化工具。"""
import json
from difflib import get_close_matches
from typing import Any, Dict

from langchain.tools import tool


def normalize_value_core(raw_value: Any, enum_mappings: Dict[str, Any]) -> Any:
    if raw_value is None:
        return raw_value
    s = str(raw_value).strip()
    if s in enum_mappings:
        return enum_mappings[s]
    lower_map = {str(k).lower(): v for k, v in enum_mappings.items()}
    if s.lower() in lower_map:
        return lower_map[s.lower()]
    normalized = s.replace('_', '').replace(' ', '').lower()
    compact_map = {str(k).replace('_', '').replace(' ', '').lower(): v for k, v in enum_mappings.items()}
    if normalized in compact_map:
        return compact_map[normalized]
    close = get_close_matches(normalized, list(compact_map.keys()), n=1, cutoff=0.8)
    if close:
        return compact_map[close[0]]
    return "UNKNOWN"


@tool
def normalize_value(raw_value: str, enum_mappings_json: str) -> str:
    """Normalize a raw value against enum mappings and return JSON."""
    enum_mappings = json.loads(enum_mappings_json)
    result = normalize_value_core(raw_value, enum_mappings)
    return json.dumps(result, ensure_ascii=False, default=str)
