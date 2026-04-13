# -*- coding: utf-8 -*-
"""去除 trace 包装，输出简化元数据。"""
import json
from typing import Any

from langchain.tools import tool


def simplify_metadata_core(obj: Any) -> Any:
    if isinstance(obj, dict):
        if "value" in obj:
            return simplify_metadata_core(obj["value"])
        return {k: simplify_metadata_core(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [simplify_metadata_core(v) for v in obj]
    return obj


@tool
def simplify_metadata(metadata_json: str) -> str:
    """Strip trace wrappers and simplify metadata values."""
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
    result = simplify_metadata_core(metadata)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)
