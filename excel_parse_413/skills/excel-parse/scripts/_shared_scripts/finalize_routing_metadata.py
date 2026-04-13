# -*- coding: utf-8 -*-
"""
CAN 路由最终后处理工具。

将 build_routing_metadata 的中间结构重组为与原始
scan_routing_table/transform_routing_data 对齐的最终结果。

纯函数，零LLM。
"""
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from langchain.tools import tool

from .add_trace import add_trace_core


def _normalize_field_to_col(field_to_col: Dict[str, Any]) -> Dict[str, str]:
    normalized = dict(field_to_col or {})
    if "routingType" not in normalized and "routeType" in normalized:
        normalized["routingType"] = normalized["routeType"]
    return normalized


def _trace_value(
    row: Dict[str, Any],
    field_name: str,
    file_path: str,
    sheet_name: str,
    field_to_col: Dict[str, str],
) -> Dict[str, Any]:
    value = row.get(field_name)
    if value == "":
        value = None
    return add_trace_core(
        value,
        "user",
        file_path,
        sheet_name,
        row.get("_row", 0),
        field_to_col.get(field_name, ""),
    )


def _build_trace_route(
    row: Dict[str, Any],
    source_channel: Optional[str],
    destination_channel: Optional[str],
    file_path: str,
    sheet_name: str,
    field_to_col: Dict[str, str],
) -> Dict[str, Any]:
    routing_type = _trace_value(row, "routeType", file_path, sheet_name, field_to_col)
    return {
        "sourceChannelName": add_trace_core(source_channel, "user", file_path, sheet_name, row.get("_row", 0)),
        "sourceSignalName": _trace_value(row, "sourceSignalName", file_path, sheet_name, field_to_col),
        "sourcePduName": _trace_value(row, "sourcePduName", file_path, sheet_name, field_to_col),
        "routingType": routing_type,
        "sourcePduId": _trace_value(row, "sourcePduId", file_path, sheet_name, field_to_col),
        "destinationChannelName": [
            add_trace_core(destination_channel, "user", file_path, sheet_name, row.get("_row", 0))
        ],
        "destinationPduName": _trace_value(row, "destinationPduName", file_path, sheet_name, field_to_col),
        "destinationSignalName": _trace_value(row, "destinationSignalName", file_path, sheet_name, field_to_col),
        "destinationPduId": _trace_value(row, "destinationPduId", file_path, sheet_name, field_to_col),
        "isLLCE": _trace_value(row, "isLLCE", file_path, sheet_name, field_to_col),
    }


def _add_target_info(
    destination_channel_name: Dict[str, Any],
    route: Dict[str, Any],
    source_groups: Dict[Any, List[Dict[str, Any]]],
    source_key: Any,
) -> None:
    for target_info in source_groups[source_key]:
        if (
            target_info.get("destinationChannelName", {}).get("value") == destination_channel_name.get("value")
            and target_info.get("destinationPduName", {}).get("value") == route.get("destinationPduName", {}).get("value")
            and target_info.get("destinationSignalName", {}).get("value") == route.get("destinationSignalName", {}).get("value")
        ):
            return

    source_groups[source_key].append(
        {
            "destinationChannelName": destination_channel_name,
            "destinationPduName": route.get("destinationPduName", {"value": None}),
            "destinationSignalName": route.get("destinationSignalName", {"value": None}),
            "routingType": route.get("routingType", {"value": None}),
            "destinationPduId": route.get("destinationPduId", {"value": None}),
            "isLLCE": route.get("isLLCE", {"value": None}),
        }
    )


def _transform_routing_data(input_json: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    result = {}
    for route_type, routes in (input_json or {}).items():
        source_info_map = {}
        for route in routes:
            key = (
                route.get("sourceChannelName", {}).get("value"),
                route.get("sourceSignalName", {}).get("value"),
                route.get("sourcePduName", {}).get("value"),
                route.get("routingType", {}).get("value"),
            )
            if key not in source_info_map:
                source_info_map[key] = {
                    "sourceChannelName": route.get("sourceChannelName", {"value": None}),
                    "sourceSignalName": route.get("sourceSignalName", {"value": None}),
                    "sourcePduName": route.get("sourcePduName", {"value": None}),
                    "routingType": route.get("routingType", {"value": None}),
                    "sourcePduId": route.get("sourcePduId", {"value": None}),
                }

        source_groups = defaultdict(list)
        for route in routes:
            source_key = (
                route.get("sourceChannelName", {}).get("value"),
                route.get("sourceSignalName", {}).get("value"),
                route.get("sourcePduName", {}).get("value"),
                route.get("routingType", {}).get("value"),
            )
            for destination_channel_name in route.get("destinationChannelName", []):
                _add_target_info(destination_channel_name, route, source_groups, source_key)

        output = []
        for source_key, targets in source_groups.items():
            source_info = source_info_map.get(source_key)
            if source_info is None:
                continue
            output.append({"source": source_info, "targets": targets})
        result[route_type] = output
    return result


def finalize_routing_metadata_core(
    route_info_data: Any,
    file_path: str,
    sheet_name: str,
    field_to_col: Optional[Dict[str, Any]] = None,
    default_route_group: str = "Default",
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    field_to_col = _normalize_field_to_col(field_to_col or {})
    routing_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    pdur_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in route_info_data or []:
        route_group = row.get("routeGroup") or default_route_group
        source_channels = row.get("sourceChannels") or [None]
        destination_channels = row.get("destinationChannels") or [None]

        for source_channel in source_channels:
            for destination_channel in destination_channels:
                trace_route = _build_trace_route(
                    row,
                    source_channel,
                    destination_channel,
                    file_path,
                    sheet_name,
                    field_to_col,
                )
                routing_type_value = trace_route.get("routingType", {}).get("value")
                if str(routing_type_value) == "0":
                    pdur_rows[route_group].append(trace_route)
                else:
                    routing_rows[route_group].append(trace_route)

    return {
        "SignalGateWay": _transform_routing_data(dict(routing_rows)),
        "PduGateWay": _transform_routing_data(dict(pdur_rows)),
    }


@tool
def finalize_routing_metadata(
    route_info_json: str,
    file_path: str,
    sheet_name: str,
    field_to_col_json: str = "{}",
    default_route_group: str = "Default",
) -> str:
    """Finalize routing metadata into legacy-compatible output."""
    route_info_data = json.loads(route_info_json) if isinstance(route_info_json, str) else route_info_json
    field_to_col = json.loads(field_to_col_json) if isinstance(field_to_col_json, str) else field_to_col_json
    result = finalize_routing_metadata_core(
        route_info_data,
        file_path,
        sheet_name,
        field_to_col,
        default_route_group,
    )
    return json.dumps(result, ensure_ascii=False, default=str)
