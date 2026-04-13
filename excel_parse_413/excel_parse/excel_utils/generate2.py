# -*- coding: utf-8 -*-
import json
import logging
import traceback
import os
import copy
from datetime import datetime

# 修改导入路径
from .parse_xdm import xml_to_json
from .extracting_arxml_standardize import save_arxml_data
from .extracting_arxml_preh import save_swc_data
from .func import save_dbc_info
from .metadata_to_front import JsonTransformer, replace_trace_with_id
from .schema_mapping import make_show_data
from .parse_signal import get_channel_name_by_sheet_name, contains_chinese, \
    update_com_sys_signal_ref_trace, get_excel_column_mapping
from .parse_excel_api import parse_routing_table_api
from .ldf_parser_tool import EBLdfParser

# 导入 AUTOSAR 标准模板和全局配置
from . import global_var
from .global_cfg import global_config
from .dep_excel_basic import clean_sheet_data, handle_merged_cells
from .dep_llm import call_model
from .dep_utils import extract_json
from .prompt import prompts_data
from .global_config_class import GlobalConfig

class WorkbookParser:
    """简化的工作簿解析器"""

    def __init__(self):
        self.workbook_data = {}

    def parse_and_get_single_excel(self, file_path):
        """解析Excel文件并返回工作簿对象"""
        import openpyxl
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            return workbook
        except Exception as e:
            return None


# 全局工作簿解析器
wbparser = WorkbookParser()


def clear_routing_msg_des(new_routing_msg):
    """清除 routing_msg 的描述信息"""
    _routing_msg = {}
    for k, v in new_routing_msg.items():
        if isinstance(v, dict) and "value" in v:
            _routing_msg[k] = v["value"]
    return _routing_msg


def get_can_routing_metadata(can_routing_data):
    routing_msg = clear_routing_msg_des(can_routing_data["routing_msg"])
    routing_name = can_routing_data["routing_name"]
    file_path = can_routing_data["file_path"]
    try:
        gw_mapping, route_info = parse_routing_table_api(file_path, routing_msg, routing_name)
        return gw_mapping, route_info
    except Exception as e:
        raise e


def rebuild_nested_dict(flat_dict):
    """
    将扁平化字典重建为嵌套字典结构（带容错机制）

    改进点：
    1. 自动处理子键列表长度不一致问题
    2. 支持自定义分隔符（默认用'.'，可覆盖）
    3. 空值自动填充为""
    4. 类型注解完善

    Args:
        flat_dict: {
            "TopKey.SubKey1": ["val1", "val2"],
            "TopKey.SubKey2": ["val3"]  # 允许长度不一致
        }

    Returns:
        {
            "TopKey": [
                {"SubKey1": "val1", "SubKey2": "val3"},
                {"SubKey1": "val2", "SubKey2": ""}  # 自动补空
            ]
        }
    """

    def safe_get(lst, index, default=""):
        """安全获取列表元素，避免IndexError"""
        return lst[index] if index < len(lst) else default

    output = {}
    top_level_keys = {}
    separator = "."  # 可修改为其他分隔符如"::"

    # Step 1: 收集所有顶层键和子键
    for flat_key in flat_dict.keys():
        try:
            top, sub_key = flat_key.split(separator, 1)
            if top not in top_level_keys:
                top_level_keys[top] = []
            top_level_keys[top].append(sub_key)
        except ValueError:
            logging.error(f"Invalid key format: '{flat_key}'. Expected 'TopKey.SubKey'")

    # Step 2: 构建嵌套结构
    for top_key, sub_keys in top_level_keys.items():
        # 计算最大行数（解决长度不一致问题）
        max_rows = max(len(flat_dict[f"{top_key}{separator}{key}"]) for key in sub_keys)

        # 使用列表推导式优化性能
        output[top_key] = [
            {
                sub_key: safe_get(flat_dict[f"{top_key}{separator}{sub_key}"], i)
                for sub_key in sub_keys
            }
            for i in range(max_rows)
        ]

    return output


def compose_data(sheet_name, extract_data, data_source, header_index):
    """
    Parse input_dict to extract leaf node information and rebuild the structure
    with the given data_source.
    """

    def extract_leaf_keys(data, path=""):
        """
        Recursively extract all leaf keys and their paths from the dictionary.

        Args:
          data: The input dictionary or nested structure.
          path: The current key path being traversed.

        Returns:
          A list of tuples, each containing the full key path and its value.
        """
        leaf_keys = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    leaf_keys.extend(extract_leaf_keys(value, new_path))
                else:
                    leaf_keys.append((new_path, value))
        return leaf_keys

    # Step 1: Extract the leaf keys and their full paths
    leaf_key_values = extract_leaf_keys(extract_data)
    path_data = {}
    for path, col_name in leaf_key_values:
        # 如果 value 为空字符串，逐行填充空值
        if not col_name:  # 如果 value 是空字符串
            num_rows = len(data_source) - 1  # 减去表头行
            path_data[path] = [""] * num_rows  # 用空字符串填充每一行
            continue

        header = data_source[header_index]
        title_col_index = -1
        for index, header_name in enumerate(header):
            if header_name.strip().lower().replace('\n', '') == col_name.strip().lower().replace('\n', ''):
                title_col_index = index
                break
        if title_col_index == -1:
            logging.error(f"Column '{col_name}' not found in sheet {sheet_name}")
            num_rows = len(data_source) - 1  # 减去表头行
            path_data[path] = [""] * num_rows  # 如果列未找到，填充空列表
            continue

        current_data = []
        for row in data_source[header_index + 1:]:
            # 提取值并过滤空值
            cell_value = row[title_col_index]
            current_data.append(cell_value)

        path_data[path] = current_data
    # updated_path_data = update_com_bit_size_and_signal_length(path_data)
    resp = rebuild_nested_dict(path_data)
    delete_invalid_data(resp)
    return resp


def delete_invalid_data(resp):
    """删除无效数据"""
    for key, data_list in resp.items():
        if isinstance(data_list, list):
            index_to_remove = []
            for i, item in enumerate(data_list):
                if isinstance(item, dict):
                    item["index"] = i
                    # 对于空值率大于80%的行，则删除
                    length = len(item)
                    if length > 0:
                        null_count = 0
                        for value in item.values():
                            if not value:
                                null_count += 1
                        if null_count / length > 0.8:
                            index_to_remove.append(i)
            for index in reversed(index_to_remove):
                del data_list[index]


def rebuild_extract_data(extract_data):
    """重建提取数据"""
    new_extract_data = {}
    for key_signal, signal in extract_data.items():
        new_signal_data = {}
        for key, value in signal.items():
            new_signal_data[key] = value["title_name"]
        new_extract_data[key_signal] = new_signal_data
    return new_extract_data


def update_srs_value(value, value_type, trace=None):
    """更新SRS值"""
    return {
        "value": value,
        "trace": trace if trace else [],
        "type": value_type
    }


def process_can_signal_fields(signal, extract_data, file_path, sheet_name, header_index, column_mapping, real_index):
    """处理CAN信号字段，添加trace信息"""
    for key, val in signal.items():
        title_name = extract_data["ComSignal"][key]
        if title_name != "":
            row = real_index + header_index[sheet_name] + 2
            col = column_mapping[sheet_name].get(title_name)
            signal[key] = {
                "value": None if val == "" else val,
                "trace": [{"file": file_path, "row": row, "col": col, "sheet": sheet_name}],
                "type": "user"
            }
        else:
            signal[key] = update_srs_value(val, "user")
    return signal


def build_can_message(signal, msg_name_obj, msg_name, direction, channel_name):
    """构建CAN消息对象"""
    message = {
        "msg_name": msg_name_obj,
        "signals": [signal] if signal.get("ShortName") else [],
        "group_ref": update_srs_value(channel_name, "design"),
        "delay_time": signal.pop("MsgDelayTime", None),
        "offset": signal.pop("Offset", None),
        "reption": signal.pop("MsgNrOfReption", None),
        "send_type": signal.pop("MsgSendType", None),
        "msg_id": signal.pop("MsgId", None),
        "msg_length": signal.pop("MsgLength", None),
        "cycle_time": signal.get("MsgCycleTime", None),
        "direction": direction,
        "msg_type": signal.pop("MsgType", None),
    }

    # 添加默认属性
    signal['ComTransferProperty'] = update_srs_value("TRIGGERED", "default")
    signal['ComSignalEndianness'] = update_srs_value("BIG_ENDIAN", "default")
    signal['ComUpdateBitPosition'] = update_srs_value(None, "default")
    signal['ComSystemTemplateSystemSignalRef'] = update_com_sys_signal_ref_trace(
        signal, msg_name, signal.get("ShortName")
    )

    return message, signal


def process_can_sheet(workbook, sheet_name, extract_data, file_path, header_index, column_mapping, channel_name,
                      direction):
    """处理单个CAN sheet，返回消息映射表"""
    message_info_map = {}
    sheet = workbook[sheet_name]
    cleaned_data = handle_merged_cells(sheet)
    sheet_data = clean_sheet_data(cleaned_data)

    extract_data = rebuild_extract_data(extract_data)
    result = compose_data(sheet_name, extract_data, sheet_data, header_index[sheet_name])

    for index, signal in enumerate(result["ComSignal"]):
        real_index = signal.pop("index", index)
        signal = process_can_signal_fields(signal, extract_data, file_path, sheet_name, header_index, column_mapping,
                                           real_index)

        msg_name_obj = signal.get("MsgName", {})
        msg_name = signal.pop("MsgName", {}).get("value")
        if not msg_name or contains_chinese(msg_name):
            continue

        # 确定方向
        if direction == '':
            if signal['EcuName']["value"] in ['CCURT2', 'CCURT1', 'CCU']:
                direction = 'TX'
            else:
                direction = 'RX'

        # 构建消息
        message, signal = build_can_message(signal, msg_name_obj, msg_name, direction, channel_name)

        # 分组消息
        if msg_name not in message_info_map:
            message_info_map[msg_name] = message
        else:
            if signal.get("ShortName"):
                message_info_map[msg_name]["signals"].append(signal)

    return message_info_map, direction


def merge_can_messages(message_info, channel_name, direction, message_info_map):
    """将处理好的消息合并到全局消息信息中"""
    if not message_info_map:
        return message_info

    if direction == '':
        for msg_data in message_info_map.values():
            msg_dir = msg_data.pop('direction')
            message_info[channel_name][msg_dir].append(msg_data)
    else:
        for msg_data in message_info_map.values():
            msg_data.pop('direction', None)
        message_info[channel_name][direction].extend(list(message_info_map.values()))

    # 处理RT1和RT2的回环路由
    if 'RT1_RollBack_CANFD' in message_info and 'RT2_RollBack_CANFD' in message_info:
        message_info['RT1_RollBack_CANFD']['RX'] = message_info['RT2_RollBack_CANFD']['TX']
        message_info['RT2_RollBack_CANFD']['RX'] = message_info['RT1_RollBack_CANFD']['TX']

    return message_info


def get_can_signal_metadata(can_signal_mapping_infos):
    message_info = {}
    for can_signal_mapping_info in can_signal_mapping_infos:
        mapping_info = can_signal_mapping_info["mapping_data"]["mapping_info"]
        column_mapping = can_signal_mapping_info["mapping_data"]["column_mapping"]
        header_index = can_signal_mapping_info["mapping_data"]["header_index"]
        file_path = can_signal_mapping_info["file_path"]
        workbook = wbparser.parse_and_get_single_excel(file_path)

        for sheet_name, extract_data in mapping_info.items():
            try:
                channel_name, direction = get_channel_name_by_sheet_name(sheet_name)
                if not channel_name:
                    continue

                # 记录channel的trace信息
                global_config.channel_trace_info[channel_name] = update_srs_value(
                    channel_name, "user", [{"file": file_path, "row": 0, "col": 0, "sheet": sheet_name}]
                )
                message_info.setdefault(channel_name, {"RX": [], 'TX': []})

                # 处理sheet数据
                message_info_map, direction = process_can_sheet(
                    workbook, sheet_name, extract_data, file_path, header_index, column_mapping, channel_name, direction
                )

                # 合并处理结果
                message_info = merge_can_messages(message_info, channel_name, direction, message_info_map)

            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(f"{file_path} {sheet_name} {e}")

    return message_info


def process_lin_signal_fields(signal, extract_data, file_path, sheet_name, header_index, column_mapping, real_index):
    """处理LIN信号字段，添加trace信息"""
    for key, val in signal.items():
        title_name = extract_data["ComSignal"][key]
        if title_name != "":
            row = header_index[sheet_name] + 2 + real_index
            col = column_mapping[sheet_name].get(title_name)
            signal[key] = {
                "value": None if val == "" else val,
                "trace": [{"file": file_path, "row": row, "col": col, "sheet": sheet_name}],
                "type": "user"
            }
        else:
            signal[key] = update_srs_value(val, "user")
    return signal


def build_lin_message(signal, msg_name, direction, message_keys):
    """构建LIN消息对象"""
    signal_name = signal.get("ShortName", {}).get("value")
    this_message_info = {ele: signal.pop(ele, None) for ele in message_keys}
    this_message_info['direction'] = direction
    this_message_info["signals"] = [signal] if signal_name else []
    return this_message_info, signal


def process_lin_sheet(workbook, sheet_name, extract_data, file_path, header_index, column_mapping, message_keys):
    """处理单个LIN sheet，返回消息映射表和帧名称集合"""
    message_info_map = {}
    frame_name_set = set()

    sheet = workbook[sheet_name]
    cleaned_data = handle_merged_cells(sheet)
    sheet_data = clean_sheet_data(cleaned_data)

    extract_data = rebuild_extract_data(extract_data)
    result = compose_data(sheet_name, extract_data, sheet_data, header_index[sheet_name])["ComSignal"]

    for index, signal in enumerate(result):
        real_index = signal.pop("index", index)
        signal = process_lin_signal_fields(signal, extract_data, file_path, sheet_name, header_index, column_mapping,
                                           real_index)

        msg_name = signal.get("FrameName", {}).get("value")
        if not msg_name or contains_chinese(msg_name):
            continue

        frame_name_set.add(msg_name)

        # 确定方向
        if signal['EcuName']["value"] in ['CCURT2', 'CCURT1', 'CCU']:
            direction = 'TX'
        else:
            direction = 'RX'

        # 分组消息
        if msg_name not in message_info_map:
            message, signal = build_lin_message(signal, msg_name, direction, message_keys)
            message_info_map[msg_name] = message
        elif signal.get("ShortName", {}).get("value"):
            for key in message_keys:
                signal.pop(key, None)
            message_info_map[msg_name]["signals"].append(signal)

    return message_info_map, frame_name_set


def merge_lin_messages(message_info, sheet_name, message_info_map):
    """将处理好的LIN消息合并到全局消息信息中"""
    if not message_info_map:
        return message_info

    for msg_data in message_info_map.values():
        msg_dir = msg_data.pop('direction')
        message_info[sheet_name][msg_dir].append(msg_data)

    return message_info


def get_lin_signal_metadata(lin_signal_mapping_infos):
    message_info = {}
    lin_schedule_info = {}
    lin_channel_frame_name_info = {}
    lin_schedule_info_file_path = ''
    message_keys = ["EcuName", "FrameName", "LinId", "ProtectedId", "MsgSendType",
                    "FrameLength", "FrameSendType", "FrameCycleTime"]

    for lin_signal_mapping_info in lin_signal_mapping_infos:
        if 'mapping_data' not in lin_signal_mapping_info:
            lin_schedule_info = lin_signal_mapping_info["schedule_data"]
            lin_schedule_info_file_path = lin_signal_mapping_info["file_path"]
            continue

        mapping_info = lin_signal_mapping_info["mapping_data"]["mapping_info"]
        column_mapping = lin_signal_mapping_info["mapping_data"]["column_mapping"]
        header_index = lin_signal_mapping_info["mapping_data"]["header_index"]
        file_path = lin_signal_mapping_info["file_path"]
        workbook = wbparser.parse_and_get_single_excel(file_path)

        for sheet_name, extract_data in mapping_info.items():
            try:
                message_info[sheet_name] = {"RX": [], 'TX': []}
                lin_channel_frame_name_info[sheet_name] = set()

                # 处理sheet数据
                message_info_map, frame_name_set = process_lin_sheet(
                    workbook, sheet_name, extract_data, file_path, header_index, column_mapping, message_keys
                )

                lin_channel_frame_name_info[sheet_name] = frame_name_set

                # 合并处理结果
                message_info = merge_lin_messages(message_info, sheet_name, message_info_map)

            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(f"{file_path} {sheet_name} {e}")

    if not lin_schedule_info:
        logging.warning("lin_schedule_info is empty, skipping schedule processing")
        return message_info, {}

    new_lin_schedule_info = lin_schedule_info_mapping_lin_message_info(lin_schedule_info, lin_channel_frame_name_info)
    make_schedule_trace_info(lin_schedule_info_file_path, new_lin_schedule_info)
    return message_info, new_lin_schedule_info


def make_schedule_trace_info(lin_schedule_info_file_path, new_lin_schedule_info):
    for channel_name, channel_infos in new_lin_schedule_info.items():
        for table_name, schedule_data in channel_infos.items():
            schedule_infos = schedule_data['data']
            sheet_name = schedule_data['sheet_name']
            for schedule_info in schedule_infos:
                if 'frame_name' in schedule_info and "frame_row" in schedule_info and "frame_column_name" in schedule_info:
                    schedule_info["frame_name"] = {
                        "value": schedule_info["frame_name"],
                        "trace": [
                            {
                                "file": lin_schedule_info_file_path,
                                "row": schedule_info["frame_row"],
                                "col": schedule_info["frame_column_name"],
                                "sheet": sheet_name
                            }],
                        "type": "user"
                    }
                    schedule_info.pop("frame_row")
                    schedule_info.pop("frame_column")
                    schedule_info.pop("frame_column_name")
                if 'tans_time' in schedule_info and "trans_time_row" in schedule_info and "trans_time_column_name" in schedule_info:
                    schedule_info["tans_time"] = {
                        "value": schedule_info["tans_time"],
                        "trace": [
                            {
                                "file": lin_schedule_info_file_path,
                                "row": schedule_info["trans_time_row"],
                                "col": schedule_info["trans_time_column_name"],
                                "sheet": sheet_name
                            }],
                        "type": "user"
                    }
                    schedule_info.pop("trans_time_row")
                    schedule_info.pop("trans_time_column")
                    schedule_info.pop("trans_time_column_name")
            channel_infos[table_name] = schedule_infos


def lin_schedule_info_mapping_lin_message_info(lin_schedule_info, lin_channel_frame_name_info):
    new_lin_schedule_info = {}
    for schedule_sheet_name, schedule_datas in lin_schedule_info.items():
        frame_name_list = set([schedule_data["frame_name"] for schedule_data in schedule_datas])
        # 计算frame_name_list与哪个channel_frame_name_info的frame_name_list的交集率最高
        highest_inter_rate = -1
        channel_name = ""
        for sheet_name, frame_names in lin_channel_frame_name_info.items():
            if not frame_names:
                continue
            inter_rate = len(frame_name_list & frame_names) / len(frame_names)
            if inter_rate > highest_inter_rate:
                highest_inter_rate = inter_rate
                channel_name = sheet_name
        schedule_data = {"data": schedule_datas, 'sheet_name': schedule_sheet_name}

        # 重新构造schedule_info
        new_lin_schedule_info[channel_name] = {"schedule_table_1": schedule_data}
    return new_lin_schedule_info


def get_multiple_rows_table_headers(table_data, header_indices):
    """将表格数据按照指定的表头行索引转换为字典列表格式"""
    if not table_data or not header_indices:
        return []

    # 获取表头行数据
    header_rows = []
    for idx in header_indices:
        if 0 <= idx < len(table_data):
            header_rows.append(table_data[idx])
        else:
            raise IndexError(f"Header index {idx + 1} is out of table range")

    # 构建表头
    headers = []
    for col_idx in range(len(header_rows[0]) if header_rows else 0):
        if len(header_rows) == 1:
            # 只有一行表头
            header = str(header_rows[0][col_idx])
        else:
            # 多行表头，组合所有行的对应列值
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


def get_nvm_meta_data(data):
    nvm_datas = data["nvm_datas"]
    try:
        for nvm_data in nvm_datas:
            file_path = nvm_data.get("file_path")
            parse_data = wbparser.parse_and_get_single_excel(file_path)
            main_data = nvm_data.get("main_data")
            for sheet_name, sheet_main_data in main_data.items():
                common_data = sheet_main_data.get("common")
                for key, value in common_data.items():
                    if 'column' in value and 'row' in value:
                        i = int(value.get("column"))
                        column_name = ""
                        while i > 0:
                            i -= 1
                            column_name = chr(i % 26 + 65) + column_name
                            i //= 26
                        common_data[key] = {
                            "value": value.get("value"),
                            "trace": [
                                {
                                    "file": file_path,
                                    "row": value.get("row"),
                                    "col": column_name,
                                    "sheet": sheet_name
                                }],
                            "type": "user"

                        }
                headers = sheet_main_data.get("block", {}).get("headers")
                if not headers:
                    continue
                sheet = parse_data[sheet_name]
                cleaned_data = handle_merged_cells(sheet)
                sheet_data = clean_sheet_data(cleaned_data)
                headers_data = get_multiple_rows_table_headers(sheet_data, headers)
                column_mapping = get_excel_column_mapping(headers_data)

                extract_data = {"block": sheet_main_data.get("block", {}).get('fields')}
                result = compose_data(sheet_name, extract_data, sheet_data, headers[-1])["block"]
                for index, signal in enumerate(result):
                    real_index = signal.pop("index", index)
                    for key, val in signal.items():
                        # 获取列
                        title_name = extract_data["block"][key]
                        if title_name != "":
                            row = real_index + headers[-1] + 2
                            col = column_mapping.get(title_name)

                            signal[key] = {
                                "value": None if val == "" else val,
                                "trace": [
                                    {
                                        "file": file_path,
                                        "row": row,
                                        "col": col,
                                        "sheet": sheet_name
                                    }],
                                "type": "user"

                            }

                        else:
                            signal[key] = update_srs_value(val, "user")
                sheet_main_data["block"] = result
        return nvm_datas
    except Exception:
        logging.error(traceback.format_exc())
        return nvm_datas


def get_can_routing_data(data):
    can_routing_datas = data["can_routing_data"]
    gw_mappings = []
    route_infos = []
    for can_routing_data in can_routing_datas:
        if can_routing_data['routing_name']:
            if can_routing_data.get('routing_msg') and len(can_routing_data['routing_msg']) <= 2:
                logging.info(f"can_routing_data routing_msg does not meet requirements")
                continue
            gw_mapping, route_info = get_can_routing_metadata(can_routing_data)
            if gw_mapping:
                gw_mappings.append(gw_mapping)
            if route_info:
                route_infos.append(route_info)
    return gw_mappings, route_infos


def extra_excel_info(extract_params_info_path):
    """提取Excel信息"""
    with open(extract_params_info_path, "r", encoding="utf-8") as f:
        data = json.loads(f.read())

    # 获取can的routing_data的数据
    gw_mappings, route_infos = get_can_routing_data(data)

    # 获取can信号的数据
    can_signal_mapping_infos = data["can_signal_mapping_infos"]
    can_signal_data = get_can_signal_metadata(can_signal_mapping_infos)

    # 获取lin信号的数据
    lin_signal_scheduler_mapping_infos = data["lin_signal_scheduler_mapping_infos"]
    excel_lin_signal_data, excel_lin_schedule_info = get_lin_signal_metadata(lin_signal_scheduler_mapping_infos)

    # 获取nvm数据
    nvm_data = get_nvm_meta_data(data)

    return gw_mappings, route_infos, excel_lin_signal_data, excel_lin_schedule_info, nvm_data, can_signal_data


def get_json_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    if not json_data:
        return None
    try:
        system_prompt = prompts_data.get("json_parse_prompt")
        query = f"""请帮我提取以下补充需求的数据：{json_data}"""
        res = call_model(query.replace("{", "{{").replace("}", "}}"),
                                      system_prompt.replace("{", "{{").replace("}", "}}"))

        res_json = res.replace("{{", "{").replace("}}", "}")
        valid_data = extract_json(res_json).get("MessageList", "")
        return valid_data
    except Exception as e:
        logging.error(f"Failed to extract JSON data: {e}")
        return None


def generate_requirement_metadata(global_config:GlobalConfig):
    """生成需求元数据（AUTOSAR标准模板结构）"""
    # 提取Excel信息
    extract_params_info_path = global_config.previous_data["extract_params_info_path"]
    output_dir = os.path.join(global_config.current_work_space["project_directory"],global_config.current_work_space["project_name"])
    gw_mappings, route_infos, excel_lin_signal_data, excel_lin_schedule_info, nvm_data, can_signal_data = extra_excel_info(
        extract_params_info_path)
    
    # 获取补充数据（JSON和XDM）
    json_data = None
    xdm_data = None
    
    # 尝试获取JSON数据
    try:
        json_path = os.path.join(os.path.dirname(extract_params_info_path), "补充需求.json")
        if os.path.exists(json_path):
            json_data = get_json_data(json_path)
    except Exception as e:
        logging.warning(f"Failed to get JSON data: {e}")
    
    # 尝试获取XDM数据
    try:
        xdm_path = os.path.join(os.path.dirname(extract_params_info_path), "xdm.xml")
        if os.path.exists(xdm_path):
            xdm_json = xml_to_json(xdm_path)
            xdm_data = [xdm_json]
    except Exception as e:
        logging.warning(f"Failed to get XDM data: {e}")

    # 使用 AUTOSAR 标准模板构建需求元数据
    requirement_metadata = copy.deepcopy(global_var.requirement_metadata_template)
    
    # 填充通信栈数据
    com_module = requirement_metadata["RequirementsData"]["CommunicationStack"]
    com_module["Can"] = can_signal_data
    com_module["Lin"] = {
        "LinSignal": excel_lin_signal_data,
        "LinSchedule": excel_lin_schedule_info,
    }
    com_module["GateWayConfiguration"] = {
        "SignalGateWay": gw_mappings,
        "PduGateWay": route_infos,
    }
    
    # 填充存储数据
    requirement_metadata["RequirementsData"]["Storage"]["NvRamManager"] = nvm_data
    
    # 填充CDD数据
    if json_data:
        requirement_metadata["RequirementsData"]['CDD']['AVTP'] = json_data
    elif xdm_data:
        requirement_metadata["RequirementsData"]['CDD']['AVTP'] = xdm_data

    # 添加 AUTOSAR 包装
    requirement_metadata = {'AUTOSAR': requirement_metadata}
    
    # 如果启用了 schema mapping，则进行数据转换
    if global_var.schema_mapping_flag:
        make_show_data(requirement_metadata)

    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 保存需求元数据
    requirement_metadata_file = os.path.join(output_dir, "requirement_metadata_file.json")
    global_config.previous_data["requirement_metadata_file_path"] = requirement_metadata_file
    with open(requirement_metadata_file, "w", encoding="utf-8") as f:
        json.dump(requirement_metadata, f, ensure_ascii=False, indent=2)

    return requirement_metadata_file


if __name__ == "__main__":
    # 示例用法
    # extract_params_info_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\extract_params_info_1.json"
    # extract_params_info_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\new_data\extract_params_info.json"
    extract_params_info_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\extract_params_info_1.json"
    # 输出目录：默认放到 <repo_root>/data/output，避免写死绝对路径
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    output_dir = os.path.join(repo_root, "data", "output")

    requirement_metadata_file = generate_requirement_metadata(extract_params_info_path, output_dir)
    print(f"需求元数据已生成：{requirement_metadata_file}")


