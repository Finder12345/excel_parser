# -*- coding: utf-8 -*-
"""
路由矩阵元数据构建工具。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Union

from langchain.tools import tool

from .column_utils import col_index_to_letter_core, col_letter_to_index_core
from .read_sheet import read_sheet_core


def _col_to_index(col: Union[int, str]) -> int:
    if isinstance(col, int):
        return col
    return col_letter_to_index_core(str(col))


def _safe_cell(data: List[List[Any]], row_1based: int, col_1based: int) -> Any:
    r = row_1based - 1
    c = col_1based - 1
    if r < 0 or r >= len(data):
        return ""
    row = data[r]
    if c < 0 or c >= len(row):
        return ""
    return row[c]


def build_routing_metadata_core(file_path: str, layout_config: Dict[str, Any], sheet_name: str) -> Dict[str, Any]:
    """按布局配置扫描矩阵，构建 gw_mapping 与 route_info。"""
    data = read_sheet_core(file_path, sheet_name)

    data_start_row = int(layout_config.get("dataContentStartRow", 1))
    channel_row = int(layout_config.get("channelNameInfoRow", 1))
    matrix_start_col = _col_to_index(layout_config.get("matrixStartCol", 1))
    matrix_end_col = _col_to_index(layout_config.get("matrixEndCol", matrix_start_col))

    ids = layout_config.get("identifiers", {})
    source_marker = str(ids.get("source_marker", "S")).lower()
    destination_marker = str(ids.get("destination_marker", "D")).lower()
    both_marker = str(ids.get("both_marker", "S/D")).lower()

    field_cols = {
        "sourceSignalName": layout_config.get("sourceSignalNameCol"),
        "sourcePduName": layout_config.get("sourcePduNameCol"),
        "sourcePduId": layout_config.get("sourcePduIdCol"),
        "destinationSignalName": layout_config.get("destinationSignalNameCol"),
        "destinationPduName": layout_config.get("destinationPduNameCol"),
        "destinationPduId": layout_config.get("destinationPduIdCol"),
        "routeType": layout_config.get("routeTypeCol"),
        "isLLCE": layout_config.get("isLLCECol"),
    }
    field_cols = {k: _col_to_index(v) for k, v in field_cols.items() if v is not None}

    channel_names: Dict[int, str] = {}
    for c in range(matrix_start_col, matrix_end_col + 1):
        raw = _safe_cell(data, channel_row, c)
        name = str(raw).strip() if raw is not None else ""
        if not name:
            name = f"CH_{col_index_to_letter_core(c)}"
        channel_names[c] = name

    route_info: List[Dict[str, Any]] = []
    gw_mapping: Dict[str, Dict[str, List[str]]] = {}

    for r in range(data_start_row, len(data) + 1):
        base: Dict[str, Any] = {}
        for f, c in field_cols.items():
            base[f] = _safe_cell(data, r, c)

        source_channels: List[str] = []
        destination_channels: List[str] = []
        hit = False

        for c in range(matrix_start_col, matrix_end_col + 1):
            mark_raw = _safe_cell(data, r, c)
            mark = str(mark_raw).strip().lower() if mark_raw is not None else ""
            if not mark:
                continue

            ch = channel_names[c]
            if mark == both_marker:
                source_channels.append(ch)
                destination_channels.append(ch)
                hit = True
            else:
                if source_marker and source_marker in mark:
                    source_channels.append(ch)
                    hit = True
                if destination_marker and destination_marker in mark:
                    destination_channels.append(ch)
                    hit = True

        # 没有矩阵标记且基础字段也空，认为是尾部空行
        if not hit and not any(str(v).strip() for v in base.values()):
            continue

        item = {
            **base,
            "sourceChannels": sorted(set(source_channels)),
            "destinationChannels": sorted(set(destination_channels)),
            "_row": r,
        }
        route_info.append(item)

        for ch in item["sourceChannels"]:
            gw_mapping.setdefault(ch, {"tx": [], "rx": []})
            sig = str(base.get("sourceSignalName", "")).strip()
            if sig and sig not in gw_mapping[ch]["tx"]:
                gw_mapping[ch]["tx"].append(sig)
        for ch in item["destinationChannels"]:
            gw_mapping.setdefault(ch, {"tx": [], "rx": []})
            sig = str(base.get("sourceSignalName", "")).strip()
            if sig and sig not in gw_mapping[ch]["rx"]:
                gw_mapping[ch]["rx"].append(sig)

    return {"gw_mapping": gw_mapping, "route_info": route_info}


@tool
def build_routing_metadata(file_path: str, layout_config_json: str, sheet_name: str) -> str:
    """Tool wrapper for build_routing_metadata."""
    cfg = json.loads(layout_config_json) if isinstance(layout_config_json, str) else layout_config_json
    result = build_routing_metadata_core(file_path, cfg, sheet_name)
    return json.dumps(result, ensure_ascii=False, default=str)
