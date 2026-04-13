# -*- coding: utf-8 -*-
"""
获取 Excel sheet 表头区域样本。

返回左上角的 N×M 区域数据，供 Agent 分析表头结构。

纯函数，零LLM。
"""
import json
from typing import Any, List, Optional

from langchain.tools import tool

from .read_sheet import read_sheet_core


# ── 核心纯函数 ──

def get_header_sample_core(
    file_path: str,
    sheet_name: str,
    sample_rows: int = 10,
    sample_cols: int = 20,
) -> List[List[Any]]:
    """获取 Excel sheet 表头区域样本。

    读取 sheet 后截取左上角 sample_rows × sample_cols 的区域，
    供 Agent 或人工分析表头方向、表头行号等结构信息。

    Args:
        file_path: Excel 文件路径
        sheet_name: sheet 名称
        sample_rows: 样本行数（默认10行）
        sample_cols: 样本列数（默认20列）

    Returns:
        二维列表，左上角 sample_rows × sample_cols 区域
    """
    return read_sheet_core(file_path, sheet_name, max_rows=sample_rows, max_cols=sample_cols)


# ── LangChain @tool 包装 ──

@tool
def get_header_sample(
    file_path: str,
    sheet_name: str,
    sample_rows: int = 10,
    sample_cols: int = 20,
) -> str:
    """Read a top-left worksheet sample for header analysis."""
    data = get_header_sample_core(file_path, sheet_name, sample_rows, sample_cols)
    return json.dumps(data, ensure_ascii=False, default=str)
