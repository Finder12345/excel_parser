# -*- coding: utf-8 -*-
"""
元数据差异对比工具。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List

from langchain.tools import tool

from .json_utils import load_json_core


def _diff(old: Any, new: Any, path: str, changed: List[Dict[str, Any]], added: List[str], removed: List[str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old.keys()) | set(new.keys())
        for k in keys:
            p = f"{path}.{k}" if path else k
            if k not in old:
                added.append(p)
            elif k not in new:
                removed.append(p)
            else:
                _diff(old[k], new[k], p, changed, added, removed)
        return

    if isinstance(old, list) and isinstance(new, list):
        n = max(len(old), len(new))
        for i in range(n):
            p = f"{path}[{i}]"
            if i >= len(old):
                added.append(p)
            elif i >= len(new):
                removed.append(p)
            else:
                _diff(old[i], new[i], p, changed, added, removed)
        return

    if old != new:
        changed.append({"path": path, "old_value": old, "new_value": new})


def diff_metadata_core(old_path: str, new_path: str, module: str = "") -> Dict[str, Any]:
    old_data = load_json_core(old_path)
    new_data = load_json_core(new_path)

    if module:
        old_data = old_data.get(module, {}) if isinstance(old_data, dict) else {}
        new_data = new_data.get(module, {}) if isinstance(new_data, dict) else {}

    changed: List[Dict[str, Any]] = []
    added: List[str] = []
    removed: List[str] = []
    _diff(old_data, new_data, "", changed, added, removed)

    return {
        "changed_fields": changed,
        "added": added,
        "removed": removed,
    }


@tool
def diff_metadata(old_path: str, new_path: str, module: str = "") -> str:
    """Tool wrapper for diff_metadata."""
    result = diff_metadata_core(old_path, new_path, module)
    return json.dumps(result, ensure_ascii=False, default=str)
