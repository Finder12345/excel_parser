# -*- coding: utf-8 -*-
"""
@File    : logic_LLM.py
@Date    : 2025--08-19 13:26
@Desc    : Description of the file
@Author  : lei
"""

import logging
import time
import traceback

from .logic_AutoPy import extract_json
from .prompt import prompts_data
from .ExcelToJson import excel_to_json
import re
from .global_cfg import global_config
from .dep_llm import call_model
from . import global_var


def extract_json_2(input_str):
    """从文本中提取 JSON 片段（正则兜底）。

    功能逻辑：
    - 通过正则匹配第一个 "{ ... }" 区间（DOTALL 支持跨行）。
    - 用于处理 LLM 输出夹杂说明文本/markdown 时的粗粒度提取。

    注意：
    - 该函数只返回字符串片段，不负责 json.loads。
    - 当前主流程更偏向使用 logic_AutoPy.extract_json 做更强的容错解析。
    """
    # 使用正则表达式匹配JSON内容
    json_pattern = re.search(r"\{.*\}", input_str, re.DOTALL)
    if json_pattern:
        json_content = json_pattern.group()
        return json_content


# def parse_excel(excel_path: str, sheet_name) -> dict:
#     try:
#         # 导入Excel
#         excel_to_json_content = excel_to_json(excel_path, sheet_name)
#         json_path = os.path.join(python_project_root, "resources", "routing_table_msg.json")
#         with open(json_path, 'r', encoding='utf-8') as f:
#             routing_table_msg = json.load(f)
#
#         json_content = f"""
#             {{
#                 "dataContentStartRow": None,   # value必须是数字
#                 "channelNameInfoRow": None,   # value必须是数字
#                 "letterRepresentingSourceChannelName": "{routing_table_msg['headerStructure']['sourceChannelIdentifier']}", # 该项一字不差原样返回
#                 "letterRepresentingDestinationChannelName": "{routing_table_msg['headerStructure']['destinationChannelIdentifier']}",  # 该项一字不差原样返回
#                 "letterRepresentingBothSourceAndDestinationChannelName": "{routing_table_msg['headerStructure']['sourceDestinationChannelIdentifier']}",  # 该项一字不差原样返回
#                 "sourceSignalName": None,   # 它所在的列对应的表头必须在{routing_table_msg['headerStructure']['routingMatrixName']}左侧，它的表头字段名称可能是: {"或".join(routing_table_msg['headerMeaning']['signalName'])}，返回行列号
#                 "sourcePduName": None,   # 它所在的列对应的表头在{routing_table_msg['headerStructure']['routingMatrixName']}左侧，它的表头字段名称可能是: {"或".join(routing_table_msg['headerMeaning']['pduName'])}，返回行列号
#                 "destinationSignalName": None, # 它所在的列对应的表头在{routing_table_msg['headerStructure']['routingMatrixName']}右侧，它的表头字段名称可能是: {"或".join(routing_table_msg['headerMeaning']['signalName'])}，返回行列号
#                 "destinationPduName": None  # 它所在的列对应的表头在{routing_table_msg['headerStructure']['routingMatrixName']}右侧，它的表头字段名称可能是: {"或".join(routing_table_msg['headerMeaning']['pduName'])}，返回行列号
#              }}
#
#         """
#
#         query = query_gw_header.format(excel_to_json_content=excel_to_json_content,
#                                        headerRowCount=routing_table_msg['headerStructure']['headerRowCount'],
#                                        routingMatrixName=routing_table_msg['headerStructure']['routingMatrixName'],
#                                        channelNameRow=routing_table_msg['headerStructure']['channelNameRow'],
#                                        json_content=json_content)
#         _query = query.replace("{", "{{").replace("}", "}}")
#         _prompt_excel_com = prompt_excel_com.replace("{", "{{").replace("}", "}}")
#
#         res = call_model(_query, _prompt_excel_com)
#         res_json = extract_json_2(res)
#         logging.info(res_json)
#
#         return extract_json(res_json)
#     except Exception as e:
#         logging.error(traceback.format_exc())
#         logging.error(f"发生异常: {e}")


def parse_can_excel(excel_path: str, sheet_name, max_retries: int = 2) -> dict:
    """用 LLM 识别网关路由表的“结构元数据”（表头/关键列位置）。

    功能逻辑：
    1) `excel_to_json(excel_path, sheet_name)`：
       - 将路由表 sheet 的前若干行（默认 10 行）转换为“按列组织”的 JSON，供 LLM 读懂布局。
       - 同时返回 max_row_count/max_column_count（用于后续扫描与越界保护）。

    2) 从知识库读取 can_routing 的字段定义（global_var.kb["sheet_info"]["can_routing"]["fields"]），
       将每个字段的可能表头名（mapping_name）注入 ParseGwHeaderPrompt，提升识别鲁棒性。

    3) LLM 调用：
       - query = ParseGwHeaderPrompt.format(...)
       - sys_prompt = ExcelToJsonPrompt
       - 期望 LLM 输出：dataContentStartRow、channelNameInfoRow、source/destination 的 signal/pdu/pduId 列坐标、routingType/isLLCE 列坐标等。

    4) 重试与合并：
       - 多次调用 LLM（max_retries），把每次提取到的新字段补齐到 final_result。
       - 若 destinationSignalName 缺失，默认回退为 sourceSignalName。

    5) 固定字段直接从知识库注入：
       - letterRepresentingSourceChannelName / Destination / Both
       - 这些是“通道标识符”列的字母标记（如 S/D），用于后续从矩阵区识别源/目标通道。

    返回:
    - final_result: 路由表结构配置 dict；失败返回 {}。
    """
    final_result = {"max_row_count": 0, "max_column_count": 0}
    try:
        # ws_client.send(f"Start parsing sheet[{sheet_name}]", status="pending")
        # 导入Excel
        excel_to_json_content, max_row_count, max_column_count = excel_to_json(excel_path, sheet_name)
        # json_path = os.path.join(python_project_root, "resources", "routing_table_msg.json")
        # with open(json_path, 'r', encoding='utf-8') as f:
        #     routing_table_msg = json.load(f)
        routing_table_msg = global_var.kb["sheet_info"]['can_routing']['fields']
        query_gw_header_prompt = prompts_data.get("ParseGwHeaderPrompt")
        query = query_gw_header_prompt.format(
            excel_to_json_content=excel_to_json_content,
            sourceSignalName = "、".join(routing_table_msg['sourceSignalName'].get("mapping_name", "")),
            sourcePduName = "、".join(routing_table_msg['sourcePduName'].get("mapping_name", "")),
            sourcePduId = "、".join(routing_table_msg['sourcePduId'].get("mapping_name", "")),
            destinationSignalName ="、".join(routing_table_msg['destinationSignalName'].get("mapping_name", "")),
            destinationPduName = "、".join(routing_table_msg['destinationPduName'].get("mapping_name", "")),
            destinationPduId = "、".join(routing_table_msg['destinationPduId'].get("mapping_name", "")),
            routingType = "、".join(routing_table_msg['routingType'].get("mapping_name", "")),
            isLLCE = "、".join(routing_table_msg['isLLCE'].get("mapping_name", "")),
        )
        _query = query.replace("{", "{{").replace("}", "}}")
        prompt_excel_com_prompts = prompts_data.get("ExcelToJsonPrompt")
        _prompt_excel_com = prompt_excel_com_prompts.replace("{", "{{").replace("}", "}}")

        # 初始化结果
        final_result = {"max_row_count": max_row_count, "max_column_count": max_column_count}
        retries = 0
        while retries < max_retries:
            try:
                res, spend_token = call_model(_query, _prompt_excel_com)
                logging.info(f"gw res : {res}")
                global_config.llm_spend_token["excel_parse"] += spend_token
                # res_json = extract_json_2(res)
                res_json = extract_json(res)
                # 下面3个配置项，直接从知识库里面读取，不用AI进行解析
                res_json['letterRepresentingSourceChannelName'] = routing_table_msg[
                    'sourceChannelIdentifier']["mapping_name"][-1]
                res_json['letterRepresentingDestinationChannelName'] = routing_table_msg[
                    'destinationChannelIdentifier']["mapping_name"][-1]
                res_json['letterRepresentingBothSourceAndDestinationChannelName'] = \
                    routing_table_msg['sourceDestinationChannelIdentifier']["mapping_name"][-1]
                logging.info(f"Result of attempt {retries + 1}: {res_json}")

                # 合并结果
                for key, value in res_json.items():
                    if key not in final_result and (value != 'None' and value is not None):
                        final_result[key] = value

                if not final_result.get("destinationSignalName"):
                    final_result["destinationSignalName"] = final_result.get("sourceSignalName")

                # 检查是否所有字段都提取完毕
                if all(final_result.get(field) is not None for field in [
                    "dataContentStartRow", "channelNameInfoRow", "sourceSignalName",
                    "letterRepresentingSourceChannelName", "letterRepresentingDestinationChannelName",
                    "sourcePduName", "destinationSignalName",
                    "destinationPduName", "isLLCE", "destinationPduId", "routingType", "sourcePduId"
                ]):
                    logging.info("All fields have been extracted, exiting retry loop.")
                    break
            except Exception as e:
                time_sleep = 2 * (retries + 1)
                time.sleep(time_sleep)
                logging.error(f"Attempt {retries + 1} failed: {e}, sleep {time_sleep} s")
                logging.error(traceback.format_exc())

            retries += 1

        # 如果超过最大重试次数仍有字段未提取，记录警告
        if retries == max_retries and not all(final_result.get(field) is not None for field in [
            "dataContentStartRow", "channelNameInfoRow", "sourceSignalName",
            "letterRepresentingSourceChannelName", "letterRepresentingDestinationChannelName",
            "sourcePduName", "destinationSignalName", "destinationPduName", "isLLCE", "destinationPduId", "routingType", "sourcePduId"
        ]):
            logging.warning("Exceeded maximum retry attempts, some fields still not extracted successfully.")
            return {}
        logging.info(f"final_result:{final_result}")
        return final_result

    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"Exception occurred: {e}")
        return {}


if __name__ == '__main__':
    file_paths = [
        r"D:\MyCode\Autosar-Agent-Temp\data\A02-Y_纯电AB平台_CMX_CCU_V29.2(G3 G.0-1)-20251201_Result.xlsx"]

    # 解析Excel文件指定的工作表，返回一个解析的matedata
    ans = parse_can_excel(file_paths[0], "CAN Legend",max_retries=3)
    # {'max_row_count': 392, 'max_column_count': 63, 'dataContentStartRow': 6, 'channelNameInfoRow': 4, 'sourceSignalName': 'B4', 'sourcePduName': 'C4', 'sourcePduId': 'F4', 'destinationPduName': 'AM4', 'destinationPduId': 'AO4', 'routingType': 'AT4', 'isLLCE': 'N4', 'letterRepresentingSourceChannelName': 'S', 'letterRepresentingDestinationChannelName': 'D', 'letterRepresentingBothSourceAndDestinationChannelName': 'S/D', 'destinationSignalName': 'B4'}
    print(ans)