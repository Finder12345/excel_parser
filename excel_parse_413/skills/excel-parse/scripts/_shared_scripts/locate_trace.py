# -*- coding: utf-8 -*-
"""根据字段路径定位元数据中的 trace 信息。"""
import json
from typing import Any

from langchain.tools import tool


def _walk_path(data: Any, path: str) -> Any:
    current = data
    for part in path.replace(']', '').split('.'):
        if '[' in part:
            key, idx = part.split('[')
            current = current[key][int(idx)]
        else:
            current = current[part]
    return current


def locate_trace_core(metadata_path: str, field_path: str) -> Any:
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    return _walk_path(metadata, field_path)


@tool
def locate_trace(metadata_path: str, field_path: str) -> str:
    """Locate trace information for a metadata field path."""
    result = locate_trace_core(metadata_path, field_path)
    return json.dumps(result, ensure_ascii=False, default=str)
