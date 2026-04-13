# -*- coding: utf-8 -*-
"""
@File    : extracting_arxml_preh_add.py
@Date    : 2026--02-3 09:42
@Desc    : 解析arxml文件，从中提取另一路can的message信息
@Author  : xjx
"""
import os
import re
import json
import xmltodict
import logging


class ExtractingARXMLPREHADD(object):
    # 定义关键字列表
    communication_keywords = [
        "CAN-FRAME", "NM-CONFIG", "N-PDU", "I-SIGNAL", "I-SIGNAL-GROUP",
        "I-SIGNAL-I-PDU-GROUP", "GATEWAY", "PDUR-I-PDU-GROUP", "CAN-TP-CONFIG"
    ]

    ecu_extract_keywords = [
        "SYSTEM"
    ]

    communication_cluster_keywords = [
        "ETHERNET-CLUSTER", "CAN-CLUSTER"
    ]

    def __init__(self, arxml_path):
        self.arxml_path = arxml_path
        self.arxml_data = self.init()
        self.data = {}
        self.mid_data = {}
        self.i_signal_ipdu_package = {}
        self.i_signal_package = {}
        self.triggering_package = {}
        self.can_frame_package = {}
        self.ecu_instance_package = {}
        self.i_signal_group_package = {}
        # self.ecu_instance = {}
        self.extracting_all()
        self.byte_order = ""

    def init(self):
        """
        初始化方法
        @return:
        """
        directory = os.path.dirname(self.arxml_path)  # 提取目录部分
        file_name, extension = os.path.splitext(os.path.basename(self.arxml_path))  # 提取文件名和扩展名

        # 修改文件名，在最后一个 `.` 前添加 `_bak`
        new_file_name = file_name + "_bak" + extension
        new_file_path = os.path.join(directory, new_file_name)

        try:
            with open(self.arxml_path, 'r', encoding='utf-8') as infile, open(new_file_path, 'w',encoding='utf-8') as outfile:
                line_number = 1
                for line in infile:
                    line_number_str = f"*{line_number:06}"
                    # 替换所有的 `</` 左侧非空格的标签
                    line = re.sub(r'(\S)(</)', rf'\1{line_number_str}\2', line)
                    outfile.write(line)
                    line_number += 1

        except Exception as e:
            logging.warning(f"发生错误：{e}")


        with open(new_file_path, 'r', encoding="utf-8") as f:
            arxml_content = f.read()
            string_data = xmltodict.parse(arxml_content)
        return string_data


    def extracting_all(self):
        """
        @return:
        """
        self.find_target_packages()
        self.extracting_can()
        # self.get_ecu_instance_name()
        self.extracting_can_physical_channel()


    def dict_to_list(self, data):
        """
        将字典或单个元素转换为列表形式。
        :param data: 输入数据，可能是字典、列表或 None
        :return: 返回列表
        """
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            return []

    def find_target_packages(self):
        """
        公共方法：递归查找目标包（I-SIGNAL-I-PDU、I-SIGNAL等）。
        """
        # 获取顶层 AR-PACKAGES
        top_level_packages = self.dict_to_list(self.arxml_data['AUTOSAR']['AR-PACKAGES']['AR-PACKAGE'])
        for package in top_level_packages:
            self.process_package_recursive(package)


    def process_package_recursive(self, ar_package):
        """
        递归处理 AR-PACKAGE，提取目标包。
        :param ar_package: 当前处理的 AR-PACKAGE
        """
        # 获取当前 AR-PACKAGE 中的 ELEMENTS，并转换为列表形式
        elements = self.dict_to_list(ar_package.get('ELEMENTS', {}))

        # 遍历 ELEMENTS，查找 I-SIGNAL-I-PDU 和 I-SIGNAL
        for element in elements:
            if "I-SIGNAL-I-PDU" in element:
                self.merge_with_lists(self.i_signal_ipdu_package, ar_package)
            if "I-SIGNAL" in element:
                self.merge_with_lists(self.i_signal_package, ar_package)
            if "CAN-CLUSTER" in element:
                self.triggering_package.update(ar_package)
            if "CAN-FRAME" in element:
                self.can_frame_package.update(ar_package)
            if "ECU-INSTANCE" in element:
                self.ecu_instance_package.update(ar_package)
            if "I-SIGNAL-GROUP" in element:
                self.merge_with_lists(self.i_signal_group_package, ar_package)

        # 递归处理子 AR-PACKAGES
        sub_packages = self.dict_to_list(ar_package.get('AR-PACKAGES', {}).get('AR-PACKAGE', []))
        for sub_package in sub_packages:
            self.process_package_recursive(sub_package)



    def extracting_can(self):
        tag = "CAN-COMMUNICATION-CONTROLLER"
        self.data['can'] = self.find_tag_content(self.ecu_instance_package, tag)

    def extracting_can_physical_channel(self):
        tag = "CAN-PHYSICAL-CHANNEL"
        can_physical_channel = self.find_tag_content(self.triggering_package, tag)
        self.data['can_physical_channels'] = can_physical_channel

    # def get_ecu_instance_name(self):
    #     ecu_instances = self.find_tag_content(self.ecu_instance_package, 'ECU-INSTANCE')
    #     if ecu_instances:
    #         self.ecu_instance = ecu_instances[0]['SHORT-NAME']

    def merge_with_lists(self, dict1, dict2):
        """
        合并两个字典，同时处理包含列表或字典的值，避免覆盖。
        """
        for key, value in dict2.items():
            if key in dict1:
                # 如果键在两个字典中都存在
                if isinstance(dict1[key], dict) and isinstance(value, dict):
                    # 如果两个值都是字典，转换为列表并合并
                    dict1[key] = [dict1[key], value]
                elif isinstance(dict1[key], list) and isinstance(value, list):
                    # 如果值是列表，合并两个列表
                    dict1[key].extend(value)
                elif isinstance(dict1[key], dict) and isinstance(value, list):
                    # 如果 dict1[key] 是字典，value 是列表，将字典加入到列表中
                    dict1[key] = [dict1[key]] + value
                elif isinstance(dict1[key], list) and isinstance(value, dict):
                    # 如果 dict1[key] 是列表，value 是字典，将字典加入到列表中
                    dict1[key].append(value)
                else:
                    # 如果值类型不同，直接转换为列表并合并
                    dict1[key] = [dict1[key], value]
            else:
                # 如果键只在 dict2 中存在，直接添加
                dict1[key] = value
        return dict1

    def find_tag_content(self, data, target_tag):
        """
        在JSON数据中查找指定标签下的所有内容。

        参数:
            data (dict or list): JSON数据，可能是字典或列表。
            target_tag (str): 目标标签名称。

        返回:
            list: 包含目标标签下所有内容的列表。
        """
        results = []

        # 如果是字典，遍历键值对
        if isinstance(data, dict):
            for key, value in data.items():
                if key == target_tag:
                    # 如果键匹配目标标签，添加内容到结果列表
                    if isinstance(value, list):
                        for val in value:
                            results.append(val)
                    else:
                        results.append(value)
                else:
                    # 递归查找子结构
                    results.extend(self.find_tag_content(value, target_tag))

        # 如果是列表，遍历每个元素
        elif isinstance(data, list):
            for item in data:
                results.extend(self.find_tag_content(item, target_tag))

        return results

    def parse_xml(self):
        # 遍历所有物理 CAN 通道
        self.mid_data['msg'] = []
        for physical_channel in self.data['can_physical_channels']:
            # 从当前物理通道中提取 SHORT-NAME 数据
            node_name = physical_channel['SHORT-NAME'].split("*")[0]

            # 提取所有 CAN-FRAME 信息
            can_frame = self.find_tag_content(self.can_frame_package, "CAN-FRAME")
            self.extract_can_frame(can_frame)

            # 提取所有 CAN-FRAME-TRIGGERING 信息
            can_frame_triggerings = self.find_tag_content(self.triggering_package, "CAN-FRAME-TRIGGERING")
            self.extract_can_frame_triggering(can_frame_triggerings)

            # 提取所有 PDU-TRIGGERING 信息
            pdu_triggerings = self.find_tag_content(self.triggering_package, "PDU-TRIGGERING")
            self.extract_pdu_triggering(pdu_triggerings)

            # 提取 FRAME-PORT 信息
            frame_ports = self.find_tag_content(self.ecu_instance_package, "FRAME-PORT")
            self.extract_frame_port(frame_ports)

            # 提取 I-SIGNAL-TRIGGERING 信息
            i_signal_triggerings = self.find_tag_content(self.triggering_package, "I-SIGNAL-TRIGGERING")
            self.extract_i_signal_triggering(i_signal_triggerings)

            # 提取 I-SIGNAL-I-PDU 信息
            i_signal_i_pdus = self.find_tag_content(self.i_signal_ipdu_package, "I-SIGNAL-I-PDU")
            self.extract_i_signal_i_pdu(i_signal_i_pdus)

            # 解析 I-SIGNAL-TO-I-PDU-MAPPING 信息
            self.extract_i_signal_to_i_pdu_mapping(i_signal_i_pdus)

            # 提取 I-SIGNAL 信息
            i_signals = self.find_tag_content(self.i_signal_package, "I-SIGNAL")
            self.extract_i_signal(i_signals)

            # 为每条消息添加 node_name
            for msg in self.mid_data['msg']:
                msg["node_name"] = node_name



    def extract_can_frame(self, can_frame_data):
        """
            提取 CAN 帧的数据，并直接存储到全局 self.mid_data['msg'] 中
        """
        for can_frame in can_frame_data:
            # 提取 CAN-FRAME 的 SHORT-NAME
            frame_name = can_frame["SHORT-NAME"]

            # 从当前 CAN 帧中提取 PDU-TO-FRAME-MAPPING 数据
            pdu_to_frame_mapping = self.find_tag_content(can_frame, "PDU-TO-FRAME-MAPPING")

            # 如果没有 PDU-TO-FRAME-MAPPING 数据，跳过
            if not pdu_to_frame_mapping:
                continue

            # 提取 PDU 的引用名称
            pdu_ref = pdu_to_frame_mapping[0]['PDU-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 提取 CAN 帧的关键信息
            frame_length = int(can_frame['FRAME-LENGTH'].split("*")[0])
            frame_length_row = can_frame['FRAME-LENGTH'].split("*")[1]
            start_position = pdu_to_frame_mapping[0]['START-POSITION']
            msg_type = ""

            # 将数据直接追加到全局变量中
            self.mid_data['msg'].append({
                "name": frame_name.split("*")[0],
                "name_row": frame_name.split("*")[1],
                "frame_length": frame_length,
                "frame_length_row": frame_length_row,
                "start_position": start_position.split("*")[0],
                "start_position_row": start_position.split("*")[1],
                "msg_type": msg_type,
                "pdu_ref": pdu_ref
            })

    def extract_can_frame_triggering(self, can_frame_triggerings):
        """
        遍历所有 CAN-FRAME-TRIGGERING 信息，并将匹配的触发信息更新到 self.mid_data['msg'] 中
        """
        # 遍历所有 CAN-FRAME-TRIGGERING 信息
        for can_frame_triggering in can_frame_triggerings:
            # 提取 CAN-FRAME-TRIGGERING 的 FRAME-REF 中的 SHORT-NAME
            msg_name = can_frame_triggering['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                # 如果当前消息的名称与 CAN-FRAME-TRIGGERING 的名称一致
                if msg['name'] == msg_name:
                    # 提取 CAN-FRAME-TRIGGERING 中的其他信息
                    identifier = can_frame_triggering['IDENTIFIER']
                    is_extended_frame = can_frame_triggering['CAN-ADDRESSING-MODE']
                    is_fd = can_frame_triggering['CAN-FRAME-TX-BEHAVIOR']

                    # 提取 FRAME-PORT-REF
                    frame_port_ref = (
                        can_frame_triggering.get("FRAME-PORT-REFS", {})
                        .get("FRAME-PORT-REF", {})
                    )
                    frame_port_ref = frame_port_ref["#text"].rsplit("/", 1)[1].split("*")[0]

                    # 提取 PDU-TRIGGERING-REF 信息
                    pdu_triggering_ref = (
                        can_frame_triggering.get("PDU-TRIGGERINGS", {})
                        .get("PDU-TRIGGERING-REF-CONDITIONAL", {})
                        .get("PDU-TRIGGERING-REF", {})
                    )
                    #并不是所有的 CAN-FRAME-TRIGGERING 都有 PDU-TRIGGERING-REF 信息
                    pdu_triggering_ref = pdu_triggering_ref["#text"].rsplit("/", 1)[1].split("*")[0] if pdu_triggering_ref else ""

                    # 更新 msg 中的信息
                    msg.update({
                        "identifier": identifier.split("*")[0],
                        "identifier_row": identifier.split("*")[1],
                        "is_extended_frame": "true" if is_extended_frame.split("*")[0] == "STANDARD" else "false",
                        "is_extended_frame_row": is_extended_frame.split("*")[1],
                        "is_fd": "true" if is_fd.split("*")[0] == "CAN-FD" else "false",
                        "is_fd_row": is_fd.split("*")[1],
                        "frame_port_ref": frame_port_ref,
                        "pdu_triggering_ref": pdu_triggering_ref
                    })

    def extract_frame_port(self, frame_ports):
        # 遍历所有 FRAME-PORT 信息
        for frame_port in frame_ports:
            # 提取 FRAME-PORT 中的 SHORT-NAME
            frame_port_name = frame_port['SHORT-NAME'].split("*")[0]
            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                if msg['frame_port_ref'] == frame_port_name:
                    # 提取 COMMUNICATION-DIRECTION 信息
                    direction = "tx" if frame_port.get('COMMUNICATION-DIRECTION', {}).split("*")[0] == "OUT" else "rx"

                    # 更新 msg 中的信息
                    msg.update({
                        "direction": direction
                    })

    def extract_pdu_triggering(self, pdu_triggerings):
        """
           提取所有 PDU-TRIGGERING 信息，并将匹配的 I-SIGNAL-TRIGGERING-REF 更新到 self.mid_data['msg'] 中
        """
        # 遍历所有 PDU-TRIGGERING 信息
        for pdu_triggering in pdu_triggerings:
            # 提取 PDU-TRIGGERING 中的 SHORT-NAME
            msg_name = pdu_triggering['SHORT-NAME'].split("*")[0]

            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                # 如果当前消息的名称与 PDU-TRIGGERING 的名称一致
                if msg['pdu_triggering_ref'] == msg_name:
                    # 提取所有 I-SIGNAL-TRIGGERING-REF 信息
                    i_signal_triggerings = self.dict_to_list(
                        pdu_triggering.get('I-SIGNAL-TRIGGERINGS', {}).get('I-SIGNAL-TRIGGERING-REF-CONDITIONAL', [])
                    )
                    # 并不是所有的PDU-TRIGGERING 都有 I-SIGNAL-TRIGGERING-REF 信息
                    # 创建一个列表存储所有 I-SIGNAL-TRIGGERING-REF 的引用，调整为字典结构
                    i_signal_triggering_refs = [
                        {"i_signal_triggering_ref": triggering_ref.get('I-SIGNAL-TRIGGERING-REF', {}).get('#text').rsplit("/", 1)[1].split("*")[0]}
                        for triggering_ref in i_signal_triggerings
                    ] if i_signal_triggerings else ""

                    # 更新 msg 中的信息
                    msg.update({
                        "i_signal_triggering_refs": i_signal_triggering_refs
                    })

    def extract_i_signal_triggering(self, i_signal_triggerings):
        """
           遍历所有 I-SIGNAL-TRIGGERING 信息，并将匹配的信息更新到 self.mid_data['msg'] 中。
        """
        # 遍历所有 I-SIGNAL-TRIGGERING 信息
        for i_signal_triggering in i_signal_triggerings:
            # 提取 I-SIGNAL-TRIGGERING 的 SHORT-NAME
            triggering_name = i_signal_triggering['SHORT-NAME'].split("*")[0]

            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                if not msg.get("i_signal_triggering_refs"):
                    continue
                for sig_ref in msg.get("i_signal_triggering_refs"):
                    # 检查 triggering_name 是否等于 当前 msg 中的 i_signal_triggering_refs
                    if sig_ref.get("i_signal_triggering_ref") == triggering_name:
                        # 提取 I-SIGNAL-REF 信息
                        i_signal_ref = i_signal_triggering.get('I-SIGNAL-REF', {})
                        if i_signal_ref:
                            i_signal_ref = i_signal_ref.get('#text', '').rsplit("/", 1)[1]
                            # 更新 sig_ref 中的信息
                            sig_ref["i_signal_ref"] = i_signal_ref.split("*")[0]
                            sig_ref["i_signal_ref_row"] = i_signal_ref.split("*")[1]
                        else:
                            i_signal_ref = ""
                            # 更新 sig_ref 中的信息
                            sig_ref["i_signal_ref"] = i_signal_ref
                            sig_ref["i_signal_ref_row"] = ""


    def extract_i_signal_i_pdu(self, i_signal_i_pdus):
        """
           遍历 I-SIGNAL-I-PDU 信息，提取相关字段并更新到 self.mid_data['msg'] 中。
        """
        # 遍历所有 I-SIGNAL-I-PDU 信息
        for i_signal_i_pdu in i_signal_i_pdus:
            # 提取 I-SIGNAL-I-PDU 的 SHORT-NAME 和 I-PDU-TIMING-SPECIFICATIONS
            pdu_name = i_signal_i_pdu["SHORT-NAME"].split("*")[0]

            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                # 检查 pdu_ref 是否与当前 I-SIGNAL-I-PDU 的 SHORT-NAME 匹配
                if msg.get("pdu_ref") == pdu_name:
                    timing_specifications = i_signal_i_pdu.get("I-PDU-TIMING-SPECIFICATIONS", {}).get("I-PDU-TIMING", {})

                    # 提取 TRANSMISSION-MODE-TRUE-TIMING -> CYCLIC-TIMING -> TIME-PERIOD -> VALUE
                    time_period_value = timing_specifications.get("TRANSMISSION-MODE-DECLARATION", {}).get(
                        "TRANSMISSION-MODE-TRUE-TIMING", {}
                    ).get("CYCLIC-TIMING", {}).get("TIME-PERIOD", {}).get("VALUE", "")

                    # 更新 msg 中的 cycle_time
                    msg.update({
                        "cycle_time": float(time_period_value.split("*")[0]) if time_period_value else 0,
                        "cycle_time_row": time_period_value.split("*")[1] if time_period_value else ""
                    })

    def extract_i_signal_to_i_pdu_mapping(self, i_signal_i_pdus):
        # 遍历所有 I-SIGNAL-I-PDU 信息
        for i_signal_i_pdu in i_signal_i_pdus:
            # 提取 I-SIGNAL-I-PDU 的 SHORT-NAME
            pdu_name = i_signal_i_pdu["SHORT-NAME"].split("*")[0]

            # 遍历 self.mid_data['msg'] 中的每个消息
            for msg in self.mid_data['msg']:
                # 检查 pdu_ref 是否与当前 I-SIGNAL-I-PDU 的 SHORT-NAME 匹配,确保提取到的信息都是有效的
                if msg.get("pdu_ref") == pdu_name:
                    # 提取所有 I-SIGNAL-TO-I-PDU-MAPPING 信息
                    i_signal_to_i_pdu_mappings = self.find_tag_content(i_signal_i_pdu, "I-SIGNAL-TO-I-PDU-MAPPING")
                    # 遍历所有的 I-SIGNAL-TO-I-PDU-MAPPING 信息
                    for mapping in i_signal_to_i_pdu_mappings:
                        # 提取 I-SIGNAL-TO-I-PDU-MAPPING 中 I-SIGNAL-REF 信息
                        i_signal_ref = mapping.get("I-SIGNAL-REF", {})
                        # 如果 I-SIGNAL-REF 信息存在
                        if i_signal_ref:
                            i_signal_ref = i_signal_ref.get("#text", "").rsplit("/", 1)[1].split("*")[0]
                            if not msg.get("i_signal_triggering_refs"):
                                continue
                            for sig_ref in msg.get("i_signal_triggering_refs"):
                                if sig_ref.get("i_signal_ref") == i_signal_ref:
                                    # 提取 I-SIGNAL-TO-I-PDU-MAPPING 中 PACKING-BYTE-ORDER 信息
                                    packing_byte_order = mapping.get("PACKING-BYTE-ORDER", "")
                                    # 提取 I-SIGNAL-TO-I-PDU-MAPPING 中 START-POSITION 信息
                                    start_position = mapping.get("START-POSITION", "")
                                    # 更新 sig_ref 中的 PACKING-BYTE-ORDER 和 START-POSITION
                                    sig_ref.update({
                                        "packing_byte_order": "BIG_ENDIAN" if packing_byte_order.split("*")[0] == "MOST-SIGNIFICANT-BYTE-FIRST" else "LITTLE_ENDIAN",
                                        "packing_byte_order_row": packing_byte_order.split("*")[1],
                                        "start_position": start_position.split("*")[0],
                                        "start_position_row": start_position.split("*")[1],
                                    })

    def extract_i_signal(self, i_signals):
        # 遍历所有 I-SIGNAL 信息
        for i_signal in i_signals:
            # 提取 I-SIGNAL 的 SHORT-NAME
            i_signal_name = i_signal["SHORT-NAME"].split("*")[0]
            for msg in self.mid_data['msg']:
                if not msg.get("i_signal_triggering_refs"):
                    continue
                for sig_ref in msg.get("i_signal_triggering_refs"):
                    if sig_ref.get("i_signal_ref") == i_signal_name:
                        # 提取 I-SIGNAL 中 INIT-VALUE 信息
                        init_value = self.extract_init_value(i_signal)
                        # 提取 I-SIGNAL 中 LENGTH 信息
                        length = i_signal.get("LENGTH")
                        # 更新 sig_ref 中的 PACKING-BYTE-ORDER 和 START-POSITION
                        sig_ref.update({
                            "init_value": int(init_value.split("*")[0]),
                            "init_value_row": init_value.split("*")[1],
                            "length": length.split("*")[0],
                            "length_row": length.split("*")[1],
                        })

    def extract_init_value(self, i_signal):
        """
        提取I-SIGNAL中的初始值（INIT-VALUE），支持NUMERICAL-VALUE-SPECIFICATION和ARRAY-VALUE-SPECIFICATION两种格式。
        """
        init_value_data = i_signal.get("INIT-VALUE")

        if not init_value_data:
            return 0  # 默认值，如果没有INIT-VALUE

        # 处理NUMERICAL-VALUE-SPECIFICATION格式
        if "NUMERICAL-VALUE-SPECIFICATION" in init_value_data:
            return init_value_data["NUMERICAL-VALUE-SPECIFICATION"]["VALUE"]

        # 处理ARRAY-VALUE-SPECIFICATION格式
        elif "ARRAY-VALUE-SPECIFICATION" in init_value_data:
            values = init_value_data["ARRAY-VALUE-SPECIFICATION"]["ELEMENTS"]["NUMERICAL-VALUE-SPECIFICATION"]
            # 提取 NUMERICAL-VALUE-SPECIFICATION 中的VALUE
            first_value= values[0]  # 取第一个值
            if isinstance(first_value, dict):
                return first_value["VALUE"]

        # 如果没有匹配的格式，返回默认值
        return 0

    def extracting_can_msg(self):
        """
        将所有 self.mid_data 中 msg 信息按照 node_name 和 tx/rx 分类存储到 self.data 中
        """
        # 解析 XML 文件，生成中间数据 self.mid_data
        self.parse_xml()

        # 初始化 self.data 结构
        self.data["msg"] = {}
        # 遍历 self.mid_data 中的消息
        for msg in self.mid_data.get("msg", []):
            # 提取 node_name 和 direction
            node_name = msg.get("node_name", "Unknown")  # 缺失时默认为 "Unknown"
            direction = msg.get("direction", "").lower()  # 转换为小写（tx 或 rx）

            # 初始化 node_name 的分类结构
            if node_name not in self.data["msg"]:
                self.data["msg"][node_name] = {"TX": [], "RX": []}

            msg_type = "Normal"
            if "diag" in msg.get("name").lower():
                if "rs" in msg.get("name").lower():
                    msg_type = "DiagResponse"
                else:
                    msg_type = "DiagRequest"

            # 构建消息基础结构
            message_data = {
                "msg_name": msg.get("name"),
                "msg_name_row": msg.get("name_row"),
                "msg_id": msg.get("identifier"),
                "msg_id_row": msg.get("identifier_row"),
                "msg_length": msg.get("frame_length"),
                "msg_length_row": msg.get("frame_length_row"),
                "is_extended_frame": msg.get("is_extended_frame"),
                "is_extended_frame_row": msg.get("is_extended_frame_row"),
                "is_fd": msg.get("is_fd"),
                "is_fd_row": msg.get("is_fd_row"),
                "send_type": "",  # 示例中没有对应字段，保持为空
                "signals": [],  # 初始化信号列表
                "cycle_time": msg.get("cycle_time",0),
                "cycle_time_row": msg.get("cycle_time_row", ""),
                "attribute": msg_type,
            }

            # 遍历信号数据
            i_signal_triggering_refs = msg.get("i_signal_triggering_refs", [])
            for signal in i_signal_triggering_refs:
                if not signal["i_signal_ref"]:
                    continue
                # 构建信号结构
                signal_data = {
                    "ShortName": signal.get("i_signal_ref"),  # 信号名称
                    "ShortName_row": signal.get("i_signal_ref_row"),
                    "BitPosition": signal.get("start_position"),
                    "BitPosition_row": signal.get("start_position_row"),
                    "BitSize": signal.get("length"),
                    "BitSize_row": signal.get("length_row"),
                    "SignalInitValue": signal.get("init_value"),
                    "SignalInitValue_row": signal.get("init_value_row"),
                    "cycle_time": 0,  # 示例中没有对应字段，默认为 0
                    "byte_order": signal.get("packing_byte_order")
                }
                # 添加信号到消息中
                message_data["signals"].append(signal_data)

            # 根据 direction 分类存储到 TX 或 RX
            if direction == "tx":
                self.data["msg"][node_name]["TX"].append(message_data)
            elif direction == "rx":
                self.data["msg"][node_name]["RX"].append(message_data)

        # 在最后一步，循环遍历 self.data['msg']，为每个 `_row` 添加对应的 `_src`
        # 遍历 self.data['msg'] 的顶层结构，node_name 是节点名称，directions 是对应的 TX 和 RX 消息
        for node_name, directions in self.data["msg"].items():
            # 遍历每个节点的消息方向（TX 和 RX）
            for direction, messages in directions.items():
                # 遍历当前方向（TX 或 RX）下的所有消息
                for message in messages:
                    # 遍历消息中的所有字段
                    for key in list(message.keys()):  # 使用 list 防止字典大小改变引发的问题
                        # 检查是否存在以 "_row" 结尾的字段
                        row_key = f"{key}_row"
                        if row_key in message:
                            # 动态生成 `_src` 字段名
                            src_key = f"{key}_src"
                            # 赋值为来源路径
                            message[src_key] = self.arxml_path

                    # 遍历信号中的所有字段
                    for signal in message["signals"]:
                        for key in list(signal.keys()):
                            row_key = f"{key}_row"
                            if row_key in signal:
                                # 动态生成 `_src` 字段名
                                src_key = f"{key}_src"
                                # 赋值为来源路径
                                signal[src_key] = self.arxml_path

        return self.data['msg']

if __name__ == '__main__':
    parser = ExtractingARXMLPREHADD(
        r"E:\AIAUTOSAR\demand\KOTEI\ECU Extract & Message Catalogue\SWCM_STAR_35_2025_05a0_d_Ecu_Details_Extract_2025_05a0_AR2011.arxml")

    # 解析 ARXML 文件并提取数据到 mid_data
    data = parser.extracting_can_msg()

    # 指定 JSON 文件保存路径
    output_path = r"E:\AIAUTOSAR\data_output.json"

    # 将 data 输出到 JSON 文件
    with open(output_path, "w", encoding="utf-8") as json_file:
        # 使用 json.dump 格式化数据并写入文件
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    pass
