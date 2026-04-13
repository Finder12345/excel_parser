# -*- coding: utf-8 -*-
"""
CAN 最终后处理工具。

将 build_module_metadata 的通用分组结果收敛为与原始实现接近的 CAN wrapped 输出语义。

纯函数，零LLM。
"""
import json
from typing import Any, Dict, List, Optional

from langchain.tools import tool

from .add_trace import add_trace_core

_TX_ECUS = {"CCURT2", "CCURT1", "CCU"}


def _trace_value(value: Any, value_type: str = "user") -> Dict[str, Any]:
    return add_trace_core(value, value_type)


def _unwrap(v: Any) -> Any:
    if isinstance(v, dict) and {"value", "type", "trace"}.issubset(v.keys()):
        return v.get("value")
    return v


def _is_empty(v: Any) -> bool:
    return _unwrap(v) in (None, "")


def _signal_ref(msg_name: str, short_name_obj: Any) -> Dict[str, Any]:
    short_name = _unwrap(short_name_obj)
    suffix = short_name if short_name is not None else "None"
    return _trace_value(f"{msg_name}/{suffix}", "design")


def _infer_direction(sheet_direction: str, signal: Dict[str, Any]) -> str:
    if sheet_direction:
        return sheet_direction
    ecu_name = _unwrap(signal.get("EcuName"))
    return "TX" if str(ecu_name) in _TX_ECUS else "RX"


def _build_signal_defaults(signal: Dict[str, Any], msg_name: str) -> Dict[str, Any]:
    out = dict(signal)
    out["ComTransferProperty"] = _trace_value("TRIGGERED", "default")
    out["ComSignalEndianness"] = _trace_value("BIG_ENDIAN", "default")
    out["ComUpdateBitPosition"] = _trace_value(None, "default")
    out["ComSystemTemplateSystemSignalRef"] = _signal_ref(msg_name, out.get("ShortName"))
    return out


def _build_placeholder_signal(message: Dict[str, Any], msg_name: str) -> Dict[str, Any]:
    return {
        "ShortName": _trace_value(None, "user"),
        "BitSize": _trace_value(None, "user"),
        "BitPosition": _trace_value(None, "user"),
        "SignalType": _trace_value(None, "user"),
        "SignalEndianness": _trace_value("", "user"),
        "SignalInitValue": _trace_value(None, "user"),
        "SignalMinValue": _trace_value(None, "user"),
        "SignalMaxValue": _trace_value(None, "user"),
        "SignalDataInvalidValue": _trace_value(None, "user"),
        "TimeoutValue": _trace_value(None, "user"),
        "TransferProperty": _trace_value("", "user"),
        "UpdateBitPosition": _trace_value("", "user"),
        "SystemTemplateSystemSignalRef": _trace_value("", "user"),
        "MsgCycleTime": message.get("cycle_time"),
        "EcuName": message.get("EcuName", _trace_value(None, "user")),
        "Remark": _trace_value(None, "user"),
        "ComTransferProperty": _trace_value("TRIGGERED", "default"),
        "ComSignalEndianness": _trace_value("BIG_ENDIAN", "default"),
        "ComUpdateBitPosition": _trace_value(None, "default"),
        "ComSystemTemplateSystemSignalRef": _signal_ref(msg_name, None),
    }


def _build_message(signal: Dict[str, Any], msg_name: str, channel_name: str, direction: str) -> Dict[str, Any]:
    signal_copy = dict(signal)
    msg_name_obj = signal_copy.pop("MsgName", _trace_value(msg_name, "user"))
    out_signal = _build_signal_defaults(signal_copy, msg_name)
    message = {
        "msg_name": msg_name_obj,
        "signals": [out_signal] if not _is_empty(out_signal.get("ShortName")) else [],
        "group_ref": _trace_value(channel_name, "design"),
        "delay_time": signal_copy.pop("MsgDelayTime", None),
        "offset": signal_copy.pop("Offset", None),
        "reption": signal_copy.pop("MsgNrOfReption", None),
        "send_type": signal_copy.pop("MsgSendType", None),
        "msg_id": signal_copy.pop("MsgId", None),
        "msg_length": signal_copy.pop("MsgLength", None),
        "cycle_time": signal_copy.get("MsgCycleTime", None),
        "direction": direction,
        "msg_type": signal_copy.pop("MsgType", None),
        "EcuName": signal_copy.get("EcuName", _trace_value(None, "user")),
    }
    return message


def _extract_signal_rows(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    signals = message.get("signals", [])
    if not isinstance(signals, list) or not signals:
        return [dict(message)]
    rows = []
    message_fields = {k: v for k, v in message.items() if k != "signals"}
    for signal in signals:
        if isinstance(signal, dict):
            row = dict(message_fields)
            row.update(signal)
            rows.append(row)
    return rows or [dict(message)]


def finalize_can_metadata_core(
    grouped_can_data: Dict[str, Any],
    channel_name: str,
    sheet_direction: str = "",
    apply_rollback_aliases: bool = False,
    rollback_source: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    result = {"TX": [], "RX": []}
    messages = []
    if isinstance(grouped_can_data, dict):
        if isinstance(grouped_can_data.get("TX"), list) or isinstance(grouped_can_data.get("RX"), list):
            messages.extend(grouped_can_data.get("TX", []))
            messages.extend(grouped_can_data.get("RX", []))
        else:
            messages.extend(v for v in grouped_can_data.values() if isinstance(v, dict))
    elif isinstance(grouped_can_data, list):
        messages = grouped_can_data

    message_info_map: Dict[str, Dict[str, Any]] = {}
    for message in messages:
        if not isinstance(message, dict):
            continue
        for base_signal in _extract_signal_rows(message):
            msg_name = _unwrap(base_signal.get("MsgName") or base_signal.get("msg_name"))
            if not msg_name or any('\u4e00' <= ch <= '\u9fff' for ch in str(msg_name)):
                continue

            direction = _infer_direction(sheet_direction, base_signal)
            if msg_name not in message_info_map:
                built = _build_message(base_signal, msg_name, channel_name, direction)
                message_info_map[msg_name] = built
            else:
                short_name = _unwrap(base_signal.get("ShortName"))
                if short_name not in (None, ""):
                    message_info_map[msg_name]["signals"].append(_build_signal_defaults(base_signal, msg_name))

    for msg in message_info_map.values():
        direction = msg.pop("direction", sheet_direction or "RX")
        if not msg.get("signals"):
            msg_name = _unwrap(msg.get("msg_name"))
            msg["signals"] = [_build_placeholder_signal(msg, msg_name)]
        result.setdefault(direction, []).append(msg)

    if apply_rollback_aliases and rollback_source:
        if "RT1_RollBack_CANFD" in rollback_source and "RT2_RollBack_CANFD" in rollback_source:
            rollback_source["RT1_RollBack_CANFD"]["RX"] = rollback_source["RT2_RollBack_CANFD"].get("TX", [])
            rollback_source["RT2_RollBack_CANFD"]["RX"] = rollback_source["RT1_RollBack_CANFD"].get("TX", [])

    return result


@tool
def finalize_can_metadata(
    grouped_can_json: str,
    channel_name: str,
    sheet_direction: str = "",
) -> str:
    """Finalize grouped CAN metadata into legacy-compatible wrapped output."""
    grouped_can_data = json.loads(grouped_can_json) if isinstance(grouped_can_json, str) else grouped_can_json
    result = finalize_can_metadata_core(grouped_can_data, channel_name, sheet_direction)
    return json.dumps(result, ensure_ascii=False, default=str)
