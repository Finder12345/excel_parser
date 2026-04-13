# -*- coding: utf-8 -*-
"""
汇总各模块元数据为完整输出结构。

纯函数，零LLM。
"""
import json
from typing import Any, Dict

from langchain.tools import tool


def _deep_copy(data: Any) -> Any:
    return json.loads(json.dumps(data, ensure_ascii=False))


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            _deep_merge(target[k], v)
        elif k in target and isinstance(target[k], list) and isinstance(v, list):
            target[k] = v
        else:
            target[k] = v
    return target


def _set_by_path(root: Dict[str, Any], dotted_path: str, value: Any) -> None:
    keys = [k for k in dotted_path.split(".") if k]
    if not keys:
        return
    cur = root
    for key in keys[:-1]:
        next_node = cur.get(key)
        if not isinstance(next_node, dict):
            next_node = {}
            cur[key] = next_node
        cur = next_node
    cur[keys[-1]] = value


def assemble_full_metadata_core(module_results: Dict[str, Any], template_schema: Dict[str, Any]) -> Dict[str, Any]:
    result = _deep_copy(template_schema) if template_schema else {}

    if not isinstance(module_results, dict):
        return result

    for key, value in module_results.items():
        if isinstance(key, str) and "." in key:
            _set_by_path(result, key, value)
            continue

        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


@tool
def assemble_full_metadata(module_results_json: str, template_schema_json: str) -> str:
    """Tool wrapper for assemble_full_metadata."""
    module_results = json.loads(module_results_json) if isinstance(module_results_json, str) else module_results_json
    template_schema = json.loads(template_schema_json) if isinstance(template_schema_json, str) else template_schema_json
    out = assemble_full_metadata_core(module_results, template_schema)
    return json.dumps(out, ensure_ascii=False, default=str)
