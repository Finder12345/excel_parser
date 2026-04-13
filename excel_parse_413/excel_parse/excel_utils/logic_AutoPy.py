# -*- coding: utf-8 -*-
"""
@File    : logic_AutoPy.py
@Date    : 2025--08-19 11:48
@Desc    : Description of the file
@Author  : lei
"""
import logging
import traceback


from .global_var import wbparser, support_route_type
from .prompt import prompts_data
from .dep_llm import  call_model
from collections import defaultdict
from typing import Any, Dict, List
from .global_cfg import global_config
import pandas as pd
import json,re
from json_repair import repair_json, loads

def extract_json(content):
    """将 LLM 输出文本解析为 Python 对象（JSON 容错解析）。

    功能逻辑：
    - 优先尝试直接 json.loads（说明 content 本身就是纯 JSON）。
    - 若包含 ```json ...``` 代码块，则提取代码块内容并修正 Python 风格字面量（None/True/False）。
    - 否则使用 json_repair 对“接近 JSON 但不严格”的字符串进行修复，再 loads。

    用途：
    - 统一处理不同模型/不同 prompt 返回格式差异，提升解析稳定性。
    """
    is_json = False
    try:
        json.loads(content)
        is_json = True
    except Exception as e:
        pass
    if is_json:
        return json.loads(content)
    pattern = r"```json(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    if len(matches):
        # 预处理内容，将 Python 特有值转换为 JSON 格式
        json_content = matches[0].strip()
        json_content = json_content.replace('None', 'null')  # Python None -> JSON null
        json_content = json_content.replace('True', 'true')  # Python True -> JSON true
        json_content = json_content.replace('False', 'false')  # Python False -> JSON false
        return json.loads(json_content)
    else:
        # 预处理内容，替换 Python 特有值
        processed_content = content.replace('None', 'null').replace('True', 'true').replace('False', 'false')
        repaired = repair_json(processed_content)
        return loads(repaired)




def find_and_replace_comgw_mapping(data: Dict[str, Any], new_content: List[Dict]) -> bool:
    """
    使用迭代方式查找并替换ComGwMapping内容

    参数:
        data: JSON数据字典
        new_content: 要替换的新内容

    返回:
        bool: 是否找到并替换了ComGwMapping
    """
    try:
        stack = [data]

        while stack:
            current = stack.pop()

            if isinstance(current, dict):
                if "ComGwMapping" in current:
                    current["ComGwMapping"] = new_content
                    return True

                # 将字典值加入栈中继续处理
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)

            elif isinstance(current, list):
                # 将列表元素加入栈中继续处理
                for item in current:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

        return False
    except Exception as e:
        logging.error(f"Exception occurred: {e}")


def generate_and_write_gw_mapping(input_json, excel_path, sheet_name):
    """将“一对多路由结构”转换为 ComGwMapping 风格的数据结构（带 trace）。

    输入:
    - input_json: transform_routing_data 之后的结构：{route_type: [{source:..., targets:[...]}, ...]}

    功能逻辑：
    - 先做一次关键字段缺失检查：若 source/target 通道名缺失，将提示项写入 global_config.excel_exception_list。
    - 对每条 source：
      - 组合 source_parts = [sourceChannelName, sourcePduName, sourceSignalName]
      - 对每个 target 组合 dest_parts = [destinationChannelName, destinationPduName, destinationSignalName]
      - 通过 get_trace_info 生成 "Channel_Pdu_Signal" 形式的 value 与 trace。
    - 产出结构类似：
      - {"ShortName": ..., "ComGwSource": {...}, "ComGwDestination": [...]}

    返回:
    - {route_type: [ComGwMappingItem, ...]}
    """
    """
    生成网关映射数据并替换目标JSON文件中嵌套的ComGwMapping标签内容

    参数:
        input_json: 输入的JSON数据
        pattern: 组合模式字符串
        target_file_path: 目标JSON文件路径
    """
    try:
        res = {}
        check_flag = False
        for route_type, route_infos in input_json.items():
            print(f"测试：{route_infos}")
            if not check_flag and route_infos:
                # 临时越用越聪明
                if route_infos[0]['source']['sourceChannelName']['value'] is None:
                    global_config.excel_exception_list.append('源通道标识符')
                if route_infos[0]['targets'][0]['destinationChannelName']['value'] is None:
                    global_config.excel_exception_list.append('目标通道标识符')
                # if route_infos[0]['source']['sourceSignalName']['value'] is None:
                #     global_config.excel_exception_list.append('信号名称')
                logging.info(global_config.excel_exception_list)
                check_flag = True
            # 第一步：生成新的映射数据
            generated_data = []

            for item in route_infos:
                source = item["source"]
                targets = item["targets"]

                # 处理源信号路径
                source_parts = [source['sourceChannelName'], source['sourcePduName'], source['sourceSignalName']]

                # 处理目标信号路径
                dest_refs = []
                for target in targets:
                    dest_parts = [target['destinationChannelName'], target['destinationPduName'],
                                  target['destinationSignalName']]
                    dest_refs.append({
                        "ShortName": get_trace_info(dest_parts, excel_path, sheet_name),
                        "ComGwSignal": {
                            "ComGwSignalRef": get_trace_info(dest_parts, excel_path, sheet_name),
                        }
                    })

                generated_data.append({
                    "ShortName": get_trace_info(source_parts, excel_path, sheet_name),
                    "ComGwSource": {
                        "ComGwSignal": {
                            "ComGwSignalRef": get_trace_info(source_parts, excel_path, sheet_name),

                        }
                    },
                    "ComGwDestination": dest_refs
                })
            # logging.info(generated_data)
            res[route_type] = generated_data
        return res
    except Exception as e:
        logging.info(traceback.format_stack())
        logging.error(f"Exception occurred: {e}")
        raise e

def refresh_route_type(current_row, pdur_result, result, signal_col_index):
    """在扫描路由表时更新“当前路由类型分组”。

    背景：
    - 路由表中常用“仅 signal 列有值”的行作为分组标题行，标识后续若干行属于同一种 route_type。

    功能逻辑：
    - 读取 signal 列值作为 route_type 文本，并做规范化（空格/大小写/CAN/CAN-FD 归一）。
    - 若不在 support_route_type 列表中，则调用 try_find_route_type_by_ai 做语义归类兜底。
    - 确保 result/pdur_result 中存在该 route_type 的列表容器。

    返回:
    - current_route_type: 标准化后的 route_type。
    """
    current_route_type = current_row.iloc[signal_col_index - 1]
    if current_route_type == "LLCE路由":
        current_route_type = "LLCE"
    elif current_route_type == "E2E报文重组路由":
        current_route_type = "E2E_Message_Rebuild_Route"
    current_route_type = current_route_type.strip(' ').replace(' ', '_').replace('CAN/CAN-FD', 'CAN')

    if current_route_type not in support_route_type:
        current_route_type = try_find_route_type_by_ai(current_route_type)

    if current_route_type not in pdur_result:
        pdur_result[current_route_type] = []
    if current_route_type not in result:
        result[current_route_type] = []
    return current_route_type


def try_find_route_type_by_ai(route_type):
    """当 route_type 不在已支持列表时，用 LLM 做语义匹配归类。

    功能逻辑：
    - 使用 QueryRouteTypeNamePrompt，让 LLM 在预定义 route_type 列表中选择最匹配的一项。
    - 若 LLM 返回值仍不在支持列表中，则回退为 Default。

    返回:
    - output_route_type: 归类后的 route_type 字符串。
    """
    try:
        system_prompt = prompts_data.get("QueryRouteTypeNamePrompt")
        query = f"""请帮我找到与以下字符语义匹配的路由类型：{route_type}"""
        res, spend_token = call_model(query.replace("{", "{{").replace("}", "}}"),
                                             system_prompt.replace("{", "{{").replace("}", "}}"))
        global_config.llm_spend_token["excel_parse"] += spend_token
        res_json = res.replace("{{", "{").replace("}}", "}")
        output_route_type = extract_json(res_json).get("route_type", "")
        if output_route_type not in support_route_type:
            logging.info(f"AI found matching route type {output_route_type}, not in supported route types list, using default: Default")
            output_route_type = 'Default'
        return output_route_type
    except Exception as e:
        logging.error(traceback.format_exc())
        return "Default"


def scan_routing_table(excel_path, config_dict, sheet_name):
    """按“结构元数据配置”扫描路由表内容，抽取逐行路由记录。

    输入:
    - excel_path: 路由表所在 Excel。
    - config_dict: 来自 logic_LLM.parse_can_excel 的配置，提供关键列坐标/起始行等。
    - sheet_name: 路由表 sheet。

    功能逻辑：
    - 校验 sheet 是否存在。
    - 根据 config_dict 构建 col_mapping（字段→列字母）。
    - 用 pandas 读取整张 sheet（避免 usecols out-of-bounds），再按 max_col 截断。
    - 从 dataContentStartRow 开始逐行遍历：
      - 空行：重置 current_route_type。
      - 仅 signal 列有值：视为“路由类型标题行”，调用 refresh_route_type。
      - 普通数据行：调用 get_gw_mapping_info 抽取一条路由记录（含 trace）。
    - 将 routingType.value == 0 的记录分流到 pdur_result（其语义待进一步确认）。

    返回:
    - (result, pdur_result)
      - result/pdur_result 形如 {route_type: [row_data, ...]}
    """
    """
    解析Excel路由表并生成结构化数据
    """
    # 验证 sheet_name 是否有效
    if not sheet_name or not sheet_name.strip():
        logging.error(f"无效的工作表名称: '{sheet_name}'")
        return {'Default': []}, {'Default': []}
    
    # 初始化数据
    wb = wbparser.parse_and_get_single_excel(excel_path)
    if not wb:
        logging.error(f"无法加载Excel文件: {excel_path}")
        return {'Default': []}, {'Default': []}
    
    if sheet_name not in wb.sheetnames:
        logging.error(f"工作表 '{sheet_name}' 不存在，可用的工作表: {wb.sheetnames}")
        return {'Default': []}, {'Default': []}
    
    sheet = wb[sheet_name]
    result = {'Default': []}
    pdur_result = {'Default': []}

    # 提取配置参数
    start_row = config_dict.get("dataContentStartRow", 6)
    channel_name_row = config_dict.get("channelNameInfoRow", 4)
    channel_cells = sheet[channel_name_row]
    max_row = config_dict.get("max_row_count", sheet.max_row)
    max_col = config_dict.get("max_column_count", sheet.max_column)

    # 生成列映射
    col_mapping = build_column_mapping(config_dict)
    # openpyxl 的 column 是 1-based（A=1），但 pandas.read_excel(usecols=range(max_col))
    # 只会读前 max_col 列；如果配置里给的列字母超出了 max_col，就会在后续 iloc 取值时越界。
    col_letter_index = {
        value: sheet[f"{value}{channel_name_row}"].column
        for key, value in col_mapping.items()
        if value
    }

    signal_letter = col_mapping.get("sourceSignalName")
    signal_col_index = int(col_letter_index.get(signal_letter) or 0)

    # 将需要访问的列数提升到“配置里最大列”，避免 iloc 越界
    max_needed_col = max([0, max_col] + list(col_letter_index.values()))
    max_col = max_col if max_col >= max_needed_col else max_needed_col
    # 遍历数据行
    current_route_type = 'Default'
    # 读取Excel数据
    # pandas 在某些工作表上会认为“有效列数”比 openpyxl 的 sheet.max_column 更小，
    # 这时 usecols=range(max_col) 可能触发 ParserError: usecols out-of-bounds。
    # 先不限制 usecols 读取整表，再用 iloc 截断到需要的列数。
    all_data = pd.read_excel(
        excel_path,
        sheet_name=sheet_name,
        nrows=max_row,
        header=None,
    )
    if max_col and all_data.shape[1] > max_col:
        all_data = all_data.iloc[:, :max_col]

    for row_idx in range(start_row - 1, len(all_data)):
        current_row = all_data.iloc[row_idx]

        # 跳过空行
        if is_empty_row(current_row):
            logging.info(f"Row {row_idx + 1} is empty")
            current_route_type = 'Default'
            continue

        # 更新路由类型
        if is_signal_only_row(current_row, signal_col_index):
            current_route_type = refresh_route_type(current_row, pdur_result, result, signal_col_index)
            continue


        row_data = get_gw_mapping_info(col_mapping, current_row, row_idx, config_dict, channel_cells, max_col, col_letter_index, excel_path, sheet_name)
        # TODO 需要确认0是signal还是message
        routing_type_info = row_data.get('routingType')
        if routing_type_info and routing_type_info.get('value') == 0:
            pdur_result[current_route_type].append(row_data)
        else:
            result[current_route_type].append(row_data)

    return result, pdur_result


def build_column_mapping(config_dict):
    """从 LLM 返回的配置中提取“字段 → 列字母”的映射。

    功能逻辑：
    - 过滤掉 startRow/channelRow/通道标识符等非列坐标字段。
    - 对形如 "B4" 的坐标，仅保留字母部分 "B"。

    返回:
    - col_mapping: {"sourceSignalName": "B", "destinationPduName": "AM", ...}
    """
    filter_keys = ['dataContentStartRow', 'channelNameInfoRow', 'letterRepresentingSourceChannelName',
                   'letterRepresentingDestinationChannelName', 'letterRepresentingBothSourceAndDestinationChannelName']
    col_mapping = {}
    for key, value in config_dict.items():
        if key in filter_keys:
            continue
        col_mapping[key] = ''.join([c for c in value if c.isalpha()]) if isinstance(value, str) and value != "None" else None
    return col_mapping


def is_empty_row(row):
    """判断当前 pandas Series 行是否为空行（全是 NaN）。"""
    return row.isna().all()


def is_signal_only_row(row, signal_col_index):
    """判断当前行是否为“路由类型标题行”。

    判定规则：
    - 除 signal_col_index 指定列外，其它列均为空（NaN 或空字符串）。
    - signal 列本身有值。

    用途：
    - 路由表常用这种行来标记一个分组的 route_type。
    """
    return all(pd.isna(row.iloc[col_idx]) or str(row.iloc[col_idx]).strip() == ""
               for col_idx in range(len(row)) if col_idx != signal_col_index - 1) and row.iloc[signal_col_index - 1]



def get_gw_mapping_info(col_mapping, row_cells, row_idx, config_dict, channel_cells, max_col, col_letter_index, excel_path, sheet_name):
    """从路由表的一行中抽取字段值，并识别源/目标通道。

    功能逻辑：
    1) 按 col_mapping 提取 sourceSignalName/sourcePduName/... 等“固定字段列”。
       - 每个字段都携带 trace：file/row/col/sheet。
       - 做 pandas 越界保护：若配置列超出实际列数，则 value=None。

    2) 在“矩阵区”扫描通道标识符：
       - config_dict["letterRepresentingSourceChannelName"] / Destination / Both
       - 在当前行中找到对应标记后，通过 channelNameInfoRow 对应的表头单元格读取真实通道名。
       - destinationChannelName 可能多个（一个 source 映射多个目标）。

    返回:
    - row_data: 一条路由记录（字段均为 {value, trace} 或列表）。
    """
    row_data = {}
    # 处理名称类字段
    row_idx = row_idx + 1
    for key, col_letter in col_mapping.items():
        if col_letter:
            col_pos = col_letter_index[col_letter] - 1
            # 这里 col_letter_index 来自 openpyxl（按工作表列号），但 pandas 读出来的列数可能更少；
            # 如果越界，说明该字段配置的列在当前 sheet 中不存在，直接记为 None。
            if col_pos < 0 or col_pos >= len(row_cells):
                value = None
            else:
                value = row_cells.iloc[col_pos]
            row_data[key] = {
                "value": None if (value is None or pd.isna(value)) else value,
                "trace": [{
                    "file": excel_path,
                    "row": row_idx,
                    "col": col_letter,
                    "sheet": sheet_name
                }]
            }

    # 查找源/目标通道
    if not row_data.get("sourceChannelName"):
        row_data["sourceChannelName"] = {"value": None}
    row_data["destinationChannelName"] = []

    source_channel_id = config_dict.get("letterRepresentingSourceChannelName", "")
    dest_channel_id = config_dict.get("letterRepresentingDestinationChannelName", "")
    both_channel_id = config_dict.get("letterRepresentingBothSourceAndDestinationChannelName", "")

    # 如果三个通道标识符都为空，跳过通道扫描
    if not (source_channel_id or dest_channel_id or both_channel_id):
        row_data["destinationChannelName"].append({"value": None})
        return row_data

    for col_idx in range(1, max_col):
        # 同上：row_cells 是 Series，必须用 iloc 按位置取值；并且要防止越界
        if col_idx - 1 >= len(row_cells):
            break
        value = row_cells.iloc[col_idx - 1]
        if pd.isna(value):
             continue
        if source_channel_id and str(value) in str(source_channel_id):
            channel_cell = channel_cells[col_idx-1]
            row_data["sourceChannelName"] = {
                "value": channel_cell.value,
                "trace": [{
                    "file": excel_path,
                    "row": row_idx,
                    "col": channel_cell.column_letter,
                    "sheet": sheet_name
                }]
            }
        elif dest_channel_id and str(value) in str(dest_channel_id):
            channel_cell = channel_cells[col_idx-1]
            row_data["destinationChannelName"].append({
                "value": channel_cell.value,
                "trace": [{
                    "file": excel_path,
                    "row": row_idx,
                    "col": channel_cell.column_letter,
                    "sheet": sheet_name
                }]
            })
        elif both_channel_id and str(value) in str(both_channel_id):
            channel_cell = channel_cells[col_idx-1]
            row_data["sourceChannelName"] = {
                "value": channel_cell.value,
                "trace": [{
                    "file": excel_path,
                    "row": row_idx,
                    "col": channel_cell.column_letter,
                    "sheet": sheet_name
                }]
            }
            row_data["destinationChannelName"].append({
                "value": channel_cell.value,
                "trace": [{
                    "file": excel_path,
                    "row": row_idx,
                    "col": channel_cell.column_letter,
                    "sheet": sheet_name
                }]
            })
    if not row_data.get("destinationChannelName"):
        row_data["destinationChannelName"].append({"value": None})
    return row_data


def transform_routing_data(input_json):
    """将“逐行路由记录”归并为“一源多目的”的结构。

    输入:
    - input_json: {route_type: [row_data, row_data, ...]}
      其中 row_data 包含 sourceChannelName/sourcePduName/sourceSignalName 与 destination* 等。

    功能逻辑：
    - 用 (sourceChannelName, sourceSignalName, sourcePduName, routingType) 作为分组 key。
    - 同一组内合并所有 destinationChannelName/destinationPduName/destinationSignalName。
    - 通过 add_target_info_to_source_groups 去重（避免重复目标）。

    输出:
    - {route_type: [ {"source": {...}, "targets": [...]}, ... ]}
    """
    res = {}
    for route_type, routes in input_json.items():
        # 预构建源信息映射，避免重复遍历
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
                    'sourcePduId': route.get("sourcePduId", {"value": None}),
                }

        source_groups = defaultdict(list)
        # 按照源信号特征分组
        for route in routes:
            # 构建 source_key，仍然以 value 作为分组依据
            source_key = (
                route.get("sourceChannelName", {}).get("value"),
                route.get("sourceSignalName", {}).get("value"),
                route.get("sourcePduName", {}).get("value"),
                route.get("routingType", {}).get("value"),
            )

            # 构建 target_info，保留完整信息
            for destinationChannelName in route["destinationChannelName"]:
                add_target_info_to_source_groups(destinationChannelName, route, source_groups, source_key)

        # 构建输出结构，保留完整信息
        output = []
        for source_key, targets in source_groups.items():
            # 使用预构建的映射获取源信息，避免重复遍历
            source_info = source_info_map.get(source_key)
            if source_info is None:
                # 这种情况理论上不应该发生，但为了安全性添加检查
                continue

            output.append({
                "source": source_info,
                "targets": targets
            })
        res[route_type] = output
    return res


def add_target_info_to_source_groups(destinationChannelName, route, source_groups, source_key):
    """向某个 source 分组中追加目标信息，并进行去重。

    去重维度：
    - destinationChannelName.value
    - destinationPduName.value
    - destinationSignalName.value

    目标结构:
    - {destinationChannelName, destinationPduName, destinationSignalName, routingType, destinationPduId, isLLCE}
    """
    for target_info in source_groups[source_key]:
        if (target_info.get("destinationChannelName", {}).get("value") == destinationChannelName.get("value")
                and target_info.get("destinationPduName", {}).get("value") == route.get("destinationPduName", {}).get("value")
                and target_info.get("destinationSignalName", {}).get("value") == route.get("destinationSignalName", {}).get("value")):
            return
    else:
        target_info = {
            "destinationChannelName": destinationChannelName,
            "destinationPduName": route.get("destinationPduName", {"value": None}),
            "destinationSignalName": route.get("destinationSignalName", {"value": None}),
            "routingType": route.get("routingType", {"value": None}),
            "destinationPduId": route.get("destinationPduId", {"value": None}),
            "isLLCE": route.get("isLLCE", {"value": None}),
        }
        source_groups[source_key].append(target_info)


def get_ComGwSignalRef_from_srsModel(json_string):
    """从 SRS 模型（JSON 字符串）中提取 ComGwSignalRef。

    功能逻辑：
    - 将输入 JSON 字符串解析为对象。
    - 取 ComGwMapping[0].ComGwSource.ComGwSignal.ComGwSignalRef。

    用途：
    - 作为工具函数在调试/验证 mapping 格式时使用。
    """
    try:
        # 解析 JSON 字符串为 Python 字典
        data = extract_json(json_string)

        # 提取 ComGwSignalRef 的值
        source_signal_ref = data["ComGwMapping"][0]["ComGwSource"]["ComGwSignal"]["ComGwSignalRef"]
        return source_signal_ref
    except Exception as e:
        logging.error(f"Exception occurred: {e}")


def get_trace_info(datas, file, sheet_name, last=False):
    """将多个字段片段组装为一个可追溯的值对象（value + trace）。

    输入 datas:
    - 通常是多个 {"value": ..., "row": ..., "col": ...} 片段，表示 Channel/Pdu/Signal 的组成部分。

    功能逻辑：
    - last=False：
      - 拼接所有非空 value，使用 '_' 连接。
      - trace 默认只保留最后一个非空片段的位置（减少 trace 冗余）。
    - last=True：
      - 只取最后一个片段作为 value 与 trace。

    返回:
    - {"value": "...", "trace": [{file,row,col,sheet}], "type": "user"}
    """
    trace_info = []
    val_info_list = []
    if last is True:
        trace_info.append({
            "file": file,
            "row": datas[-1]['row'],
            "col": datas[-1]['col'],
            "sheet": sheet_name,
        })
        val_info_list.append(datas[-1]["value"])
    else:
        for data in datas:
            if not data["value"]:
                continue
            val_info_list.append(data["value"])
            trace_info.append({
                "file": file,
                "row": data['row'],
                "col": data['col'],
                "sheet": sheet_name,
            })
        trace_info = [trace_info[-1]] if trace_info else []
    return {
        "value": "_".join(val_info_list) if last is False else val_info_list[-1],
        "trace": trace_info,
        "type": "user",
    }


def get_route_message_info(sheet, col_mapping, row_idx, route_message_info_list):
    """从 openpyxl sheet 中抽取某一行的报文级路由信息（旧/备用逻辑）。

    功能逻辑：
    - 直接按 col_mapping 的列字母读取 routingType、source/destination PDU name、PDU ID。
    - 通过 get_trace 将值与 (row,col) 打包后追加到 route_message_info_list。

    备注：
    - 当前主流程已转向 pandas 扫描 + trace 字典结构，这里更像历史保留。
    """
    route_type = sheet[f"{col_mapping['routingType']}{row_idx}"].value
    src_pdu_name = sheet[f"{col_mapping['sourcePduName']}{row_idx}"].value
    source_pdu_id = col_mapping.get('sourcePduId', '')
    if source_pdu_id:
        src_pdu_id = sheet[f"{source_pdu_id}{row_idx}"].value
    else:
        src_pdu_id = ''
    dst_pdu_name = sheet[f"{col_mapping['destinationPduName']}{row_idx}"].value
    dst_pdu_id = sheet[f"{col_mapping['destinationPduId']}{row_idx}"].value

    route_message_info_list.append({
        "route_type": get_trace(route_type, row_idx, f"{col_mapping['routingType']}{row_idx}"),
        "src_pdu_name": get_trace(src_pdu_name, row_idx, f"{col_mapping['sourcePduName']}{row_idx}"),
        "src_pdu_id": get_trace(src_pdu_id, row_idx, f"{col_mapping['sourcePduId']}{row_idx}") if src_pdu_id else '',
        "dst_pdu_name": get_trace(dst_pdu_name, row_idx, f"{col_mapping['destinationPduName']}{row_idx}"),
        "dst_pdu_id": get_trace(dst_pdu_id, row_idx, f"{col_mapping['destinationPduId']}{row_idx}"),
    })


def get_trace(value, row_idx, column_letter):
    """构造轻量 trace 结构（用于旧逻辑）。

    返回:
    - {"value": value, "row": row_idx, "col": column_letter}
    """
    return {
        "value": value,
        "row": row_idx,
        "col": column_letter,
    }


# # 使用示例
if __name__ == "__main__":
    # excel_file = "gateway_routing.xlsx"
    # parsed_data = parse_routing_table(excel_file, config)
    #
    # # 打印前3行结果示例
    # for i, row in enumerate(parsed_data[:3], start=config["表内容开始行"]):
    #     print(f"第{i}行:", row)
    # with open("input_json.json", "r", encoding="utf-8") as f:
    #     data = json.load(f)
    from AutoSAR_Agent.tools.OMV_tools.config import global_cfg
    excel_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\A02-Y_纯电AB平台_CMX_CCU_V29.2(G3 G.0-1)-20251201_Result.xlsx"
    knowledge_json_path = r"D:\KoTEI_CODE\Agent_Autosar_Backend\AutoSAR_Agent\tools\OMV_tools\config\knowledge.json"
    knowledge_json = json.load(open(knowledge_json_path, "r", encoding="utf-8"))
    generate_and_write_gw_mapping(knowledge_json, excel_path, "RT1_Tx_RollBack_CANFD")
    # excel_path = 'D:\\work\\git repositories\\Autosar\\autosar-agent\\Agent\\output_file\\TC_AGENT_EXCEL_GW_001.xlsx'
    # config_dict = {'dataContentStartRow': 7, 'channelNameInfoRow': 4, 'letterRepresentingSourceChannelName': 'S或S1', 'letterRepresentingDestinationChannelName': 'D或D1或Des', 'letterRepresentingBothSourceAndDestinationChannelName': 'SD或S1D1或Des或', 'sourceSignalName': 'B7', 'sourcePduName': 'C7', 'sourcePduId': 'F7', 'destinationSignalName': 'AI7', 'destinationPduName': 'AU7', 'destinationPduId': 'AK7', 'routingType': 'N7'}
    # sheet_name = 'GWRoutingChart'
    # scan_routing_table(excel_path, config_dict, sheet_name)
