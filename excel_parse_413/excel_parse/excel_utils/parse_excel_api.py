# -*- coding: utf-8 -*-
"""
@File    : parse_excel_api.py
@Date    : 2025--08-19 13:29
@Desc    : Description of the file
@Author  : lei
"""

import logging
import traceback
from .logic_AutoPy import scan_routing_table, transform_routing_data
from .global_cfg import global_config


# 解析路由表
def parse_routing_table_api(excel_path: str, routing_msg: dict, gw_routing_name: str):
    """解析网关路由表并输出"一对多"结构。

    功能逻辑：
    - 输入 routing_msg（由 LLM 从表头识别出来的关键列/行配置）与 gw_routing_name（路由表 sheet 名）。
    - 调用 `scan_routing_table` 逐行扫描路由表，提取每条路由的 source/target/pdu/signal/channel 等字段（带 trace）。
    - 调用 `transform_routing_data` 将逐行记录归并为：一个 source 对应多个 targets 的结构。
    - 同时产出一份 pdur_result（routingType==0 的子集）并同样转换结构。

    返回:
    - (routing_data_transformed, pdur_data)
    """
    try:
        # # 解读路由表头
        # workbook = openpyxl.load_workbook(excel_path)
        # sheet_names = workbook.sheetnames
        # gw_routing_name = get_sheet_name(sheet_names, excel_query_gw_sheet_prompt)
        # if not gw_routing_name:
        #     logging.error(f"没有路由表,当前excel sheet列表为[sheet_names]")
        #     return {}, []
        # routing_msg = parse_excel(excel_path, gw_routing_name)

        logging.info(global_config.excel_exception_list)
        # 遍历路由表内容，转化成"一对多"结构
        routing_data, pdur_result = scan_routing_table(excel_path, routing_msg, gw_routing_name)
        routing_data_transformed = transform_routing_data(routing_data)
        pdur_data = transform_routing_data(pdur_result)

        return routing_data_transformed, pdur_data
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"Exception occurred: {e}")
        return {}, {}
