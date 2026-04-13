# -*- coding: utf-8 -*-
"""
按字段交集匹配两组数据。

典型用途：将 LIN 调度表匹配到对应的 LIN 信号通道（按帧名交集率）。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Set

from langchain.tools import tool


# ── 核心纯函数 ──

def match_by_intersection_core(
    data_a: Dict[str, List[str]],
    data_b: Dict[str, Set[str]],
    min_rate: float = 0.0,
) -> Dict[str, str]:
    """按字段值交集率将 data_a 中的每个 key 匹配到 data_b 中最佳的 key。

    Args:
        data_a: {name_a: [values...]} 待匹配方
            示例: {"调度表": ["CCU_LIN1_1", "RLS_1", "RLS_2"]}
        data_b: {name_b: set(values)} 目标方
            示例: {"LIN1": {"CCU_LIN1_1", "RLS_1", "RLS_2", "RLS_3"},
                   "LIN2": {"CCU_LIN2_1", "SSM_1"}}
        min_rate: 最小交集率阈值，低于此值不匹配

    Returns:
        {name_a: name_b} 匹配结果
        示例: {"调度表": "LIN1"}

    Note:
        交集率 = len(A ∩ B) / len(B)
        取交集率最高的作为匹配结果
    """
    result = {}
    for a_name, a_values in data_a.items():
        a_set = set(a_values)
        best_match = ""
        best_rate = -1.0

        for b_name, b_values in data_b.items():
            b_set = b_values if isinstance(b_values, set) else set(b_values)
            if not b_set:
                continue
            rate = len(a_set & b_set) / len(b_set)
            if rate > best_rate:
                best_rate = rate
                best_match = b_name

        if best_rate > min_rate and best_match:
            result[a_name] = best_match

    return result


# ── LangChain @tool 包装 ──

@tool
def match_by_intersection(
    data_a_json: str,
    data_b_json: str,
    min_rate: float = 0.0,
) -> str:
    """Match groups by intersection overlap and return best matches."""
    data_a = json.loads(data_a_json)
    data_b = json.loads(data_b_json)
    # 将 data_b 的 list 转为 set
    data_b_sets = {k: set(v) for k, v in data_b.items()}
    result = match_by_intersection_core(data_a, data_b_sets, min_rate)
    return json.dumps(result, ensure_ascii=False)
