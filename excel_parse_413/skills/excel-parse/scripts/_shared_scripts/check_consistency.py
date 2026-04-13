# -*- coding: utf-8 -*-
"""
跨源一致性检查工具。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Optional

from langchain.tools import tool

from .json_utils import load_json_core, save_json_core


def _join_path(base: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]" if base else f"[{key}]"
    return f"{base}.{key}" if base else str(key)


def _collect_diff(a: Any, b: Any, path: str, diffs: List[Dict[str, Any]]) -> None:
    if type(a) != type(b):
        diffs.append({"path": path or "<root>", "type": "type_mismatch", "a": a, "b": b})
        return

    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            p = _join_path(path, k)
            if k not in a:
                diffs.append({"path": p, "type": "missing_in_a", "a": None, "b": b.get(k)})
            elif k not in b:
                diffs.append({"path": p, "type": "missing_in_b", "a": a.get(k), "b": None})
            else:
                _collect_diff(a[k], b[k], p, diffs)
        return

    if isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            p = _join_path(path, i)
            if i >= len(a):
                diffs.append({"path": p, "type": "missing_in_a", "a": None, "b": b[i]})
            elif i >= len(b):
                diffs.append({"path": p, "type": "missing_in_b", "a": a[i], "b": None})
            else:
                _collect_diff(a[i], b[i], p, diffs)
        return

    if a != b:
        diffs.append({"path": path or "<root>", "type": "value_mismatch", "a": a, "b": b})


def check_consistency_core(
    source_a_path: str,
    source_b_path: Optional[str] = None,
    conflict_report_path: str = "",
) -> Dict[str, Any]:
    data_a = load_json_core(source_a_path)
    if not source_b_path:
        return {"consistent": True, "conflict_report_path": "", "conflicts": []}

    data_b = load_json_core(source_b_path)
    conflicts: List[Dict[str, Any]] = []
    _collect_diff(data_a, data_b, "", conflicts)
    consistent = len(conflicts) == 0

    report_path = ""
    if not consistent and conflict_report_path:
        report = {
            "source_a_path": source_a_path,
            "source_b_path": source_b_path,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
        }
        report_path = save_json_core(report, conflict_report_path)

    return {
        "consistent": consistent,
        "conflict_report_path": report_path if report_path else ("" if consistent else "in-memory-diff"),
        "conflicts": conflicts,
    }


@tool
def check_consistency(source_a_path: str, source_b_path: str = "", conflict_report_path: str = "") -> str:
    """Tool wrapper for check_consistency."""
    result = check_consistency_core(source_a_path, source_b_path or None, conflict_report_path)
    return json.dumps(result, ensure_ascii=False, default=str)
