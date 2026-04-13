# -*- coding: utf-8 -*-
"""
Excel 列号与列字母互转工具。

纯函数，零依赖，零LLM。
"""
import json

from langchain.tools import tool


def col_index_to_letter_core(index: int) -> str:
    """将 1-based 列索引转换为 Excel 列字母。"""
    result = ""
    while index > 0:
        index -= 1
        result = chr(index % 26 + 65) + result
        index //= 26
    return result


def col_letter_to_index_core(letter: str) -> int:
    """将 Excel 列字母转换为 1-based 列索引。"""
    result = 0
    for ch in letter.upper():
        result = result * 26 + (ord(ch) - 64)
    return result


@tool
def col_index_to_letter(index: int) -> str:
    """Convert a 1-based column index to an Excel column letter."""
    return col_index_to_letter_core(index)


@tool
def col_letter_to_index(letter: str) -> str:
    """Convert an Excel column letter to a 1-based column index."""
    return json.dumps(col_letter_to_index_core(letter))
