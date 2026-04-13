# -*- coding: utf-8 -*-
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Any

from .excel_ai_parse import (
    get_routing_msg,
    get_signal_mapping_data,
    get_schedule_data,
    get_nvm_main_data
)
from .prompt import prompts_data
from .global_cfg import global_config
from . import global_var
from .global_config_class import GlobalConfig
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_routing_msg_map():
    return {
        "dataContentStartRow": "表内容开始行所对应的行号",
        "channelNameInfoRow": "通道名信息所对应的行号",
        "letterRepresentingSourceChannelName": "表示源通道名的标识符",
        "letterRepresentingDestinationChannelName": "表示目标通道的标识符",
        "letterRepresentingBothSourceAndDestinationChannelName": "表示同时是源通道名和目标通道名的所在列的标识符",
        "sourceSignalName": "表示源信号名称的行列号",
        "sourcePduName": "表示源pdu名称的行列号",
        "sourcePduId": "表示源pduId的行列号",
        "destinationSignalName": "表示目标信号的行列号",
        "destinationPduName": "表示目标pdu名称的行列号",
        "destinationPduId": "表示目标pduId的行列号",
        "routingType": "表示路由类型的行列号",
        "isLLCE": "表示标识是否为LLCE路由的行列号",
        "max_row_count": "最大行数",
        "max_column_count": "最大列数",
    }


def get_routing_msg_des(routing_msg):
    routing_msg_map = get_routing_msg_map()
    _routing_msg = {}
    for k, v in routing_msg.items():
        _routing_msg[k] = {
            "value": v,
            "description": routing_msg_map.get(k, "")
        }
    return _routing_msg


def parse_can_routing_data(can_routing_data):
    routing_msg = []
    for sheet_data in can_routing_data:
        can_routing_name = sheet_data["routing_name"]
        can_routing_file_path = sheet_data["file_path"]
        this_routing_msg = get_routing_msg(can_routing_file_path, can_routing_name)
        routing_msg.append({
            "routing_name": can_routing_name,
            "routing_msg": get_routing_msg_des(this_routing_msg),
            "file_path": can_routing_file_path
        })
    return routing_msg


def parse_can_signal_data(can_signal_sheet_data):
    can_signal_mapping_infos = []
    for sheet_data in can_signal_sheet_data:
        file_path = sheet_data["file_path"]
        sheet_names = sheet_data["sheet_names"]
        if not sheet_names:
            continue
        excel_signal_prompt = prompts_data.get("ExcelSignalPrompt")
        sys_prompt = modify_signal_prompt(excel_signal_prompt, "can_signal")
        mapping_data = get_signal_mapping_data(file_path, sheet_names, sys_prompt)
        if mapping_data.get("mapping_info"):
            mapping_data["mapping_info"] = ensure_mapping_fields_complete(mapping_data["mapping_info"], "can_signal")
        can_signal_mapping_infos.append({"file_path": file_path, "mapping_data": mapping_data})
    return can_signal_mapping_infos


def parse_lin_signal_scheduler_data(lin_signal_scheduler_data):
    lin_signal_scheduler_mapping_infos = []
    for sheet_data in lin_signal_scheduler_data:
        file_path = sheet_data["file_path"]
        sheet_names = sheet_data["sheet_names"]
        if sheet_data["sheet_type"] == "lin":
            excel_signal_prompt = prompts_data.get("LinExcelSignalPrompt")
            sys_prompt = modify_signal_prompt(excel_signal_prompt, "lin_signal")
            mapping_data = get_signal_mapping_data(file_path, sheet_names, sys_prompt)
            if mapping_data.get("mapping_info"):
                mapping_data["mapping_info"] = ensure_mapping_fields_complete(mapping_data["mapping_info"], "lin_signal")
            lin_signal_scheduler_mapping_infos.append(
                {"file_path": file_path, "mapping_data": mapping_data})
        elif sheet_data["sheet_type"] == "schedule":
            schedule_data = get_schedule_data(file_path, sheet_names)
            lin_signal_scheduler_mapping_infos.append(
                {"file_path": file_path, "schedule_data": schedule_data})
    return lin_signal_scheduler_mapping_infos


def parse_nvm_data(nvm_data):
    nvm_datas = []
    for sheet_data in nvm_data:
        file_path = sheet_data["file_path"]
        if not sheet_data["sheet_name"]:
            continue
        sheet_name = sheet_data["sheet_name"]
        sheet_names = sheet_name if isinstance(sheet_name, list) else [sheet_name]
        if sheet_names:
            nvm_datas.append(get_nvm_main_data(file_path, sheet_names))
    return nvm_datas


def modify_signal_prompt(excel_signal_prompt, module_name):
    ori_sys_prompt = excel_signal_prompt.replace("{", "{{").replace("}", "}}").replace("{{properties}}", "{properties}")
    nvm_common_key_mapping = global_var.kb.get("sheet_info", {}).get(module_name, {}).get("fields", {})
    nvm_prompt = {}
    for key, value in nvm_common_key_mapping.items():
        description_str = ""
        for description in value.get("description", []):
            description_str += description.rstrip(".").rstrip("。") + "。"
        if value.get("mapping_name", False):
            description_str += "它可能的表头名为：" + '、'.join(value["mapping_name"]) + "。"
        nvm_prompt[key] = description_str
    properties = {
        "Tx_aaa": {
            "ComSignal": nvm_prompt
        }
    }
    formatted_properties = json.dumps(properties, ensure_ascii=False, indent=4)
    sys_prompt = ori_sys_prompt.format(properties=formatted_properties).replace("{", "{{").replace("}", "}}")
    return sys_prompt


def ensure_mapping_fields_complete(mapping_info, module_name):
    expected_fields = global_var.kb.get("sheet_info", {}).get(module_name, {}).get("fields", {})
    if not expected_fields:
        return mapping_info
    for sheet_name, sheet_data in mapping_info.items():
        if "ComSignal" in sheet_data:
            com_signal = sheet_data["ComSignal"]
            for field_name in expected_fields:
                if field_name not in com_signal:
                    com_signal[field_name] = {"title_name": ""}
    return mapping_info


def save_extract_info(extract_info, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    extract_params_info_path = os.path.join(
        output_dir,
        "extract_params_info.json"
    )

    with open(extract_params_info_path, 'w', encoding='utf-8') as f:
        json.dump(extract_info, f, ensure_ascii=False, indent=2)

    logging.info(f"**Successfully generated requirement reading rule file, path: {extract_params_info_path}**")
    return extract_params_info_path


def extract_mapping_info(global_config:GlobalConfig):
    logging.info("**Start intelligent parsing of requirement file, generate requirement reading rules**")
    # 核心的输入信息：
    # 1. sheet信息的文件
    # 2. 映射文件的输出文件路径
    output_dir = os.path.join(global_config.current_work_space["project_directory"],global_config.current_work_space["project_name"])
    extract_routing_data_and_signal_sheet_data_path = global_config.previous_data["extract_routing_data_and_signal_sheet_data"]

    try:
        with open(extract_routing_data_and_signal_sheet_data_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        data = metadata

        can_routing_data = parse_can_routing_data(data.get("can_routing_data"))
        can_signal_data = parse_can_signal_data(data.get("can_signal_sheet_data"))
        lin_data = parse_lin_signal_scheduler_data(data.get("lin_signal_scheduler_data"))
        nvm_data = parse_nvm_data(data.get("nvm_data", []))

        extract_info = {
            "can_routing_data": can_routing_data,
            "can_signal_mapping_infos": can_signal_data,
            "lin_signal_scheduler_mapping_infos": lin_data,
            "nvm_datas": nvm_data
        }

        extract_params_info_path = save_extract_info(extract_info, output_dir)
        global_config.previous_data["extract_params_info_path"] = extract_params_info_path


        # return {
        #     "code": 1,
        #     "msg": "",
        #     "next_step": "",
        #     "confirm_content": [
        #         {
        #             "name": "mapping info",
        #             "path": extract_params_info_path,
        #         }
        #     ],
        #     "confirm_buttons": "Confirm"
        # }
        return extract_params_info_path


    except Exception as e:
        error_msg = f"""Failed to generate requirement reading rule file, error information: {traceback.format_exc()}"""
        logging.error(error_msg)
        return {
            "code": 0,
            "msg": error_msg,
        }


if __name__ == "__main__":
    # input_data = {
    #     "can_routing_data": [
    #         {
    #             "routing_name": "",
    #             "file_path": "D:\\KoTEI_CODE\\Agent_Autosar_Backend\\new_data\\AY5-G Project_CMX_EEA3.0_CCU_LIN_MIX_V1.4 - 增加诊断(LIN诊断相关).xlsx"
    #         }
    #     ],
    #     "can_signal_sheet_data": [],
    #     "lin_signal_scheduler_data": [
    #         {
    #             "file_path": "D:\\KoTEI_CODE\\Agent_Autosar_Backend\\new_data\\AY5-G Project_CMX_EEA3.0_CCU_LIN_MIX_V1.4 - 增加诊断(LIN诊断相关).xlsx",
    #             "sheet_names": [
    #                 "LIN1",
    #                 "LIN2"
    #             ],
    #             "sheet_type": "lin"
    #         },
    #         {
    #             "file_path": "D:\\KoTEI_CODE\\Agent_Autosar_Backend\\new_data\\AY5-G Project_CMX_EEA3.0_CCU_LIN_MIX_V1.4 - 增加诊断(LIN诊断相关).xlsx",
    #             "sheet_names": [
    #                 "调度表",
    #                 "调度表1"
    #             ],
    #             "sheet_type": "schedule"
    #         }
    #     ],
    #     "nvm_data": [
    #         {
    #             "sheet_name": "",
    #             "file_path": "D:\\KoTEI_CODE\\Agent_Autosar_Backend\\new_data\\AY5-G Project_CMX_EEA3.0_CCU_LIN_MIX_V1.4 - 增加诊断(LIN诊断相关).xlsx"
    #         }
    #     ]
    # }
    input_data_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\AutoSAR_Agent\autosar_temp_test\my_test\output\测试\extract_routing_data_and_signal_sheet_data.json"

    global_config.current_work_space['project_directory'] = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data"

    result = extract_mapping_info(input_data_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
