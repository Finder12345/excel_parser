# -*- coding: utf-8 -*-
"""
获取 Excel sheet 表头文本到列字母的映射。

纯函数，零LLM。
"""
import json
from typing import Dict

from langchain.tools import tool

from .read_sheet import read_sheet_core
from .column_utils import col_index_to_letter_core


# ── 核心纯函数 ──

def get_column_letter_mapping_core(
    file_path: str,
    sheet_name: str,
    header_row: int,
) -> Dict[str, str]:
    """获取表头文本到 Excel 列字母的映射。

    Args:
        file_path: Excel 文件路径
        sheet_name: sheet 名称
        header_row: 表头行号（0-based 索引，即在 read_sheet 返回的二维数组中的行索引）

    Returns:
        {列标题文本: 列字母} 映射
        示例: {"Signal Name": "A", "Start Bit": "B", "Length": "C"}

    Note:
        - 空表头或纯空格的列会被跳过
        - 列字母是 1-based（A=第1列）
    """
    data = read_sheet_core(file_path, sheet_name)
    if header_row >= len(data):
        raise ValueError(f"header_row={header_row} 超出数据范围（共 {len(data)} 行）")

    header = data[header_row]
    mapping = {}
    for col_idx, cell_value in enumerate(header):
        text = str(cell_value).strip() if cell_value else ""
        if text:
            letter = col_index_to_letter_core(col_idx + 1)  # 1-based
            mapping[text] = letter
    return mapping


# ── LangChain @tool 包装 ──

@tool
def get_column_letter_mapping(
    file_path: str,
    sheet_name: str,
    header_row: int,
) -> str:
    """Return sheet header titles mapped to Excel column letters."""
    mapping = get_column_letter_mapping_core(file_path, sheet_name, header_row)
    return json.dumps(mapping, ensure_ascii=False)
