# -*- coding: utf-8 -*-
"""
LIN 最终后处理工具。

将 build_module_metadata 的通用分组结果收敛为与原始实现接近的 LIN wrapped 输出语义，
并提供 schedule 的最终清理能力。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List

from langchain.tools import tool

from .add_trace import add_trace_core
from .column_utils import col_index_to_letter_core
from .match_by_intersection import match_by_intersection_core

_MESSAGE_KEYS = [
    "EcuName", "FrameName", "LinId", "ProtectedId", "MsgSendType",
    "FrameLength", "FrameSendType", "FrameCycleTime",
]


def _unwrap(v: Any) -> Any:
    if isinstance(v, dict) and {"value", "type", "trace"}.issubset(v.keys()):
        return v.get("value")
    return v


def _clean_signal(signal: Dict[str, Any], message_keys: List[str]) -> Dict[str, Any]:
    return {
        k: v for k, v in signal.items()
        if k not in set(message_keys) | {"index", "_row_index", "_data_index", "direction"}
    }


def finalize_lin_metadata_core(
    grouped_lin_data: Dict[str, Any],
    message_keys: List[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    message_keys = message_keys or list(_MESSAGE_KEYS)
    result = {"TX": [], "RX": []}

    if not isinstance(grouped_lin_data, dict):
        return result

    for direction in ["TX", "RX"]:
        messages = grouped_lin_data.get(direction, [])
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            out = {k: message.get(k) for k in message_keys if k in message}
            signals = message.get("signals", [])
            if not isinstance(signals, list):
                signals = []
            out["signals"] = [_clean_signal(signal, message_keys) for signal in signals if isinstance(signal, dict)]
            result[direction].append(out)

    return result


def _wrap_schedule_value(value: Any, file_path: str, sheet_name: str, row: Any, col: Any) -> Dict[str, Any]:
    col_name = col if isinstance(col, str) else col_index_to_letter_core(int(col)) if col else ""
    return add_trace_core(value, "user", file_path, sheet_name, row, col_name)


def finalize_lin_schedule_core(
    lin_schedule_info: Dict[str, List[Dict[str, Any]]],
    lin_channel_frame_name_info: Dict[str, List[str]],
    file_path: str,
    min_rate: float = 0.0,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    if not lin_schedule_info:
        return {}

    schedule_frames = {
        sheet_name: [item.get("frame_name") for item in items if isinstance(item, dict) and item.get("frame_name")]
        for sheet_name, items in lin_schedule_info.items()
    }
    channel_frames = {k: set(v) for k, v in (lin_channel_frame_name_info or {}).items()}
    matched = match_by_intersection_core(schedule_frames, channel_frames, min_rate)

    result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for schedule_sheet_name, items in lin_schedule_info.items():
        channel_name = matched.get(schedule_sheet_name, schedule_sheet_name)
        cleaned_items = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            cleaned = dict(item)
            if "frame_name" in cleaned and "frame_row" in cleaned and "frame_column_name" in cleaned:
                cleaned["frame_name"] = _wrap_schedule_value(
                    cleaned["frame_name"], file_path, schedule_sheet_name,
                    cleaned.get("frame_row"), cleaned.get("frame_column_name") or cleaned.get("frame_column")
                )
            if "tans_time" in cleaned and "trans_time_row" in cleaned and "trans_time_column_name" in cleaned:
                cleaned["tans_time"] = _wrap_schedule_value(
                    cleaned["tans_time"], file_path, schedule_sheet_name,
                    cleaned.get("trans_time_row"), cleaned.get("trans_time_column_name") or cleaned.get("trans_time_column")
                )
            for helper in [
                "frame_row", "frame_column", "frame_column_name",
                "trans_time_row", "trans_time_column", "trans_time_column_name",
            ]:
                cleaned.pop(helper, None)
            cleaned_items.append(cleaned)
        result[channel_name] = {"schedule_table_1": cleaned_items}

    return result


@tool
def finalize_lin_metadata(grouped_lin_json: str, message_keys_json: str = "") -> str:
    """Finalize grouped LIN metadata into legacy-compatible wrapped output."""
    grouped_lin_data = json.loads(grouped_lin_json) if isinstance(grouped_lin_json, str) else grouped_lin_json
    message_keys = json.loads(message_keys_json) if message_keys_json else None
    result = finalize_lin_metadata_core(grouped_lin_data, message_keys)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def finalize_lin_schedule(
    lin_schedule_json: str,
    lin_channel_frame_name_json: str,
    file_path: str,
    min_rate: float = 0.0,
) -> str:
    """Finalize LIN schedule metadata into legacy-compatible wrapped output."""
    lin_schedule_info = json.loads(lin_schedule_json) if isinstance(lin_schedule_json, str) else lin_schedule_json
    lin_channel_frame_name_info = json.loads(lin_channel_frame_name_json) if isinstance(lin_channel_frame_name_json, str) else lin_channel_frame_name_json
    result = finalize_lin_schedule_core(lin_schedule_info, lin_channel_frame_name_info, file_path, min_rate)
    return json.dumps(result, ensure_ascii=False, default=str)
