# -*- coding: utf-8 -*-
"""
字段映射完整性验证工具。

检查 Agent 提供的字段映射是否覆盖了足够多的期望字段。

纯函数，零LLM。
"""
import json
from typing import Dict, List

from langchain.tools import tool


# ── 核心纯函数 ──

def validate_field_mapping_core(
    mapping: Dict[str, str],
    expected_fields: List[str],
    threshold: float = 0.8,
    required_fields: List[str] = None,
) -> Dict:
    """验证字段映射的完整性。

    Args:
        mapping: {字段名: 映射到的列标题} Agent 提供的映射
        expected_fields: 期望的所有字段名列表
        threshold: 最低覆盖率（0~1），低于此值判定为不合格
        required_fields: 必须映射的字段列表（即使总覆盖率达标，
                         缺少必填字段仍判定为不合格）

    Returns:
        {
            "valid": bool,       # 是否达标
            "coverage": float,   # 实际覆盖率（0~1）
            "total": int,        # 期望字段总数
            "mapped": int,       # 已映射字段数
            "missing": [str],    # 未映射的字段列表
            "missing_required": [str],  # 未映射的必填字段
        }
    """
    if not expected_fields:
        return {"valid": True, "coverage": 1.0, "total": 0, "mapped": 0,
                "missing": [], "missing_required": []}

    if required_fields is None:
        required_fields = []

    missing = []
    mapped_count = 0
    for field in expected_fields:
        val = mapping.get(field, "")
        if val and str(val).strip():
            mapped_count += 1
        else:
            missing.append(field)

    coverage = mapped_count / len(expected_fields)
    missing_required = [f for f in required_fields if f in missing]
    valid = coverage >= threshold and len(missing_required) == 0

    return {
        "valid": valid,
        "coverage": round(coverage, 4),
        "total": len(expected_fields),
        "mapped": mapped_count,
        "missing": missing,
        "missing_required": missing_required,
    }


# ── LangChain @tool 包装 ──

@tool
def validate_field_mapping(
    mapping_json: str,
    expected_fields_json: str,
    threshold: float = 0.8,
    required_fields_json: str = "[]",
) -> str:
    """Validate field mapping coverage and required fields."""
    mapping = json.loads(mapping_json)
    expected = json.loads(expected_fields_json)
    required = json.loads(required_fields_json) if required_fields_json else []
    result = validate_field_mapping_core(mapping, expected, threshold, required)
    return json.dumps(result, ensure_ascii=False)
