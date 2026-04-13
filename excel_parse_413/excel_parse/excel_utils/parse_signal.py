# -*- coding: utf-8 -*-
"""
@File    : parse_signal.py
@Date    : 2025--08-20 14:33
@Desc    : Description of the file
@Author  : lei
"""
import copy
import json
import logging
import os

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Union
import pandas as pd
from tqdm import tqdm

from .logic_AutoPy import extract_json

from .dep_llm import  call_model
from .prompt import prompts_data
from . import global_var
from .global_cfg import global_config, init_global_config

import datetime

init_global_config()


def convert_datetime(obj):
    """将 datetime 对象递归转换为可 JSON 序列化的字符串。

    功能逻辑：
    - 支持 dict/list 的递归遍历。
    - 遇到 datetime.datetime 时转为 ISO8601 字符串。

    用途：
    - 给 LLM/prompt 组装输入时做预处理，避免 datetime 直接 json.dumps 失败。
    """
    if isinstance(obj, dict):
        return {key: convert_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(item) for item in obj]
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj


def clean_sheet_data(sheet_data):
    """
    清理Sheet数据，去除空行和空列。

    :param sheet_data: List[List]，表示Excel表格的二维数据
    :return: 清理后的数据
    """
    # 将数据转换为DataFrame（方便处理）
    df = pd.DataFrame(sheet_data)

    # 去除空行（所有列均为空的行）
    df.dropna(how='all', inplace=True)

    # 去除空列（所有行均为空的列）
    df.dropna(how='all', axis=1, inplace=True)

    # 将清理后的数据转换回List[List]格式
    cleaned_data = df.values.tolist()
    return cleaned_data


def get_header_input(sheet_data: list, max_row=10, max_column=10):
    """截取 sheet 的左上角局部区域作为"表头识别/字段映射"的输入。

    功能逻辑：
    - 深拷贝原始二维表格数据，避免污染源数据。
    - 限制最大行/列，降低 LLM 输入 token，提升识别稳定性。

    参数:
    - sheet_data: 解析后的二维表格数据。
    - max_row/max_column: 取样窗口大小。

    返回:
    - header_input: 截断后的二维数据。
    """
    header_input = copy.deepcopy(sheet_data)
    if len(header_input) > max_row:
        header_input = header_input[:max_row]
    for i in range(len(header_input)):
        if len(header_input[i]) > max_column:
            header_input[i] = header_input[i][:max_column]
    return header_input


def contains_chinese(text):
    """判断字符串是否包含中文字符。

    功能逻辑：
    - 遍历字符，检查是否落在常用中文 Unicode 范围（\u4e00-\u9fff）。

    用途：
    - 在信号/报文命名处理时过滤掉明显不规范或说明性中文文本。
    """
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def parse_all_signal(file_path: str):
    """（当前版本未启用）从 Excel 中抽取 CAN 信号/报文结构。

    设计目标（从已注释代码可推断）：
    - 遍历每个 sheet，判断是否为 Tx_/Rx_ 信号表。
    - 通过 LLM 识别表头行、构建字段→表头映射（mapping）。
    - 依据映射从表格逐行抽取 ComSignal/Msg 等字段，并补充 trace（文件/行/列/sheet）。
    - 最终组装为按 channel 分类的 message_info 结构。

    当前实现：
    - 主体逻辑被注释，直接返回空字典 {}。

    返回:
    - {}（占位）
    """
    # data = parse_excel(file_path)
    # ws_client.send("General document analysis", status="pending")
    # # 通知状态为"智能需求解析中"
    # ws_client.send("Intelligent demand analysis excel", status="pending")
    #
    # # 获取pdu
    #
    # # 初始化最终结果存储
    # message_info = {}
    # channel_signal_name_list = []
    # signal_count_map = {}
    # input_dict = {}
    # sheet_map = {}
    # # 遍历每个Sheet、
    # sheet_list = []
    # header_input = []
    # for sheet_name, sheet_data in data.items():
    #     channel_name, _ = get_channel_name_by_sheet_name(sheet_name)
    #     if not channel_name:
    #         continue
    #     # 清理当前Sheet的空行和空列
    #     sheet_data = clean_sheet_data(sheet_data)
    #     header_input.append({sheet_name: get_header_input(sheet_data)})
    # header_infos = table_header_map_function(header_input)
    # for sheet_name, sheet_data in data.items():
    #     # 清理当前Sheet的空行和空列
    #     sheet_data = clean_sheet_data(sheet_data)
    #     channel_name, direction = get_channel_name_by_sheet_name(sheet_name)
    #     if not channel_name:
    #         continue
    #     global_config.channel_trace_info[channel_name] = update_srs_value(channel_name, "user", [
    #         {
    #             "file": file_path,
    #             "row": 0,
    #             "col": 0,
    #             "sheet": sheet_name
    #         }], )
    #
    #     message_info.setdefault(channel_name, {"RX": [], 'TX': [], '': []})
    #     # 提取当前Sheet的表头
    #     header_info = header_infos.get(sheet_name)
    #     if header_info and header_info['direction'] == 'horizontal':
    #         index = header_info['index'][-1]  # 取最后一行
    #         header = sheet_data[index - 1]  # 表头
    #         # header list
    #         # 构建参数与列名的映射关系
    #         column_mapping = get_excel_column_mapping(header)
    #         # input_dict = {sheet_name: ",".join(header)}  # 当前Sheet的表头JSON
    #         input_dict[sheet_name] = ",".join(header)  # 当前Sheet的表头
    #         sheet_map[sheet_name] = {
    #             "sheet_data": sheet_data,
    #             "column_mapping": column_mapping,
    #             "signal_name_list": [],
    #             "message_info_map": {},
    #             "channel_name": channel_name,
    #             "header_index": index - 1,
    #             "direction": direction
    #         }
    #         sheet_list.append(sheet_name)
    #
    # input_list = []
    # for k, v in input_dict.items():
    #     input_list.append({k: v})
    # if input_list:
    #
    #     try:
    #         # 如果成功解析，退出重试循环
    #         # Step 1: 解析AI返回的映射关系
    #         mapping = map_function(input_list)
    #
    #         # Step 2: 根据映射关系和当前Sheet数据提取具体值
    #         for sheet_name, data in sheet_map.items():
    #             result = compose_data({"ComSignal": mapping[sheet_name]["ComSignal"]},
    #                                   {sheet_name: data["sheet_data"], "header_index": data["header_index"]})
    #
    #             for index, signal in enumerate(result["ComSignal"]):
    #                 signal_name = signal.get("ShortName")
    #                 # if not signal_name:
    #                 #     continue
    #                 for key, val in signal.items():
    #                     # 获取列
    #                     row_info = mapping[sheet_name]["ComSignal"][key]
    #
    #                     if row_info != "":
    #                         row = index + 1 + 1
    #                         col = data["column_mapping"].get(row_info.rsplit("|", 1)[1])
    #
    #                         signal[key] = {
    #                             "value": None if val == "" else val,
    #                             "trace": [
    #                                 {
    #                                     "file": file_path,
    #                                     "row": row,
    #                                     "col": col,
    #                                     "sheet": sheet_name
    #                                 }],
    #                             "type": "user"
    #
    #                         }
    #
    #                     else:
    #                         signal[key] = update_srs_value(val, "user")
    #                 msg_name = signal.get("MsgName", {}).get("value")
    #                 if not msg_name or contains_chinese(msg_name):
    #                     continue
    #
    #                 new_signal_name = f"{sheet_map[sheet_name]['channel_name']}/{signal.get('MsgName', {}).get('value')}/{signal_name}"
    #                 signal["ShortName"]["value"] = new_signal_name
    #                 if data['direction'] == '':
    #                     if signal['EcuName']["value"] in ['CCURT2', 'CCURT1', 'CCU']:
    #                         direction = 'TX'
    #                     else:
    #                         direction = 'RX'
    #                 else:
    #                     direction = data['direction']
    #
    #                 message_name = f"{sheet_map[sheet_name]['channel_name']}_{signal.get('MsgName', {}).get('value')}"
    #                 msg_name_obj = signal.get("MsgName", {})
    #                 msg_name_obj['value'] = message_name
    #                 message = {
    #                     "msg_name": msg_name_obj,
    #                     "signals": [signal] if signal_name else [],
    #                     "group_ref": update_srs_value(data['channel_name'], "design"),
    #                     "delay_time": signal.get("MsgDelayTime"),
    #                     "offset": signal.get("Offset"),
    #                     "reption": signal.get("MsgNrOfReption"),
    #                     "send_type": signal.get("MsgSendType"),
    #                     "msg_id": signal.get("MsgId"),
    #                     "msg_length": signal.get("MsgLength"),
    #                     "cycle_time": signal.get("MsgCycleTime"),
    #                     "direction": direction,
    #                     "msg_type": signal.get("MsgType"),
    #                 }
    #                 # 　更新信号的值
    #                 del_signal_other_info(signal)
    #                 signal['TransferProperty'] = update_srs_value("TRIGGERED", "default")
    #                 signal['SignalEndianness'] = update_srs_value("BIG_ENDIAN", "default")
    #                 signal['UpdateBitPosition'] = update_srs_value(None, "default")
    #                 # signal['ComSystemTemplateSystemSignalRef'] = update_srs_value(f"{msg_name}/{signal_name}", "user")
    #                 signal['SystemTemplateSystemSignalRef'] = update_com_sys_signal_ref_trace(signal, msg_name,
    #                                                                                           signal_name)
    #
    #                 if message_name not in data["message_info_map"]:
    #                     data["message_info_map"][message_name] = message
    #                 else:
    #                     if signal_name:
    #                         data["message_info_map"][message_name]["signals"].append(signal)
    #             if data["message_info_map"]:
    #                 if data['direction'] == '':
    #                     for msg_data in data["message_info_map"].values():
    #                         if msg_data['direction'] == 'TX':
    #                             message_info[data['channel_name']]['TX'].append(msg_data)
    #                         elif msg_data['direction'] == 'RX':
    #                             message_info[data['channel_name']]['RX'].append(msg_data)
    #                 else:
    #                     message_info[data['channel_name']][data['direction']].extend(
    #                         list(data["message_info_map"].values()))
    #         if 'RT1_RollBack_CANFD' in message_info and 'RT2_RollBack_CANFD' in message_info:
    #             message_info['RT1_RollBack_CANFD']['RX'] = message_info['RT2_RollBack_CANFD']['TX']
    #             message_info['RT2_RollBack_CANFD']['RX'] = message_info['RT1_RollBack_CANFD']['TX']
    #
    #         # rename_duplicate_msg_names(message_info)
    #     except Exception as e:
    #         logging.error(traceback.format_exc())
    # return message_info
    return {}


def schedule_parse_function(input_list, max_workers=None):
    """批量解析 LIN 调度表（多 sheet 并行）。

    功能逻辑：
    - 使用线程池并发执行 `get_schedule`，提升多个 sheet 的解析速度。
    - tqdm 展示进度条（通常用于离线/控制台调试）。
    - 将各 sheet 的解析结果聚合为一个 dict 返回。

    参数:
    - input_list: [{sheet_name: sheet_data}, ...]
    - max_workers: 线程数；默认按 CPU 核数估算，上限 4。

    返回:
    - {sheet_name: [ {frame_name, tans_time, frame_row, frame_column, ...}, ... ]}
    """
    if not max_workers:
        max_workers = min(4, (os.cpu_count() or 2) * 2)
    obj = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(
            executor.map(get_schedule, input_list),
            total=len(input_list),
            desc="LIN调度表提取处理进度"
        ))
        for item in results:
            obj = {**obj, **item}
    return obj


def get_schedule(input_item: dict):
    """解析单个 LIN 调度表 sheet，抽取帧名与传输耗时等列信息。

    功能逻辑：
    - 将二维表格序列化为 JSON 字符串作为 LLM 输入。
    - 调用 LLM（ScheduleDataPrompt）识别：frame_name 列、trans_time 列，以及对应的行列索引。
    - 将 LLM 输出的"列号(数字)"转换为 Excel 风格列字母（A、B、AA...），补充 *_column_name 字段。

    返回:
    - {sheet_name: [ {...}, {...} ]}；异常时返回空列表。
    """
    jsons_res = {}
    try:
        # 在序列化前转换数据
        data = list(input_item.values())[0]
        json_str = json.dumps(data)

        # 构造AI模型的Query
        query = f"""
                请根据以下表格，返回表头信息，格式为json格式：
                {json_str}
                """

        # 调用AI模型
        schedule_data_prompt = prompts_data.get("ScheduleDataPrompt")
        res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                      schedule_data_prompt.replace("{", "{{").replace("}", "}}"))
        global_config.llm_spend_token["excel_parse"] += spend_token
        jsons_res = extract_json(res)
        for json_res in jsons_res:
            i = int(json_res.get("frame_column"))
            if i:
                column_name = ""
                while i > 0:
                    i -= 1
                    column_name = chr(i % 26 + 65) + column_name
                    i //= 26
                json_res["frame_column_name"] = column_name
            j = int(json_res.get("trans_time_column"))
            if j:
                column_name = ""
                while j > 0:
                    j -= 1
                    column_name = chr(j % 26 + 65) + column_name
                    j //= 26
                json_res["trans_time_column_name"] = column_name
        return {list(input_item.keys())[0]: jsons_res}
    except Exception as e:
        logging.error(traceback.format_exc())
        return {list(input_item.keys())[0]: jsons_res}


def nvm_map_function(input_list, max_workers=None):
    """批量解析 NVM 配置表（多 sheet 并行）。

    功能逻辑：
    - 使用线程池并发执行 `get_nvm`。
    - 聚合每个 sheet 的解析结果为一个 dict。

    返回:
    - {sheet_name: {common: {...}, block: {...}}}
    """
    if not max_workers:
        max_workers = min(4, (os.cpu_count() or 2) * 2)
    obj = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(
            executor.map(get_nvm, input_list),
            total=len(input_list),
            desc="NVM提取处理进度"
        ))
        for item in results:
            obj = {**obj, **item}
    return obj


def get_nvm(input_item: dict):
    """解析单个 NVM 配置 sheet，抽取 common 配置值与 block 表头/字段映射。

    功能逻辑：
    - 先对输入数据做 datetime → string 的序列化预处理。
    - 将二维数据转成"第1行/第2行..."的字典，增强 LLM 读取定位能力。
    - 从知识库 global_var.kb 中读取字段定义（common 与 block），拼接为 properties，注入到 NvmExcelPrompt。
    - 调用 LLM 输出：
      - common: 每个通用参数的 value/row/column
      - block.headers: block 表头所在行（可能多行）
      - block.fields: 配置字段与 Excel 表头的匹配关系
    - 将 headers 做 -1 偏移（把 LLM 的 1-based 行号改为 0-based，用于后续 pandas/列表索引）。

    返回:
    - {sheet_name: out_put_res}；异常时返回空字典。
    """
    try:
        # 在序列化前转换数据
        data = list(input_item.values())[0]
        converted_data = convert_datetime(data)
        converted_dict = {}
        index = 1
        for line in converted_data:
            converted_dict["第" + str(index) + "行"] = line
            index += 1
        json_str = json.dumps(converted_dict, ensure_ascii=False)

        # 构造AI模型的Query
        query = f"""
                请根据以下表格，返回NVM信息，格式为json格式：
                {json_str}
                """
        ori_sys_prompt = prompts_data.get("NvmExcelPrompt").replace("{", "{{").replace("}", "}}").replace(
            "{{properties}}", "{properties}")

        nvm_common_key_mapping = global_var.kb.get("sheet_info", {}).get("nvm_common", {}).get("fields", {})
        nvm_prompt = {}
        for key, value in nvm_common_key_mapping.items():
            description_str = ""
            for description in value["description"]:
                description_str += description.rstrip(".").rstrip("。") + "。"
            if value.get("mapping_name", False):
                description_str += "它可能的表头名为：" + '、'.join(value["mapping_name"]) + "。"
            nvm_prompt[key] = description_str

        nvm_block_key_mapping = global_var.kb.get("sheet_info", {}).get("nvm_block", {}).get("fields", {})
        nvm_block_prompt = {}
        for key, value in nvm_block_key_mapping.items():
            description_str = ""
            for description in value["description"]:
                description_str += description.rstrip(".").rstrip("。") + "。"
            if value.get("mapping_name", False):
                description_str += "它可能的表头名为：" + '、'.join(value["mapping_name"]) + "。"
            nvm_block_prompt[key] = description_str

        properties = {
            "properties": {
                "common": nvm_prompt,
                "block": nvm_block_prompt
            }
        }
        # 使用 json.dumps 美化输出，并保留双花括号转义
        formatted_properties = json.dumps(properties, ensure_ascii=False, indent=4)
        sys_prompt = ori_sys_prompt.format(properties=formatted_properties).replace("{", "{{").replace("}", "}}")

        # 调用AI模型
        res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                      sys_prompt)
        global_config.llm_spend_token["excel_parse"] += spend_token
        out_put_res = extract_json(res)
        logging.info(f"nvm out_put_res : {out_put_res}")
        if out_put_res.get('block').get('headers'):
            headers = out_put_res.get('block').get('headers')
            for i in range(len(headers)):
                headers[i] -= 1  # 直接修改原列表元素
        return {list(input_item.keys())[0]: out_put_res}
    except Exception as e:
        logging.error(traceback.format_exc())
        return {list(input_item.keys())[0]: {}}



def table_header_map_function(input_list, max_workers=None):
    """批量识别多个 sheet 的表头位置（横/竖表头 + index）。

    功能逻辑：
    - 并发调用 `get_table_header`。
    - 将每个 sheet 的识别结果合并为一个 dict。

    输出一般形态：
    - {sheet_name: {"direction": "horizontal"|"vertical", "index": [行号或列号列表]}}
    """
    if not max_workers:
        max_workers = min(4, (os.cpu_count() or 2) * 2)
    obj = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(
            executor.map(get_table_header, input_list),
            total=len(input_list),
            desc="表头提取处理进度"
        ))
        for item in results:
            obj = {**obj, **item}
    return obj


def get_table_header(input_item: dict):
    """调用 LLM 识别单个 sheet 的表头结构信息。

    功能逻辑：
    - 将 sheet 的局部采样数据（header_input）转为 JSON 字符串。
    - 使用 prompts_data["table_header_prompt"] 提示词，让 LLM 返回表头方向与表头所在 index。

    返回:
    - {sheet_name: header_info_json}
    """
    try:
        # 在序列化前转换数据
        data = list(input_item.values())[0]
        converted_data = convert_datetime(data)
        json_str = json.dumps(converted_data, ensure_ascii=False)

        # 构造AI模型的Query
        query = f"""
                请根据以下表格，返回表头信息，格式为json格式：
                {json_str}
                """

        # 调用AI模型
        res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                      prompts_data.get("table_header_prompt").replace("{", "{{").replace("}", "}}"))
        global_config.llm_spend_token["excel_parse"] += spend_token
        return {list(input_item.keys())[0]: extract_json(res)}
    except Exception as e:
        logging.error(traceback.format_exc())
        return {list(input_item.keys())[0]: {}}


# 多线程实现
def map_function(input_list, excel_signal_prompt, max_workers=None):
    """批量生成"字段 → Excel 表头"的映射关系（多 sheet 并行）。

    功能逻辑：
    - 并发调用 `get_signal`，对每个 sheet 的表头进行语义匹配。
    - 输出 mapping 用于后续 `compose_data` 逐列抽取值。

    参数:
    - excel_signal_prompt: 不同业务使用不同 prompt（如 CAN 信号表、LIN 信号表）。

    返回:
    - {sheet_name: {"ComSignal": {field: {title_name: "列名"}, ...}}}
    """
    if not max_workers:
        max_workers = min(4, (os.cpu_count() or 2) * 2)
    obj = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(
            executor.map(lambda x: get_signal(x, excel_signal_prompt), input_list),
            total=len(input_list),
            desc="处理进度"
        ))
        for item in results:
            # 添加类型检查，确保 item 是字典
            if isinstance(item, dict):
                obj = {**obj, **item}
            else:
                logging.error(f"Skipping non-dict item: {type(item)}, value: {item}")
    return obj


def get_signal(input_item, excel_signal_prompt):
    """对单个 sheet 的表头做字段映射推理（LLM）。

    功能逻辑：
    - input_item 形如 {sheet_name: "col1,col2,..."}。
    - 将其作为 query，配合 excel_signal_prompt，让 LLM 输出目标 JSON（字段→表头列名）。
    - 通过 `extract_json` 做 JSON 清洗/容错解析。

    返回:
    - dict（以 sheet_name 为 key 的映射结构）。
    """
    json_str = json.dumps(input_item)
    # ws_client.send(f"  Start parsing sheet[{list(input_item.keys())[0]}]", status="pending")

    # 构造AI模型的Query
    query = f"""
            请根据以下Excel文件sheet页的表头，生成字段映射关系，返回JSON格式：
            Excel文件sheet页的表头信息: {json_str}
            注意: 键名为sheet页名称，键值为表头信息
        """

    # 调用AI模型
    res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                  excel_signal_prompt)
    logging.info(f" init Signal Res: {res}")
    global_config.llm_spend_token["excel_parse"] += spend_token
    return extract_json(res)

def get_signal1():
    """返回一个示例映射（用于本地调试/示例）。

    功能逻辑：
    - 直接构造一个典型 CAN 信号表的字段映射结构（ComSignal 下多字段）。
    - 最终仍通过 extract_json 走统一的"解析/规范化"流程。

    注意：
    - 该函数通常不参与正式流程，更多是样例/测试。
    """
    res = {
          "Rx_Public_CANFD2": {
            "ComSignal": {
              "ShortName": {"title_name": "Signal Name"},
              "BitSize": {"title_name": "Signal Length"},
              "BitPosition": {"title_name": "Start Bit Position"},
              "SignalType": {"title_name": ""},
              "SignalEndianness": {"title_name": ""},
              "SignalInitValue": {"title_name": "Default Value (hex)"},
              "SignalMinValue": {"title_name": "Signal Min Value (phys)"},
              "SignalMaxValue": {"title_name": "Signal Max Value (phys)"},
              "SignalDataInvalidValue": {"title_name": "Invalid Value (hex)"},
              "TimeoutValue": {"title_name": ""},
              "TransferProperty": {"title_name": ""},
              "UpdateBitPosition": {"title_name": ""},
              "SystemTemplateSystemSignalRef": {"title_name": ""},
              "MsgName": {"title_name": "Msg Name"},
              "MsgDelayTime": {"title_name": ""},
              "Offset": {"title_name": "Offset"},
              "MsgNrOfReption": {"title_name": ""},
              "MsgSendType": {"title_name": "Msg Send Type"},
              "MsgId": {"title_name": "Msg ID (hex)"},
              "MsgLength": {"title_name": "Msg Length (bytes)"},
              "MsgCycleTime": {"title_name": "Msg Cycle Time (ms)"},
              "EcuName": {"title_name": "ECU (Tx)"},
              "MsgType": {"title_name": ""},
              "Remark": {"title_name": "Remark"}
            }
          }
        }
    # global_config.llm_spend_token["excel_parse"] += spend_token
    return extract_json(res)



def rebuild_nested_dict(flat_dict: Dict[str, List[Union[str, int, float]]]) -> Dict[
    str, List[Dict[str, Union[str, int, float]]]]:
    """将"扁平路径 → 列值列表"的结构还原为嵌套 JSON 列表。

    功能逻辑：
    - 输入形如：
      - "ComSignal.ComBitSize": [8, 16, ...]
      - "ComSignal.ShortName": ["Sig1", "Sig2", ...]
    - 先按顶层 key（如 ComSignal）分组，再按最大行数对齐。
    - 对不同字段列表长度不一致的情况做容错：缺失项填充空字符串。

    输出形如：
    - {"ComSignal": [ {"ComBitSize": 8, "ShortName": "Sig1"}, ... ]}
    """
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

    def safe_get(lst: List, index: int, default: str = "") -> Union[str, int, float]:
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


def update_com_bit_size_and_signal_length(path_data):
    """按规则修正 ComBitSize 与 ComSignalLength 的互斥关系。

    背景：
    - 在 AUTOSAR/通信信号定义中，部分场景用 BitSize 表达信号长度；超长信号可能用 SignalLength。

    功能逻辑（当前规则）：
    - 若 bit_size <= 64：保留 ComBitSize，清空 ComSignalLength。
    - 若 bit_size > 64：清空 ComBitSize，保留 ComSignalLength。
    - 若遇到非数字/异常：两者都置空。

    返回:
    - 更新后的 path_data（就地修改后返回）。
    """
    """
    Update ComBitSize and ComSignalLength values in path_data based on the given rules.
    """
    # 获取 ComBitSize 和 ComSignalLength 的值列表
    com_bit_sizes = path_data.get("ComSignal.ComBitSize", [])
    com_signal_lengths = path_data.get("ComSignal.ComSignalLength", [])

    # 检查两个字段的长度是否一致
    if len(com_bit_sizes) != len(com_signal_lengths):
        logging.error("ComBitSize and ComSignalLength lists must have the same length.")

    # 创建新的值列表
    updated_com_bit_sizes = []
    updated_com_signal_lengths = []

    # 遍历 ComBitSize 的值，并根据规则修改
    for bit_size, signal_length in zip(com_bit_sizes, com_signal_lengths):
        try:
            # 转换为整数进行比较
            bit_size = int(bit_size)
            signal_length = int(signal_length)

            if bit_size <= 64:
                # 如果 ComBitSize 小于 64，保持原值，清空 ComSignalLength
                updated_com_bit_sizes.append(bit_size)
                updated_com_signal_lengths.append("")
            else:
                # 如果 ComBitSize 大于或等于 64，清空 ComBitSize，保持原值
                updated_com_bit_sizes.append("")
                updated_com_signal_lengths.append(signal_length)
        except ValueError:
            # 如果转换失败（例如值不是整数），保持原值
            updated_com_bit_sizes.append("")
            updated_com_signal_lengths.append("")

    # 更新 path_data 中的值
    path_data["ComSignal.ComBitSize"] = updated_com_bit_sizes
    path_data["ComSignal.ComSignalLength"] = updated_com_signal_lengths

    return path_data


def compose_data(input_dict, data_source):
    """依据"字段→表头映射"从 sheet 中抽取列数据，并重建为嵌套结构。

    输入:
    - input_dict: 映射树（叶子值通常为 "SheetName|ColumnName" 或空字符串）。
    - data_source: 包含 sheet 数据与表头所在行信息，例如：
      - {sheet_name: sheet_data, "header_index": header_row_idx}

    功能逻辑：
    1) 递归遍历 input_dict，提取所有叶子路径（如 ComSignal.ComBitSize）。
    2) 对每个叶子：
       - 若映射为空，则按行数填充空值列。
       - 否则定位表头列 index，并从表头下一行开始逐行收集该列的值。
    3) 对抽取出的 path_data 应用 `update_com_bit_size_and_signal_length`。
    4) 用 `rebuild_nested_dict` 还原成嵌套列表结构。

    返回:
    - 嵌套 dict（通常顶层为 ComSignal）。
    """
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
    leaf_key_values = extract_leaf_keys(input_dict)
    path_data = {}
    for path, value in leaf_key_values:
        # 如果 value 为空字符串，逐行填充空值
        if not value:  # 如果 value 是空字符串
            sheet_name = list(data_source.keys())[0]  # 假设从第一个 sheet 获取行数
            sheet_data = data_source[sheet_name]
            num_rows = len(sheet_data) - 1  # 减去表头行
            path_data[path] = [""] * num_rows  # 用空字符串填充每一行
            continue

        data = value.split("|")
        sheet_name = data[0]
        col_name = data[1]
        sheet_data = data_source[sheet_name]
        header = sheet_data[data_source["header_index"]]
        header_index = -1
        for index, header_name in enumerate(header):
            if header_name.strip().lower().replace('\n', '') == col_name.strip().lower():
                header_index = index
                break
        if header_index == -1:
            logging.info(f"Column '{col_name}' not found in sheet '{sheet_name}'")
            path_data[path] = [""]  # 如果列未找到，填充空列表
            continue

        current_data = []
        for row in sheet_data[data_source["header_index"] + 1:]:
            # 检查是否是空行，跳过空行
            # if all(cell in (None, "") for cell in row):  # 如果整行都是空值，跳过
            #     continue
            # 提取值并过滤空值
            cell_value = row[header_index]
            # if cell_value not in (None, ""):  # 跳过 None 和空字符串
            current_data.append(cell_value)

        path_data[path] = current_data
    updated_path_data = update_com_bit_size_and_signal_length(path_data)
    resp = rebuild_nested_dict(updated_path_data)
    return resp


def get_channel_name_by_sheet_name(sheet_name):
    """从 sheet 名称推断通道名（channel）与方向（TX/RX）。

    功能逻辑：
    - 若包含 Tx_ / Rx_：去掉前缀并返回方向 TX/RX。
    - 若包含 DebugMessage：视为特殊表，但方向置空。

    返回:
    - (channel_name, direction)
    """
    """
    Process sheet name by removing Tx_, Rx_, or DebugMessage prefixes.

    Args:
        sheet_name (str): The input sheet name string

    Returns:
        channel_name: The processed channel name with prefixes removed OR None
        direction: "TX" or "RX" or ""
    """
    # Define the prefixes to remove which only channel_name had
    prefixes = ['Tx_', 'Rx_', 'DebugMessage']

    # Remove each prefix if it exists in the sheet_name
    for prefix in prefixes:
        if prefix in sheet_name:
            if prefix in ["Tx_"]:
                direction = "TX"
            elif prefix in ["Rx_"]:
                direction = "RX"
            else:
                direction = ""
            channel_name = sheet_name.replace(prefix, '')
            return channel_name.strip(' '), direction
    else:
        return '', ''


def get_channel_name(sheet_name):
    """从 sheet 名称提取通道名（channel）与方向（TX/RX）。

    功能逻辑：
    - 仅处理以 "Tx_" / "Rx_" 开头的格式，直接切片去前缀。
    - 其他情况原样返回，方向为空。

    返回:
    - (channel_name, direction)
    """
    """
    从给定的sheetname中提取通道名称。

    参数:
        sheet_name (str): 输入的Sheet名称，例如 'Tx_CAN_FLZCU_BD'。

    返回:
        str: 提取的通道名称，例如 'CAN_FLZCU_BD'。
    """
    # 按下划线分隔字符串
    # parts = sheet_name.split('_')
    #
    # # 如果格式符合预期，返回第二部分及之后的内容
    # if len(parts) > 1:
    #     return '_'.join(parts[1:])  # 从第二部分开始拼接
    # else:
    #     # 如果格式不符合预期，返回空字符串或提示
    #     return sheet_name
    if sheet_name.startswith("Tx_"):
        return sheet_name[3:], "TX"  # 删除 "Tx_" 前缀
    elif sheet_name.startswith("Rx_"):
        return sheet_name[3:], "RX"  # 删除 "Rx_" 前缀
    else:
        return sheet_name, ""  # 原样返回


def get_direction(sheet_name):
    """通过 LLM 根据 sheet 名称列表推断每个 sheet 的方向信息。

    功能逻辑：
    - 使用 prompts_data["DirectionPrompt"] 描述任务。
    - LLM 返回一个映射表（通常为 {"content": [..]} 或其它结构，取决于 prompt 输出定义）。

    返回:
    - direction_map: LLM 输出解析后的 JSON。
    """
    direction_prompt = prompts_data.get("DirectionPrompt")
    query = f"请根据sheet名称列表{sheet_name},返回对应的不同sheet名称的方向信息"
    res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                  direction_prompt.replace("{", "{{").replace("}", "}}"))
    global_config.llm_spend_token["excel_parse"] += spend_token
    direction_map = extract_json(res)
    return direction_map


def get_excel_column_mapping(headers):
    """根据表头列数生成"表头文本 → Excel 列字母(A/B/AA...)"映射。

    功能逻辑：
    - 按 headers 的顺序生成对应 Excel 列字母。
    - 过滤掉空白表头。

    返回:
    - mapping: {"Signal Name": "A", "Msg ID": "D", ...}
    """
    """
    根据传入的表头列表动态生成Excel列名映射关系。

    :param headers: List[str] 表头列表
    :return: dict 表头与Excel列名的映射关系
    """
    # 获取Excel列名（A, B, C, ..., Z, AA, AB, ...）
    excel_columns = []
    for i in range(1, len(headers) + 1):
        column_name = ""
        while i > 0:
            i -= 1
            column_name = chr(i % 26 + 65) + column_name
            i //= 26
        excel_columns.append(column_name)

    # 创建映射关系
    mapping = {header: excel_columns[idx] for idx, header in enumerate(headers) if header.strip()}
    return mapping


def update_com_sys_signal_ref_trace(signal, message_name, signal_name):
    """生成 SystemTemplateSystemSignalRef，并合并 trace 信息。

    功能逻辑：
    - 组合 message_name 与 signal_name，形成 "Msg/Signal" 形式引用字符串。
    - 将 MsgName 与 ShortName 的 trace 合并，作为引用字段 trace，提升可追溯性。

    返回:
    - {"value": "...", "trace": [...], "type": "user"}
    """
    signal_trace = signal.get("ShortName", {}).get("trace", [])
    message_trace = signal.get("MsgName", {}).get("trace", [])
    message_trace.extend(signal_trace)
    value = f'{message_name}/{signal_name.get("value")}'
    return {
        "value": value,
        "trace": message_trace,
        "type": "user"

    }


def convert_to_decimal(input_str):
    """将十六进制/十进制字符串转换为十进制整数。

    功能逻辑：
    - 支持以 0x 开头或包含 A-F 字母的十六进制字符串。
    - 其它情况按十进制解析。
    - 解析失败返回错误提示字符串（而非抛异常）。

    用途：
    - Excel/需求输入里常见 ID 字段以 hex 表示，需要统一转换。
    """
    try:
        # 判断是否是16进制字符串（以0x开头或包含字母A-F）
        if input_str.startswith("0x") or any(char.upper() in "ABCDEF" for char in input_str):
            # 处理16进制转换为10进制
            return int(input_str, 16)
        else:
            # 直接转换为10进制
            return int(input_str)
    except ValueError:
        return "输入无效，请确保输入为数字或16进制字符串"

if __name__ == '__main__':
    header_input = [{'LIN1': [['CCU LIN1 Messages', '', '', '', '', '', '', '', '', ''],
                              ['ECU (Tx)', 'Frame Name', 'LIN ID (hex)', 'Protected ID (hex)', 'Frame Length (bytes)',
                               'Frame Send Type', 'Frame Cycle Time (ms)', 'Signal Name', 'Signal Comment',
                               'Start Bit Position'], ['Application Frames', '', '', '', '', '', '', '', '', ''],
                              ['CCURT1', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'UMM_UsageModeSt',
                               'Usage mode state', 0],
                              ['CCURT2', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'WW_ScreenType',
                               'Type of windscreen', 3],
                              ['CCURT1', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'Not used', '', 7],
                              ['CCU', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'BCS_VehSpdVD',
                               'Quality/fault information to vehicle speed', 12],
                              ['CCU', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'BCS_VehSpd', 'Vehicle speed', 13],
                              ['CCURT2', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'WW_RS_Cali_Data',
                               'Rain sensor calibration data', 26],
                              ['CCURT1', 'CCU_LIN1_1', '0x10', '0x50', 8, 'UF', 60, 'Not used', '', 30]]}, {
                        'LIN2': [['CCU LIN2 Messages', '', '', '', '', '', '', '', '', ''],
                                 ['ECU (Tx)', 'Frame Name', 'LIN ID (hex)', 'Protected ID (hex)',
                                  'Frame Length (bytes)', 'Frame Send Type', 'Frame Cycle Time (ms)', 'Signal Name',
                                  'Signal Comment', 'Start Bit Position'],
                                 ['Application Frames', '', '', '', '', '', '', '', '', ''],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'UMM_UsageModeSt',
                                  'Usage mode state', 0],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'UMM_PowerKeepMode',
                                  'Power Keep Mode', 3],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'UMM_PowerOffEnable',
                                  'Power off Enable Status', 4],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'UMM_PowerKeepEnable',
                                  'Power keep Enable Status', 5],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'Not used', '', 6],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'VMM_VehModeSt',
                                  'Vehicle mode state', 8],
                                 ['CCURT1', 'CCU_LIN2_1', '0x11', '0x11', 8, 'UF', 60, 'VMM_LastVehModeSt',
                                  'Last time vehicle mode', 12]]}]
    header_infos = table_header_map_function(header_input)
    print(header_infos)