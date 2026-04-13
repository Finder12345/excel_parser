# -*- coding: utf-8 -*-
"""
NVM 最终后处理工具。

将识别后的 nvm_datas 结构收敛为与原始实现接近的 legacy wrapped 输出语义。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List

from langchain.tools import tool

from .add_trace import add_trace_core
from .column_utils import col_index_to_letter_core
from .extract_columns_by_mapping import extract_columns_by_mapping_core
from .get_column_letter_mapping import get_column_letter_mapping_core
from .read_sheet import read_sheet_core


def _wrap_common_value(value: Dict[str, Any], file_path: str, sheet_name: str) -> Dict[str, Any]:
    column = value.get("column")
    col_name = ""
    if isinstance(column, int) and column > 0:
        col_name = col_index_to_letter_core(column)
    elif isinstance(column, str) and column:
        col_name = column
    return add_trace_core(value.get("value"), "user", file_path, sheet_name, value.get("row"), col_name)


def _flatten_headers(table_data: List[List[Any]], header_indices: List[int]) -> List[str]:
    if not table_data or not header_indices:
        return []
    header_rows = []
    for idx in header_indices:
        if 0 <= idx < len(table_data):
            header_rows.append(table_data[idx])
        else:
            raise IndexError(f"Header index {idx + 1} is out of table range")

    headers = []
    for col_idx in range(len(header_rows[0]) if header_rows else 0):
        if len(header_rows) == 1:
            header = str(header_rows[0][col_idx])
        else:
            header_parts = []
            for row_idx in range(len(header_rows)):
                if col_idx < len(header_rows[row_idx]):
                    header_parts.append(str(header_rows[row_idx][col_idx]))
                else:
                    header_parts.append("")
            header_parts.reverse()
            new_headers = [header_parts[0]]
            for part in range(1, len(header_parts)):
                if header_parts[part] != header_parts[part - 1]:
                    new_headers.append(header_parts[part])
            header = "_".join(new_headers)
        headers.append(header)
    return headers


def _build_header_letter_mapping(headers: List[str]) -> Dict[str, str]:
    mapping = {}
    for idx, text in enumerate(headers):
        if text:
            mapping[text] = col_index_to_letter_core(idx + 1)
    return mapping


def _wrap_block_rows(
    rows: List[Dict[str, Any]],
    field_mapping: Dict[str, str],
    header_index: int,
    file_path: str,
    sheet_name: str,
    column_mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    result = []
    for index, row in enumerate(rows):
        item = dict(row)
        real_index = item.pop("_data_index", index)
        item.pop("_row_index", None)
        wrapped = {}
        for key, val in item.items():
            title_name = field_mapping.get(key, "")
            if title_name:
                wrapped[key] = add_trace_core(
                    None if val == "" else val,
                    "user",
                    file_path,
                    sheet_name,
                    real_index + header_index + 2,
                    column_mapping.get(title_name, ""),
                )
            else:
                wrapped[key] = add_trace_core(val, "user")
        result.append(wrapped)
    return result


def finalize_nvm_metadata_core(nvm_datas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(nvm_datas, list):
        return []

    result = []
    for nvm_data in nvm_datas:
        if not isinstance(nvm_data, dict):
            continue
        item = json.loads(json.dumps(nvm_data, ensure_ascii=False))
        file_path = item.get("file_path", "")
        main_data = item.get("main_data", {})
        for sheet_name, sheet_main_data in (main_data or {}).items():
            if not isinstance(sheet_main_data, dict):
                continue
            common_data = sheet_main_data.get("common") or {}
            for key, value in list(common_data.items()):
                if isinstance(value, dict) and "column" in value and "row" in value:
                    common_data[key] = _wrap_common_value(value, file_path, sheet_name)

            block_data = sheet_main_data.get("block", {})
            headers = block_data.get("headers") if isinstance(block_data, dict) else None
            fields = block_data.get("fields") if isinstance(block_data, dict) else None
            if not headers or not fields:
                continue

            sheet_data = read_sheet_core(file_path, sheet_name)
            flattened_headers = _flatten_headers(sheet_data, headers)
            if headers[-1] < len(sheet_data):
                sheet_data[headers[-1]] = flattened_headers
            column_mapping = _build_header_letter_mapping(flattened_headers)
            extracted = extract_columns_by_mapping_core(file_path, sheet_name, fields, headers[-1])
            sheet_main_data["block"] = _wrap_block_rows(
                extracted, fields, headers[-1], file_path, sheet_name, column_mapping
            )
        result.append(item)
    return result


@tool
def finalize_nvm_metadata(nvm_datas_json: str) -> str:
    """Finalize NVM metadata into legacy-compatible wrapped output."""
    nvm_datas = json.loads(nvm_datas_json) if isinstance(nvm_datas_json, str) else nvm_datas_json
    result = finalize_nvm_metadata_core(nvm_datas)
    return json.dumps(result, ensure_ascii=False, default=str)
