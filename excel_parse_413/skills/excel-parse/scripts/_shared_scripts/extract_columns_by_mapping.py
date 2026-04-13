# -*- coding: utf-8 -*-
"""
按字段→列名映射批量提取 Excel 数据行。

根据 Agent 提供的字段映射关系，从指定 sheet 中逐行提取数据，
每行返回一个 {field_name: cell_value} 的 dict。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Optional

from langchain.tools import tool

from .read_sheet import read_sheet_core


# ── 核心纯函数 ──

def extract_columns_by_mapping_core(
    file_path: str,
    sheet_name: str,
    field_mapping: Dict[str, str],
    header_row: int,
    start_row: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """按字段→列标题映射批量提取数据行。

    Args:
        file_path: Excel 文件路径
        sheet_name: sheet 名称
        field_mapping: {标准字段名: Excel列标题}
            示例: {"ShortName": "Signal Name", "BitPosition": "Start Bit"}
            值为空字符串的字段会被跳过（提取结果为 ""）
        header_row: 表头所在行（0-based，read_sheet 返回数据中的行索引）
        start_row: 数据开始行（0-based，默认 header_row + 1）

    Returns:
        List[Dict]，每个 dict 为一行数据：
        [
            {"ShortName": "Sig1", "BitPosition": 0, "_row_index": 5, "_data_index": 0},
            {"ShortName": "Sig2", "BitPosition": 8, "_row_index": 6, "_data_index": 1},
            ...
        ]
        _row_index: 该行在 sheet 二维数组中的 0-based 索引
        _data_index: 该行在数据区的 0-based 序号

    Note:
        - 忽略全空行（所有字段都为空或None）
        - 列标题匹配忽略大小写、忽略前后空格和换行符
    """
    data = read_sheet_core(file_path, sheet_name)
    if header_row >= len(data):
        raise ValueError(f"header_row={header_row} 超出范围（共 {len(data)} 行）")

    header = data[header_row]
    if start_row is None:
        start_row = header_row + 1

    # 建立 列标题 → 列索引 的映射（忽略大小写、空格、换行）
    def _normalize(s: str) -> str:
        return str(s).strip().lower().replace("\n", "").replace("\r", "")

    header_to_idx = {}
    for idx, cell in enumerate(header):
        norm = _normalize(cell) if cell else ""
        if norm:
            header_to_idx[norm] = idx

    # 建立 字段名 → 列索引 的映射
    field_to_col_idx = {}
    for field_name, col_title in field_mapping.items():
        if not col_title:
            continue
        norm_title = _normalize(col_title)
        # 精确匹配
        if norm_title in header_to_idx:
            field_to_col_idx[field_name] = header_to_idx[norm_title]
            continue
        # 包含匹配（表头可能是 "Signal Name\n(信号名称)" 包含 "signal name"）
        for h_norm, h_idx in header_to_idx.items():
            if norm_title in h_norm or h_norm in norm_title:
                field_to_col_idx[field_name] = h_idx
                break

    # 逐行提取
    results = []
    data_index = 0
    for row_idx in range(start_row, len(data)):
        row = data[row_idx]
        row_dict = {}
        all_empty = True

        for field_name, col_title in field_mapping.items():
            if not col_title or field_name not in field_to_col_idx:
                row_dict[field_name] = ""
                continue

            col_idx = field_to_col_idx[field_name]
            cell_value = row[col_idx] if col_idx < len(row) else ""
            row_dict[field_name] = cell_value
            if cell_value is not None and str(cell_value).strip():
                all_empty = False

        if all_empty:
            continue

        # 与原始代码对齐：先打元字段，再按 not value 计算空值率（分母含元字段）
        row_dict["_row_index"] = row_idx
        row_dict["_data_index"] = data_index
        length = len(row_dict)
        if length > 0:
            null_count = sum(1 for value in row_dict.values() if not value)
            if null_count / length > 0.8:
                continue

        results.append(row_dict)
        data_index += 1

    return results


# ── LangChain @tool 包装 ──

@tool
def extract_columns_by_mapping(
    file_path: str,
    sheet_name: str,
    field_mapping_json: str,
    header_row: int,
    start_row: Optional[int] = None,
) -> str:
    """Extract mapped worksheet columns into row dictionaries."""
    mapping = json.loads(field_mapping_json) if isinstance(field_mapping_json, str) else field_mapping_json
    rows = extract_columns_by_mapping_core(file_path, sheet_name, mapping, header_row, start_row)
    return json.dumps(rows, ensure_ascii=False, default=str)
