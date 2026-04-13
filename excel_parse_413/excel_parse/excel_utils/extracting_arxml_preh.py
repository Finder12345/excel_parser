# -*- coding: utf-8 -*-
"""
@File    : extracting_arxml.py
@Date    : 2025--03-25 09:42
@Desc    : 解析arxml文件，从中提取can的message信息
@Author  : lei
"""
import copy
import logging
import os
import re
import json as ujson
import time
import xmltodict
from .global_cfg import global_config
from .extracting_arxml_preh_add import ExtractingARXMLPREHADD
from .metadata_to_front import replace_trace_with_id



def parse_arxml_file_by_structure(db_path):
    """
    判断 ARXML 文件的嵌套类型。

    参数:
        db_path (str): ARXML 文件路径。
    返回:
         parser: 解析器对象，根据嵌套结构返回不同的解析类实例。
    """

    def is_nested_structure(package, depth=1):
        """
        递归检查 AR-PACKAGE 的嵌套深度。
        """
        if 'AR-PACKAGES' in package and 'AR-PACKAGE' in package['AR-PACKAGES']:
            nested_packages = package['AR-PACKAGES']['AR-PACKAGE']
            if not isinstance(nested_packages, list):
                nested_packages = [nested_packages]

            max_depth = depth
            for nested_package in nested_packages:
                max_depth = max(max_depth, is_nested_structure(nested_package, depth + 1))
            return max_depth
        return depth

    message_info = {}

    for item in db_path:
        # 从字典中获取 ARXML 文件路径
        # value = item.get('arxml_path')

        # 使用 xmltodict 将 ARXML 文件解析为字典
        with open(item, 'r', encoding='utf-8') as file:
            arxml_data = xmltodict.parse(file.read())

        # 获取顶层 AR-PACKAGES
        top_level_packages = arxml_data['AUTOSAR']['AR-PACKAGES']['AR-PACKAGE']

        if not isinstance(top_level_packages, list):
            top_level_packages = [top_level_packages]

        # 检查嵌套深度
        max_depth = 0
        for package in top_level_packages:
            depth = is_nested_structure(package)
            max_depth = max(max_depth, depth)

        # 根据嵌套深度返回结果
        if max_depth < 3:
            parser = ExtractingARXMLPREH(item)
            message_info.update(parser.extracting_can_msg2())
        elif max_depth > 2:
            parser = ExtractingARXMLPREHADD(item)
            message_info.update(parser.extracting_can_msg())

    return message_info


class ExtractingARXMLPREH(object):
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
        self.signal_package = {}
        self.signal_group_package = {}
        self.ecu_instance_package = {}
        self.communication_cluster_package = {}
        self.communication_package = {}
        self.ecu_extract_package = {}
        self.ecu_instance = None
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
            with open(self.arxml_path, 'r', encoding='utf-8') as infile, open(new_file_path, 'w',
                                                                              encoding='utf-8') as outfile:
                line_number = 1
                for line in infile:
                    line_number_str = f"*{line_number:06}"
                    # 替换所有的 `</` 左侧非空格的标签
                    line = re.sub(r'(\S)(</)', rf'\1{line_number_str}\2', line)
                    outfile.write(line)
                    line_number += 1

        except Exception as e:
            logging.error(f"发生错误：{e}")

        with open(new_file_path, 'r', encoding="utf-8") as f:
            arxml_content = f.read()
            string_data = xmltodict.parse(arxml_content)
        return string_data

    @staticmethod
    def dict_to_list(content):
        """
        公共方法 将字典 转成list

        @param content:
        @return:
        """
        if isinstance(content, dict):
            return [content]
        return content

    def get_ecu_instance_name(self):
        ecu_instances = self.find_tag_content(self.ecu_instance_package, 'ECU-INSTANCE')
        if ecu_instances:
            self.ecu_instance = ecu_instances[0]['SHORT-NAME']

    def find_package(self):
        """
        公共方法：找到对应的 package 并分类存储。

        @return: 无返回值，将找到的 package 数据存储到类的属性中。
        """
        # 将 ARXML 数据中的 AR-PACKAGES 转换为列表形式，便于遍历
        ar_packages = self.dict_to_list(self.arxml_data['AUTOSAR']['AR-PACKAGES']['AR-PACKAGE'])

        # 遍历所有 AR-PACKAGE
        for ar_package in ar_packages:
            # 获取当前 AR-PACKAGE 中的 ELEMENTS，并转换为列表形式
            elements = self.dict_to_list(ar_package.get('ELEMENTS', {}))

            # 遍历 ELEMENTS，查找特定类型的 package
            for element in elements:
                # 如果 ELEMENTS 中包含 "ETHERNET-CLUSTER"、"CAN-CLUSTER" 或 "LIN-CLUSTER"
                # 则将当前 AR-PACKAGE 归类为通信集群包（communication_cluster_package）
                if "ETHERNET-CLUSTER" in element or "CAN-CLUSTER" in element or "LIN-CLUSTER" in element:
                    self.communication_cluster_package = ar_package

                # 如果 ELEMENTS 中包含 "ECU-INSTANCE"
                # 则将当前 AR-PACKAGE 归类为 ECU 实例包（ecu_instance_package）
                if "ECU-INSTANCE" in element:
                    self.ecu_instance_package = ar_package

                # 如果 ELEMENTS 中包含 "SYSTEM-SIGNAL"
                # 则将当前 AR-PACKAGE 归类为信号包（signal_package）
                if "SYSTEM-SIGNAL" in element:
                    self.signal_package = ar_package

                # 如果 ELEMENTS 中包含 "SYSTEM-SIGNAL-GROUP"
                # 则将当前 AR-PACKAGE 归类为信号组包（signal_group_package）
                if "SYSTEM-SIGNAL-GROUP" in element:
                    self.signal_group_package = ar_package

            # 查找其他类型的 package，调用辅助方法 find_other_package
            self.find_other_package(ar_package)

    def find_other_package(self, ar_package):
        """
        查找 AR-PACKAGE 中的嵌套包，并进一步处理。

        @param ar_package: 当前的 AR-PACKAGE 数据。
        @return: 无返回值，处理结果存储在类的属性中。
        """
        # 获取当前 AR-PACKAGE 中的嵌套 AR-PACKAGES，并转换为列表形式
        inner_arpackage = self.dict_to_list(ar_package.get('AR-PACKAGES', {}))
        if not inner_arpackage:
            return
        # 遍历嵌套的 AR-PACKAGES
        for inner_package in inner_arpackage:
            if not inner_package:
                continue
            # 获取嵌套包中的 AR-PACKAGE 数据，并转换为列表形式
            inner_packages_data = self.dict_to_list(inner_package.get("AR-PACKAGE", {}))

            # 遍历每个嵌套包数据
            for inner_package_data in inner_packages_data:
                # 获取当前嵌套包中的 ELEMENTS，并转换为列表形式
                elements = self.dict_to_list(inner_package_data.get('ELEMENTS', {}))

                # 调用 handle_elements 方法，处理 ELEMENTS 数据
                # 将当前嵌套包的 ELEMENTS 和外层 AR-PACKAGE 传递给处理函数
                self.handle_elements(elements, ar_package)

    def handle_elements(self, elements, ar_package):
        """
        处理 ELEMENTS 数据，根据关键字匹配确定对应 package 类型。

        @param elements: 当前 AR-PACKAGE 中的 ELEMENTS 数据。
        @param ar_package: 当前的 AR-PACKAGE 数据。
        @return: 无返回值，处理结果存储在类的属性中。
        """
        # 遍历 ELEMENTS 数据
        for element in elements:
            # 如果 ELEMENTS 中包含通信相关的关键字，则将当前 AR-PACKAGE 归类为通信包
            if self.contains_keywords(element, self.communication_keywords):
                self.communication_package = ar_package

            # 如果 ELEMENTS 中包含 ECU 提取相关的关键字，则将当前 AR-PACKAGE 归类为 ECU 提取包
            if self.contains_keywords(element, self.ecu_extract_keywords):
                self.ecu_extract_package = ar_package

    @staticmethod
    def contains_keywords(element, keywords):
        """检查元素是否包含任意关键字"""
        return any(keyword in element for keyword in keywords)

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

    def extracting_all(self):
        """

        @return:
        """
        self.find_package()
        self.extracting_can()
        self.extracting_lin()
        self.extracting_eth()
        self.get_ecu_instance_name()
        self.extracting_can_physical_channel()

    def extracting_can(self):
        tag = "CAN-COMMUNICATION-CONTROLLER"
        self.data['can'] = self.find_tag_content(self.ecu_instance_package, tag)

    def extracting_lin(self):
        tag = "LIN-MASTER"
        self.data['lin'] = self.find_tag_content(self.ecu_instance_package, tag)

    def extracting_eth(self):
        tag = "ETHERNET-COMMUNICATION-CONNECTOR"
        self.data['eth'] = self.find_tag_content(self.ecu_instance_package, tag)

    def extracting_can_physical_channel(self):
        tag = "CAN-PHYSICAL-CHANNEL"
        can_physical_channel = self.find_tag_content(self.communication_package, tag)
        self.data['can_physical_channels'] = can_physical_channel
        # self.extracting_can_msg()
        # self.extracting_can_frame()

    def extracting_can_msg(self):
        """
        提取 CAN 的 message 并处理相关数据。

        @return: 无返回值，处理后的数据存储在 self.data['msg'] 中。
        """
        # 初始化存储 message 数据的字典
        self.data['msg'] = {"com": {},
                            "ecuc": {},
                            "canif": {}
                            }

        # 调用 handle_signal 方法，提取信号相关数据
        # 返回值包括：
        # - sig_data: 信号数据
        # - sig_2_pdu: 信号到 PDU 的映射
        # - sig_triggering_data: 信号触发数据
        # - i_signal_to_i_pdu_map_data: 内部信号到内部 PDU 的映射数据
        sig_data, sig_2_pdu, sig_triggering_data, i_signal_to_i_pdu_map_data = self.handle_signal()

        # 调用 extracting_can_frame 方法，提取 CAN 帧数据并生成 CAN 帧映射字典
        can_frame_data_map = self.extracting_can_frame()

        # 遍历所有物理 CAN 通道
        for physical_channel in self.data['can_physical_channels']:
            # 为当前物理通道初始化 message 数据结构，包含 com、ecuc 和 canif 三个部分
            # self.data['msg'] = {
            #     "com": {physical_channel["SHORT-NAME"]: {}},  # 初始化 com 数据
            #     "ecuc": {physical_channel["SHORT-NAME"]: {}},  # 初始化 ecuc 数据
            #     "canif": {physical_channel["SHORT-NAME"]: {}},  # 初始化 canif 数据
            # }
            # 为当前物理通道初始化 message 数据结构，包含 com、ecuc 和 canif 三个部分
            self.data['msg']["com"][physical_channel["SHORT-NAME"]] = {}
            self.data['msg']["ecuc"][physical_channel["SHORT-NAME"]] = {}
            self.data['msg']["canif"][physical_channel["SHORT-NAME"]] = {}

            # 从当前物理通道中提取 CAN-FRAME-TRIGGERING 数据
            can_frame_triggerings = self.find_tag_content(physical_channel, "CAN-FRAME-TRIGGERING")

            # 调用 handle_can_frame_triggerings 方法，处理 CAN 帧触发数据
            # 参数包括：
            # - can_frame_triggerings: 当前通道的 CAN 帧触发数据
            # - can_frame_data_map: CAN 帧映射数据
            # - physical_channel: 当前物理通道的数据
            # - sig_data: 信号数据
            # - sig_2_pdu: 信号到 PDU 的映射
            # - sig_triggering_data: 信号触发数据
            # - i_signal_to_i_pdu_map_data: 内部信号到内部 PDU 的映射数据
            self.handle_can_frame_triggerings(
                can_frame_triggerings,
                can_frame_data_map,
                physical_channel,
                sig_data,
                sig_2_pdu,
                sig_triggering_data,
                i_signal_to_i_pdu_map_data
            )

    def extracting_can_msg2(self):
        """
        提取 CAN 的 message 并处理相关数据。

        @return: 无返回值，处理后的数据存储在 self.data['msg'] 中。
        """
        # 初始化存储 message 数据的字典

        # 调用 handle_signal 方法，提取信号相关数据
        # 返回值包括：
        # - sig_data: 信号数据
        # - sig_2_pdu: 信号到 PDU 的映射
        # - sig_triggering_data: 信号触发数据
        # - i_signal_to_i_pdu_map_data: 内部信号到内部 PDU 的映射数据
        sig_data, sig_2_pdu, sig_triggering_data, i_signal_to_i_pdu_map_data = self.handle_signal()

        # 调用 extracting_can_frame 方法，提取 CAN 帧数据并生成 CAN 帧映射字典
        can_frame_data_map = self.extracting_can_frame()

        # 遍历所有物理 CAN 通道
        self.data['msg'] = {}
        for physical_channel in self.data['can_physical_channels']:
            # 从当前物理通道中提取 CAN-FRAME-TRIGGERING 数据
            node_name = physical_channel['SHORT-NAME'].split("*")[0]
            if node_name not in self.data['msg']:
                self.data['msg'][node_name] = {}

            can_frame_triggerings = self.find_tag_content(physical_channel, "CAN-FRAME-TRIGGERING")

            # 调用 handle_can_frame_triggerings 方法，处理 CAN 帧触发数据
            # 参数包括：
            # - can_frame_triggerings: 当前通道的 CAN 帧触发数据
            # - can_frame_data_map: CAN 帧映射数据
            # - physical_channel: 当前物理通道的数据
            # - sig_data: 信号数据
            # - sig_2_pdu: 信号到 PDU 的映射
            # - sig_triggering_data: 信号触发数据
            # - i_signal_to_i_pdu_map_data: 内部信号到内部 PDU 的映射数据
            self.handle_can_frame_triggerings2(
                can_frame_triggerings,
                can_frame_data_map,
                physical_channel,
                sig_data,
                sig_2_pdu,
                sig_triggering_data,
                i_signal_to_i_pdu_map_data,
                node_name
            )

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

    def handle_can_frame_triggerings(self, can_frame_triggerings, can_frame_data_map, physical_channel,
                                     sig_data, sig_2_pdu, sig_triggering_data, i_signal_to_i_pdu_map_data):
        """
        处理 CAN 帧触发信息，解析 CAN 帧、PDU 触发信息以及信号信息，并将结果存储到数据结构中。

        @param can_frame_triggerings: CAN 帧触发信息列表。
        @param can_frame_data_map: CAN 帧数据映射，用于更新 CAN 帧的额外信息。
        @param physical_channel: 当前物理通道的相关信息。
        @param sig_data: 信号的详细数据。
        @param sig_2_pdu: 信号到 PDU 的映射数据。
        @param sig_triggering_data: 信号触发数据。
        @param i_signal_to_i_pdu_map_data: I-SIGNAL 到 I-PDU 的映射数据。
        """
        # 遍历所有 CAN 帧触发信息
        for can_frame in can_frame_triggerings:
            # 提取 CAN 帧的名称（从 FRAME-REF 中提取）
            msg_name = can_frame['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 初始化一个字典，用于存储当前 CAN 帧的基本信息
            msg = {
                "msg_name": can_frame['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[0],  # CAN 帧名称
                "can_addressing_mode": can_frame['CAN-ADDRESSING-MODE'].split("*")[0],  # CAN 地址模式
                "can_fd_frame_support": "true" if can_frame['CAN-FRAME-TX-BEHAVIOR'].split("*")[
                                                      0] == "CAN-FD" else "false",  # CAN FD 帧支持情况
                "can_frame_tx_behavior": can_frame.get('CAN-FRAME-TX-BEHAVIOR', "").split("*")[0],  # CAN 帧发送行为
                "can_frame_rx_behavior": can_frame.get('CAN-FRAME-RX-BEHAVIOR', "").split("*")[0],  # CAN 帧接收行为
                "identifier": can_frame['IDENTIFIER'].split("*")[0],  # CAN 帧标识符
            }

            # 检查 CAN 帧数据映射中是否有该 CAN 帧的额外信息
            update_msg = can_frame_data_map.get(msg_name)
            if update_msg:
                # 如果有额外信息，更新到当前 CAN 帧字典中
                msg.update(update_msg)

            # 处理 PDU 触发信息
            # 从 CAN 帧中找到 PDU-TRIGGERINGS --> PDU-TRIGGERING-REF-CONDITIONAL --> PDU-TRIGGERING-REF
            pdu_triggering_ref = self.find_tag_content(can_frame, 'PDU-TRIGGERING-REF')

            # 提取所有 PDU 触发引用的短名称
            triggering_refs = [triggering_ref["#text"].rsplit("/", 1)[1].split("*")[0]
                               for triggering_ref in pdu_triggering_ref]

            # 处理 PDU 触发信息，返回找到的 PDU 触发信息和 PDU 引用映射
            find_pdu_triggerings, pdu_ref_map = self.handle_pdu_triggerings(physical_channel, triggering_refs)

            # 从 PDU 触发信息中找到所有信号触发引用
            signal_refs = self.find_tag_content(find_pdu_triggerings, 'I-SIGNAL-TRIGGERING-REF')

            # 提取所有信号触发引用的短名称
            signal_list = [signal["#text"].rsplit("/", 1)[1]
                           for signal in signal_refs]

            # 根据信号触发引用、信号数据等信息，获取信号的详细信息列表
            signal_data_list = self.find_signal_info(sig_data, sig_2_pdu, sig_triggering_data,
                                                     signal_list, i_signal_to_i_pdu_map_data, pdu_ref_map)

            # 将信号列表添加到 CAN 帧信息中
            msg['signals'] = signal_data_list

            # 根据 CAN 帧的发送行为，将数据存储到对应的结构中
            if msg['can_frame_tx_behavior']:
                # 如果 CAN 帧有发送行为，将其存储到 CANIF、ECUC 和 COM 数据结构中
                if msg["can_fd_frame_support"] == 'false':
                    msg["can_fd_frame_support"] = False
                else:
                    msg["can_fd_frame_support"] = True

                if msg["can_addressing_mode"] == 'STANDARD':
                    msg["can_addressing_mode"] = False
                else:
                    msg["can_addressing_mode"] = True

                self.data['msg']["canif"][physical_channel["SHORT-NAME"]].setdefault("tx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg["can_addressing_mode"],
                     msg['can_fd_frame_support'],
                     msg['msg_type'], 'Tx'])
                self.data['msg']["ecuc"][physical_channel["SHORT-NAME"]].setdefault("tx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg['can_fd_frame_support'],
                     msg['can_fd_frame_support'],
                     msg['msg_type']])
                self.data['msg']["com"][physical_channel["SHORT-NAME"]].setdefault("tx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg['can_fd_frame_support'],
                     msg['msg_type'], signal_data_list, 0, 0])

            # 根据 CAN 帧的接收行为，将数据存储到对应的结构中
            if msg['can_frame_rx_behavior']:
                # 如果 CAN 帧有接收行为，将其存储到 CANIF、ECUC 和 COM 数据结构中
                if msg["can_fd_frame_support"] == 'false':
                    msg["can_fd_frame_support"] = False
                else:
                    msg["can_fd_frame_support"] = True

                if msg["can_addressing_mode"] == 'STANDARD':
                    msg["can_addressing_mode"] = False
                else:
                    msg["can_addressing_mode"] = True
                self.data['msg']["canif"][physical_channel["SHORT-NAME"]].setdefault("rx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg["can_addressing_mode"],
                     msg['can_fd_frame_support'],
                     msg['msg_type'], 'Rx'])
                self.data['msg']["ecuc"][physical_channel["SHORT-NAME"]].setdefault("rx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg['can_fd_frame_support'],
                     msg['can_fd_frame_support'],
                     msg['msg_type']])
                self.data['msg']["com"][physical_channel["SHORT-NAME"]].setdefault("rx_msg", []).append(
                    [msg["msg_name"], msg["identifier"], msg["frame_length"], msg['can_fd_frame_support'],
                     msg['msg_type'], signal_data_list, 0, 0])

    def handle_can_frame_triggerings2(self, can_frame_triggerings, can_frame_data_map, physical_channel,
                                      sig_data, sig_2_pdu, sig_triggering_data, i_signal_to_i_pdu_map_data, node_name):
        """
        处理 CAN 帧触发信息，解析 CAN 帧、PDU 触发信息以及信号信息，并将结果存储到数据结构中。

        @param can_frame_triggerings: CAN 帧触发信息列表。
        @param can_frame_data_map: CAN 帧数据映射，用于更新 CAN 帧的额外信息。
        @param physical_channel: 当前物理通道的相关信息。
        @param sig_data: 信号的详细数据。
        @param sig_2_pdu: 信号到 PDU 的映射数据。
        @param sig_triggering_data: 信号触发数据。
        @param i_signal_to_i_pdu_map_data: I-SIGNAL 到 I-PDU 的映射数据。
        """
        # 初始化一个存储字典，保留所有的FRAME-PORT键值对
        frame_port_directions = {}

        # 用于删选无用pdu和txrxpdu
        msg_dir_all = self.find_tag_content(self.communication_package, "FRAME-PORT")
        can_cluster = self.find_tag_content(self.communication_package, "CAN-CLUSTER")
        self.ecu_instance = self.find_tag_content(can_cluster, "SHORT-NAME")[0].split("*")[0]

        for msg_dir in msg_dir_all:
            # 获取通信方向
            comm_direction = msg_dir.get("COMMUNICATION-DIRECTION", "UNKNOWN").split("*")[0]
            direction = "tx" if comm_direction == "OUT" else "rx" if comm_direction == "IN" else "UNKNOWN"
            # 使用 SHORT-NAME 作为键，存储通信方向信息
            frame_port_directions[msg_dir.get("SHORT-NAME", "").split("*")[0]] = direction

        # 遍历所有 CAN 帧触发信息
        for can_frame in can_frame_triggerings:
            # 提取 CAN 帧的名称（从 FRAME-REF 中提取）
            direction = ''
            msg_name = can_frame['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[0]
            # 提取 FRAME-PORT-REFS 并只处理第一条 FRAME-PORT-REF
            frame_port_refs = self.find_tag_content(can_frame, "FRAME-PORT-REFS")[0]
            if frame_port_refs:  # 确保 frame_port_refs 非空
                try:
                    for frame_port in frame_port_refs["FRAME-PORT-REF"]:
                        frame_port_name = frame_port["#text"].split("*")[0]

                        if self.ecu_instance in frame_port_name:
                            direction = frame_port_directions.get(frame_port_name.rsplit("/", 1)[-1], "UNKNOWN")

                except (IndexError, KeyError, TypeError):
                    # 捕获任何访问错误，保持默认值为 UNKNOWN
                    pass
            if direction == "tx" or direction == "rx":
                # 初始化字典，用于存储当前 CAN 帧的基本信息
                msg = {
                    "msg_name": can_frame['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[0],  # CAN 帧名称
                    "can_addressing_mode": can_frame['CAN-ADDRESSING-MODE'].split("*")[0],  # CAN 地址模式
                    "can_fd_frame_support": "true" if can_frame['CAN-FRAME-TX-BEHAVIOR'].split("*")[
                                                          0] == "CAN-FD" else "false",  # CAN FD 帧支持情况
                    "can_frame_tx_behavior": True if direction == "tx" else False,  # CAN 帧发送行为
                    "can_frame_rx_behavior": True if direction == "rx" else False,  # CAN 帧接收行为
                    "identifier": can_frame['IDENTIFIER'].split("*")[0],  # CAN 帧标识符
                    "name_row": can_frame['FRAME-REF']['#text'].rsplit("/", 1)[1].split("*")[1],
                    "can_addressing_mode_row": can_frame['CAN-ADDRESSING-MODE'].split("*")[1],
                    "identifier_row": can_frame['IDENTIFIER'].split("*")[1],  # CAN 帧标识符
                    "can_fd_frame_support_row": can_frame['CAN-FRAME-TX-BEHAVIOR'].split("*")[1]

                }

                # 检查 CAN 帧数据映射中是否有该 CAN 帧的额外信息
                update_msg = can_frame_data_map.get(msg_name)
                if update_msg:
                    # 如果有额外信息，更新到当前 CAN 帧字典中
                    msg.update(update_msg)

                # 处理 PDU 触发信息
                # 从 CAN 帧中找到 PDU-TRIGGERINGS --> PDU-TRIGGERING-REF-CONDITIONAL --> PDU-TRIGGERING-REF
                pdu_triggering_ref = self.find_tag_content(can_frame, 'PDU-TRIGGERING-REF')

                # 提取所有 PDU 触发引用的短名称
                triggering_refs = []
                for triggering_ref in pdu_triggering_ref:
                    triggering_refs.append(triggering_ref["#text"].rsplit("/", 1)[1].split("*")[0])

                # 处理 PDU 触发信息，返回找到的 PDU 触发信息和 PDU 引用映射
                find_pdu_triggerings, pdu_ref_map = self.handle_pdu_triggerings(physical_channel, triggering_refs)

                # 从 PDU 触发信息中找到所有信号触发引用
                # 一般报文这个为多元素列表，group为1个
                signal_refs = self.find_tag_content(find_pdu_triggerings, 'I-SIGNAL-TRIGGERING-REF')

                # 提取所有信号触发引用的短名称
                signal_list = [signal["#text"].rsplit("/", 1)[1]
                               for signal in signal_refs]

                # 根据信号触发引用、信号数据等信息，获取信号的详细信息列表
                signal_data_list = self.find_signal_info2(sig_data, sig_2_pdu, sig_triggering_data,
                                                          signal_list, i_signal_to_i_pdu_map_data, pdu_ref_map)

                # 如果没有信号
                if not signal_data_list:
                    signal_data_list = []

                # 将信号列表添加到 CAN 帧信息中
                msg['signals'] = signal_data_list

                # 处理 PDU 触发信息，返回找到的 PDU 触发信息和 PDU 引用映射
                pdu_cycle = 0
                pdu_cycle_row = ''
                i_signal_to_i_pdu = self.find_tag_content(self.communication_package, "I-SIGNAL-I-PDU")
                for pdu in i_signal_to_i_pdu:
                    pdu_name = self.find_tag_content(pdu, "SHORT-NAME")
                    pdu_name_map = pdu_ref_map[triggering_refs[0]]
                    if pdu_name_map[0].split("*")[0] == pdu_name[0].split("*")[0]:
                        # 获取报文周期
                        pdu_cycle_key = self.find_tag_content(pdu, "TIME-PERIOD")
                        if pdu_cycle_key:
                            pdu_cycle = float(pdu_cycle_key[0]['VALUE'].split("*")[0])
                            pdu_cycle_row = pdu_cycle_key[0]['VALUE'].split("*")[1]

                        # 获取报文offset
                        pdu_offset = self.find_tag_content(pdu, "TIME-OFFSET")

                # 根据 CAN 帧的发送行为，将数据存储到对应的结构中
                if msg['can_frame_tx_behavior']:
                    # 如果 CAN 帧有发送行为，将其存储到 CANIF、ECUC 和 COM 数据结构中
                    if msg["can_fd_frame_support"] == 'false':
                        msg["can_fd_frame_support"] = False
                    else:
                        msg["can_fd_frame_support"] = True

                    if msg["can_addressing_mode"] == 'STANDARD':
                        msg["can_addressing_mode"] = False
                    else:
                        msg["can_addressing_mode"] = True

                    msg_type = "Normal"
                    if "diag" in msg["msg_name"].lower():
                        if "rs" in msg["msg_name"].lower():
                            msg_type = "DiagResponse"
                        else:
                            msg_type = "DiagRequest"

                    self.data['msg'][node_name].setdefault("TX", []).append({
                        "msg_name": msg["msg_name"],
                        "msg_name_row": msg["name_row"],
                        "msg_id": msg["identifier"],
                        "msg_id_row": msg["identifier_row"],
                        "msg_length": msg["frame_length"],
                        "msg_length_row": msg["frame_length_row"],
                        "is_extended_frame": msg["can_addressing_mode"],  # 是否是扩展帧
                        "is_extended_frame_row": msg['can_addressing_mode_row'],
                        "is_fd": msg["can_fd_frame_support"],  # 是否是fd 报文
                        "is_fd_row": msg['can_fd_frame_support_row'],
                        "send_type": "",
                        "signals": signal_data_list,
                        "cycle_time": pdu_cycle,
                        "cycle_time_row": pdu_cycle_row,
                        "attribute": msg_type,  # 是 网管报文还是诊断报文 还是xcp报文
                        "identifier": can_frame['IDENTIFIER'].split("*")[0],  # CAN 帧标识符
                        "identifier_row": msg['identifier_row'],
                    })

                # 根据 CAN 帧的接收行为，将数据存储到对应的结构中
                if msg['can_frame_rx_behavior']:
                    # 如果 CAN 帧有接收行为，将其存储到 CANIF、ECUC 和 COM 数据结构中
                    if msg["can_fd_frame_support"] == 'false':
                        msg["can_fd_frame_support"] = False
                    else:
                        msg["can_fd_frame_support"] = True

                    if msg["can_addressing_mode"] == 'STANDARD':
                        msg["can_addressing_mode"] = False
                    else:
                        msg["can_addressing_mode"] = True

                    msg_type = "Normal"
                    if "diag" in msg["msg_name"].lower():
                        if "rs" in msg["msg_name"].lower():
                            msg_type = "DiagResponse"
                        else:
                            msg_type = "DiagRequest"

                    self.data['msg'][node_name].setdefault("RX", []).append({
                        "msg_name": msg["msg_name"],
                        "msg_name_row": msg["name_row"],
                        "msg_id": msg["identifier"],
                        "msg_id_row": msg["identifier_row"],
                        "msg_length": msg["frame_length"],
                        "msg_length_row": msg["frame_length_row"],
                        "is_extended_frame": msg["can_addressing_mode"],  # 是否是扩展帧
                        "is_extended_frame_row": msg['can_addressing_mode_row'],
                        "is_fd": msg["can_fd_frame_support"],  # 是否是fd 报文
                        "is_fd_row": msg['can_fd_frame_support_row'],
                        "send_type": "",
                        "signals": signal_data_list,
                        "cycle_time": pdu_cycle,
                        "cycle_time_row": pdu_cycle_row,
                        "attribute": msg_type,  # 是 网管报文还是诊断报文 还是xcp报文
                    })

    def handle_pdu_triggerings(self, physical_channel, triggering_refs):
        """
        处理 PDU 触发信息，找到匹配的 PDU 触发，并构建 PDU 引用映射。

        @param physical_channel: 当前物理通道的相关信息。
        @param triggering_refs: PDU 触发引用的短名称列表。
        @return: 返回找到的 PDU 触发信息和 PDU 引用映射。
        """
        # 从物理通道中提取所有 PDU-TRIGGERING 信息
        pdu_triggerings = self.find_tag_content(physical_channel, 'PDU-TRIGGERING')

        # 初始化一个字典，用于存储找到的 PDU 触发信息
        find_pdu_triggerings = {"pdu_triggerings": []}

        # # 初始化一个字典，用于存储 PDU 引用映射
        pdu_ref_map = {}

        # #初始化一个signal的字典，用于存储 signal 的真实名字
        # signal_name_map ={}
        # signal_map = self.find_tag_content(self.communication_package, "I-SIGNAL-TRIGGERING")
        #
        # for signal in signal_map:
        #     if not signal.get('I-SIGNAL-REF'):
        #         continue
        #     signal_real = signal['I-SIGNAL-REF']["#text"].rsplit("/", 1)[1]
        #     signal_name_map[signal.get("SHORT-NAME", "")] = signal_real

        # 遍历所有 PDU 触发信息
        for pdu_triggering in pdu_triggerings:
            # 检查当前 PDU 触发的 SHORT-NAME 是否在触发引用列表中
            if pdu_triggering['SHORT-NAME'].split("*")[0] in triggering_refs:
                # 如果匹配，处理单个信号的情况

                # # 提取发送（Tx）和接收（Rx）端口
                # tx_ports = []
                # rx_ports = []
                # for pdu_port_ref in self.dict_to_list(
                #         pdu_triggering.get("I-PDU-PORT-REFS", {}).get("I-PDU-PORT-REF", [])):
                #     port_path = pdu_port_ref.get("#text", "")
                #     # 判断是 Tx 还是 Rx
                #     if port_path.endswith("_Tx"):
                #         tx_ports.append(port_path)
                #     elif port_path.endswith("_Rx"):
                #         rx_ports.append(port_path)

                # 从 PDU-TRIGGERING 中提取 I-PDU-REF 的短名称
                i_pdu_ref = pdu_triggering['I-PDU-REF']["#text"].rsplit("/", 1)[1].split("*")[0]

                # 将 I-PDU-REF 添加到 PDU 引用映射中，按 SHORT-NAME 分组
                pdu_ref_map.setdefault(pdu_triggering['SHORT-NAME'].split("*")[0], []).append(i_pdu_ref)
                # #提取signal
                # signal_list = self.find_tag_content(physical_channel, 'I-SIGNAL-TRIGGERING-REF')
                # for signal in signal_list:
                #     if isinstance(signal, dict) and "#text" in signal:
                #         signal_key = signal["#text"].rsplit("/", 1)[-1]  # 提取短名称
                #         signal_name = signal_name_map.get(signal_key, "UNKNOWN")  # 根据短名称查找真实信号名
                #     else:
                #         signal_name = "UNKNOWN"  # 如果无法找到信号名，设置为默认值

                #     # 将当前 PDU-TRIGGERING 添加到找到的 PDU 触发信息列表中
                #     # find_pdu_triggerings['pdu_triggerings'].append(pdu_triggering)
                # find_pdu_triggerings['pdu_triggerings'].append({
                #     "short_name": pdu_triggering['SHORT-NAME'],
                #     "i_pdu_ref": i_pdu_ref,
                #     "tx_ports": tx_ports,
                #     "rx_ports": rx_ports,
                #     # "signal_list": signal_name
                # })
                find_pdu_triggerings['pdu_triggerings'].append(pdu_triggering)
        # 返回找到的 PDU 触发信息和 PDU 引用映射
        return find_pdu_triggerings, pdu_ref_map

    def get_com_msg(self):
        messages_data = []
        db_name = ""

        for k, msg_info in self.data['msg']['com'].items():
            inner_message = []
            rx_list = []
            tx_list = []
            # if not db_name:
            #     db_name = k
            rx_list.extend(msg_info['rx_msg'])
            tx_list.extend(msg_info['tx_msg'])
            inner_message.append(tx_list)
            inner_message.append(rx_list)
            inner_message.append(k)
            messages_data.append(inner_message)
        return messages_data

    def get_canif_msg(self):
        messages_data = []
        db_name = ""

        for k, msg_info in self.data['msg']['canif'].items():
            inner_message = []
            rx_list = []
            tx_list = []
            # if not db_name:
            #     db_name = k
            rx_list.extend(msg_info['rx_msg'])
            tx_list.extend(msg_info['tx_msg'])
            inner_message.append(tx_list)
            inner_message.append(rx_list)
            inner_message.append(k)
            inner_message.append('ZCT')  # todo
            messages_data.append(inner_message)
        return messages_data

    def get_ecuc_msg(self):
        messages_data = []
        db_name = ""
        for k, msg_info in self.data['msg']['ecuc'].items():
            inner_message = []
            rx_list = []
            tx_list = []
            # if not db_name:
            #     db_name = k
            rx_list.extend(msg_info['rx_msg'])
            tx_list.extend(msg_info['tx_msg'])
            inner_message.append(tx_list)
            inner_message.append(rx_list)
            inner_message.append(k)
            inner_message.append('ZCT')
            messages_data.append(inner_message)
        return messages_data

    def extracting_can_frame(self):
        """
        提取 CAN 帧信息，并生成 CAN 帧数据映射。

        @return: 返回一个字典（can_frame_data_map），以 CAN 帧的 SHORT-NAME 为键，值为包含帧长度、起始位置和消息类型的详细信息。
        """
        # 从通信包中提取 CAN-FRAME 数据
        can_frame_data = self.find_tag_content(self.communication_package, "CAN-FRAME")

        # 从通信包中提取 CAN-TP-CONNECTION 数据
        can_tp_connections = self.find_tag_content(self.communication_package, "CAN-TP-CONNECTION")

        # 从通信包中提取 CAN-NM-NODE 数据
        can_nm_nodes = self.find_tag_content(self.communication_package, "CAN-NM-NODE")

        # 调用 handle_can_tp_nm_node 方法，处理 CAN TP 连接和 NM 节点，生成 CAN TP 映射和 NM 节点列表
        can_tp_map, nm_node_list = self.handle_can_tp_nm_node(can_tp_connections, can_nm_nodes)

        # 初始化 CAN 帧数据映射字典
        can_frame_data_map = {}

        # 遍历所有 CAN 帧数据
        for can_frame in can_frame_data:
            # 将 CAN 帧的原始数据存储到映射字典中，以 SHORT-NAME 为键
            can_frame_data_map[can_frame["SHORT-NAME"].split("*")[0]] = can_frame

            # 从当前 CAN 帧中提取 PDU-TO-FRAME-MAPPING 数据
            pdu_to_frame_mapping = self.find_tag_content(can_frame, "PDU-TO-FRAME-MAPPING")

            # pdu_to_frame_mapping值并不是所有的CAN-FRAME都有
            if not pdu_to_frame_mapping:
                continue

            # 提取 PDU 的引用名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
            pdu_ref = pdu_to_frame_mapping[0]['PDU-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 更新 CAN 帧数据映射字典，存储帧长度、起始位置和消息类型
            can_frame_data_map[can_frame["SHORT-NAME"].split("*")[0]] = {
                "frame_length": int(can_frame['FRAME-LENGTH'].split("*")[0]),  # CAN 帧的长度
                "frame_length_row": can_frame['FRAME-LENGTH'].split("*")[1],  # CAN 帧的长度
                "start_position": pdu_to_frame_mapping[0]['START-POSITION'].split("*")[0],  # PDU 的起始位置
                "msg_type": self.cal_msg_type(pdu_ref, can_tp_map, nm_node_list)  # 消息类型，调用 cal_msg_type 方法计算
            }

        # 返回 CAN 帧数据映射字典
        return can_frame_data_map

    @staticmethod
    def cal_msg_type(pdu_ref, can_tp_map, nm_node_list):
        """
        根据 PDU 引用判断消息类型。

        @param pdu_ref: PDU 引用名称，用于判断消息类型。
        @param can_tp_map: CAN TP 映射字典，包含 PDU 的流控制信息。
        @param nm_node_list: NM 节点列表，包含 NM 消息的 PDU 名称。
        @return: 返回消息类型（字符串），可能的值包括：
                 - "Normal"：普通消息（默认类型）。
                 - "DiagState"：诊断状态消息。
                 - "DiagRequest"：诊断请求消息。
                 - "DiagResponse"：诊断响应消息。
                 - "NmAsrMessage"：NM ASR 消息。
        """
        # 初始化消息类型为 "Normal"（默认值）
        msg_type = "Normal"

        # 检查 PDU 引用是否在 CAN TP 映射中
        if pdu_ref in can_tp_map:
            # 如果 PDU 不包含流控制信息，则消息类型为 "DiagState"
            if not can_tp_map[pdu_ref]["flow_control"]:
                msg_type = "DiagState"
            else:
                # 如果 PDU 包含流控制信息，根据名称判断是否为诊断请求或响应
                if "req" in pdu_ref.lower():
                    # 如果 PDU 名称中包含 "req"（不区分大小写），消息类型为 "DiagRequest"
                    msg_type = "DiagRequest"
                if "res" in pdu_ref.lower():
                    # 如果 PDU 名称中包含 "res"（不区分大小写），消息类型为 "DiagResponse"
                    msg_type = "DiagResponse"

        if "TP_DIAG" in pdu_ref and "RQ" in pdu_ref:
            msg_type = "DiagRequest"
        if "TP_DIAG" in pdu_ref and "RS" in pdu_ref:
            msg_type = "DiagResponse"

        # 检查 PDU 引用是否在 NM 节点列表中
        if pdu_ref in nm_node_list:
            # 如果 PDU 属于 NM 节点，则消息类型为 "NmAsrMessage"
            msg_type = "NmAsrMessage"

        # 返回最终的消息类型
        return msg_type

    def handle_can_tp_nm_node(self, can_tp_connections, can_nm_nodes):
        """
        处理 CAN TP（传输协议）连接和 CAN NM（网络管理）节点信息，生成 CAN TP 映射和 NM 节点列表。

        @param can_tp_connections: CAN TP 连接信息列表，包含数据 PDU 和流控制 PDU 的相关信息。
        @param can_nm_nodes: CAN NM 节点信息列表，包含 TX 和 RX 的 NM PDU 引用。
        @return: 返回两个结果：
                 - can_tp_map: 字典，存储 CAN TP 映射信息，以数据 PDU 的名称为键，值包含流控制信息。
                 - nm_node_list: 列表，存储 NM 节点的 PDU 名称。
        """
        # 初始化 CAN TP 映射字典
        can_tp_map = {}

        # 初始化 NM 节点列表
        nm_node_list = []

        # 遍历 CAN TP 连接信息
        for can_tp_connection in can_tp_connections:
            # 检查当前连接是否包含 'DATA-PDU-REF'
            if 'DATA-PDU-REF' in can_tp_connection:
                # 提取 DATA-PDU 的名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
                text = can_tp_connection['DATA-PDU-REF']['#text'].rsplit("/", 1)[1]

                # 检查是否包含 'FLOW-CONTROL-PDU-REF'，如果存在则流控制为 True，否则为 False
                can_tp_map[text] = {
                    "flow_control": False if 'FLOW-CONTROL-PDU-REF' not in can_tp_connection else True
                }

        # 遍历 CAN NM 节点信息
        for nm_node in can_nm_nodes:
            # 提取 TX-NM-PDU-REF（发送的 NM PDU 引用）
            tx_nm_pdu_refs = self.find_tag_content(nm_node, "TX-NM-PDU-REF")

            # 提取 RX-NM-PDU-REF（接收的 NM PDU 引用）
            rx_nm_pdu_refs = self.find_tag_content(nm_node, "RX-NM-PDU-REF")

            # 合并 TX 和 RX 的 NM PDU 引用
            tx_nm_pdu_refs.extend(rx_nm_pdu_refs)

            # 遍历合并后的 NM PDU 引用列表
            for tx_nm_pdu_ref in tx_nm_pdu_refs:
                # 提取 NM PDU 的名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
                text = tx_nm_pdu_ref['#text'].rsplit("/", 1)[1]

                # 将 NM PDU 的名称添加到 NM 节点列表中
                nm_node_list.append(text)

        # 返回 CAN TP 映射字典和 NM 节点列表
        return can_tp_map, nm_node_list

    def handle_signal(self):
        """
        处理信号相关数据，包括信号信息、信号到PDU映射、信号触发信息等。

        @return: 返回处理后的信号数据、信号到PDU映射数据、信号触发数据和I-SIGNAL到I-PDU的映射数据。
        """
        # 从通信包中提取所有 I-SIGNAL 信息（信号的定义）
        signals = self.find_tag_content(self.communication_package, "I-SIGNAL")

        # 从通信包中提取所有 I-SIGNAL-I-PDU 信息（PDU的定义）
        i_signal_to_i_pdu = self.find_tag_content(self.communication_package, "I-SIGNAL-I-PDU")

        # 从通信包中提取所有 I-SIGNAL-TO-I-PDU-MAPPING 信息（信号到PDU的映射）
        # sig_2_pdu_mapping = self.find_tag_content(self.communication_package, "I-SIGNAL-TO-I-PDU-MAPPING")

        # 初始化存储 message 数据的字典
        can_frame_triggerings_map = []

        for physical_channel in self.data['can_physical_channels']:
            # 从当前物理通道中提取 CAN-FRAME-TRIGGERING 数据
            can_frame_triggerings = self.find_tag_content(physical_channel, "CAN-FRAME-TRIGGERING")

            can_frame_triggerings_map.append(can_frame_triggerings)

        # 提取 CAN-FRAME-TRIGGERING 中的所有 I-PDU-REF 的最后部分
        valid_pdu_refs = set()
        # 遍历每个物理通道的 CAN-FRAME-TRIGGERING 数据
        for can_frame_triggering in can_frame_triggerings_map:
            # 遍历每个 CAN-FRAME-TRIGGERING 数据
            for can_frame in can_frame_triggering:
                # 从 CAN-FRAME-TRIGGERING 数据中获取 FRAME-REF 信息
                trigger_names = self.find_tag_content(can_frame, "FRAME-REF")
                # 遍历 trigger_names 是列表
                for trigger_name in self.dict_to_list(trigger_names):
                    # 确保 trigger_name 为字典 提取 FRAME-REF 的最后部分
                    if isinstance(trigger_name, dict) and "#text" in trigger_name:
                        valid_pdu_refs.add(trigger_name["#text"].rsplit("/", 1)[-1].split("*")[0])

        # 从通信包中提取所有 CAN-FRAME 信息
        can_frame_datas = self.find_tag_content(self.communication_package, "CAN-FRAME")
        valid_name_map = {}
        for can_frame_data in can_frame_datas:
            pdu_ref = self.find_tag_content(can_frame_data, "PDU-REF")
            if len(pdu_ref) == 0:
                continue
            pdu_rel = pdu_ref[0]['#text'].rsplit("/", 1)[-1].split("*")[0]
            shore_name = self.find_tag_content(can_frame_data, "SHORT-NAME")

            if shore_name[0].split("*")[0] in valid_pdu_refs:
                valid_name_map[pdu_rel] = shore_name

        # 真实名字找对应的起始位 从通信包中提取 I-SIGNAL-I-PDU 信息
        sig_2_pdu_mapping = self.find_tag_content(self.communication_package, "I-SIGNAL-I-PDU")

        # 筛选 sig_2_pdu_mapping 中的 SHORT-NAME 是否存在于 valid_pdu_refs
        filtered_sig_2_pdu_mapping = []
        for mapping in sig_2_pdu_mapping:
            # 判断 mapping 中的 SHORT-NAME 是否在 valid_pdu_refs 中
            mapping_short_name = self.find_tag_content(mapping, "SHORT-NAME")
            if mapping_short_name[0].split("*")[0] in valid_name_map:
                # 提取 I-SIGNAL-TO-I-PDU-MAPPING 节点列表
                # signal_to_pdu_mappings = self.find_tag_content(mapping, "I-SIGNAL-TO-I-PDU-MAPPING")
                filtered_sig_2_pdu_mapping.append(mapping)

        signal_to_pdu_mappings = self.find_tag_content(filtered_sig_2_pdu_mapping, "I-SIGNAL-TO-I-PDU-MAPPING")

        # 从通信集群包中提取所有 I-SIGNAL-TRIGGERING 信息（信号触发定义）
        i_sig_triggering = self.find_tag_content(self.communication_package, "I-SIGNAL-TRIGGERING")

        # 提取所有的sig group
        i_sig_group_triggering = self.find_tag_content(self.communication_package, "I-SIGNAL-GROUP")

        # 初始化空字典，用于存储 I-SIGNAL 到 I-PDU 的映射数据
        i_signal_to_i_pdu_map_data = {}

        # 初始化空字典，用于存储信号的详细数据
        sig_data = {}

        # 初始化空字典，用于存储信号到PDU的映射数据
        sig_2_pdu = {}

        # 初始化空字典，用于存储信号触发数据
        i_sig_triggering_data = {}

        # 遍历所有信号触发定义（I-SIGNAL-TRIGGERING）
        for sig in i_sig_triggering:

            # # 如果信号触发定义中没有 I-SIGNAL-REF，跳过当前信号
            # if not sig.get("I-SIGNAL-REF"):
            #     continue
            #
            # # 从 I-SIGNAL-REF 中提取信号的引用，并存入 i_sig_triggering_data 字典
            # # SHORT-NAME 是信号触发的名称，I-SIGNAL-REF 是信号的引用路径
            # i_sig_triggering_data[sig['SHORT-NAME'].split("*")[0]] = sig['I-SIGNAL-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 如果信号触发定义中是I-SIGNAL-GROUP-REF，则提取信号组的name
            # 普通信号key对应的是str，信号组对应的是【】
            if sig.get("I-SIGNAL-GROUP-REF"):
                # 提取信号组名称
                sig_group_name = sig['I-SIGNAL-GROUP-REF']['#text'].rsplit("/", 1)[1].split("*")[0]
                # 提取信号组中的所有信号名称
                sig_group_sig_lists = self.handle_sig_group(sig_group_name, i_sig_group_triggering)
                # 遍历信号组中的信号
                sig_group = []
                for sig_name in sig_group_sig_lists:
                    sig_group.append(sig_name.split("*")[0])
                i_sig_triggering_data[sig['SHORT-NAME'].split("*")[0]] = sig_group

            # 如果信号触发定义中是I-SIGNAL-GROUP-REF，则提取信号组的name
            if sig.get("I-SIGNAL-REF"):
                # 从 I-SIGNAL-REF 中提取信号的引用，并存入 i_sig_triggering_data 字典
                # SHORT-NAME 是信号触发的名称，I-SIGNAL-REF 是信号的引用路径
                i_sig_triggering_data[sig['SHORT-NAME'].split("*")[0]] = \
                sig['I-SIGNAL-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

        # 遍历所有 I-SIGNAL-I-PDU 信息
        for i_pdu in i_signal_to_i_pdu:
            # 提取当前 PDU 中的 I-SIGNAL-TO-I-PDU-MAPPING 信息
            info = self.find_tag_content(i_pdu, 'I-SIGNAL-TO-I-PDU-MAPPING')

            # 如果没有找到映射信息，跳过当前 PDU
            if not info:
                continue

            # 处理单个信号的情况，取第一个映射信息的 START-POSITION（信号在PDU中的起始位置）
            # LSFri_E2E_PDU2

            if info[0].get("I-SIGNAL-GROUP-REF"):
                i_signal_to_i_pdu_map_data[i_pdu['SHORT-NAME'].split("*")[0]] = {
                    "start_position": 0,
                    "start_position_row": i_pdu['SHORT-NAME'].split("*")[1],
                    "byte_order": self.byte_order,
                }

            else:
                i_signal_to_i_pdu_map_data[i_pdu['SHORT-NAME'].split("*")[0]] = {
                    "start_position": int(info[0].get("START-POSITION").split("*")[0]),
                    "start_position_row": info[0].get("START-POSITION").split("*")[1],
                    "byte_order": info[0].get("PACKING-BYTE-ORDER").split("*")[0],

                }
                self.byte_order = info[0].get("PACKING-BYTE-ORDER").split("*")[0]

        # 调用 handle_signals 方法处理信号的详细数据
        # signals 是从通信包中提取的所有信号定义，sig_data 是存储信号详细信息的字典
        self.handle_signals(signals, sig_data)

        # 调用 handle_sig_2_pdu_mapping 处理筛选后的 sig_2_pdu_mapping
        self.handle_sig_2_pdu_mapping(signal_to_pdu_mappings, sig_2_pdu)

        # 返回处理后的数据：信号详细数据、信号到PDU的映射数据、信号触发数据和I-SIGNAL到I-PDU的映射数据
        return sig_data, sig_2_pdu, i_sig_triggering_data, i_signal_to_i_pdu_map_data

    def handle_sig_group(self, sig_group_name, i_sig_group_triggering):
        """
        提取指定信号组的所有 I-SIGNAL-REF 的最后一个名字
        :param sig_group_name: 信号组的名称 (如 "SWCM_E2E_PDU1")
        :param i_sig_group_triggering: 包含 <I-SIGNAL-GROUP> 块的结构化数据
        :return: 所有 I-SIGNAL-REF 的最后一个名字组成的列表
        """
        # 初始化存储结果的列表
        signal_names = []

        # 遍历 <I-SIGNAL-GROUP> 块，查找匹配的信号组
        for sig_group in i_sig_group_triggering:
            # 确保当前块包含 <SHORT-NAME> 标签并与 sig_group_name 匹配
            if sig_group.get("SHORT-NAME").split("*")[0] == sig_group_name:
                # 提取 <I-SIGNAL-REFS> 块
                i_signal_refs = sig_group.get("I-SIGNAL-REFS", {}).get("I-SIGNAL-REF", [])

                # 如果 <I-SIGNAL-REF> 是单个字典，则转换为列表
                if isinstance(i_signal_refs, dict):
                    i_signal_refs = [i_signal_refs]

                # 遍历每个 <I-SIGNAL-REF>，提取最后一个 "/" 后的部分
                for i_signal_ref in i_signal_refs:
                    if "#text" in i_signal_ref:
                        signal_name = i_signal_ref["#text"].rsplit("/", 1)[-1]
                        signal_names.append(signal_name)

                # 找到匹配的信号组后直接返回结果
                return signal_names

        # 如果未找到匹配的信号组，返回空列表
        return signal_names

    def handle_signal2(self):
        # 从通信包中提取所有 I-SIGNAL 信息（信号的定义）
        sig_data = {}
        signals = self.find_tag_content(self.communication_package, "I-SIGNAL")
        self.handle_signals(signals, sig_data)

        sig_2_pdu = {}
        sig_2_pdu_mapping = self.find_tag_content(self.communication_package, "I-SIGNAL-TO-I-PDU-MAPPING")

        # 调用 handle_sig_2_pdu_mapping 处理筛选后的 sig_2_pdu_mapping
        self.handle_sig_2_pdu_mapping(sig_2_pdu_mapping, sig_2_pdu)

        i_signal_group_map = {}
        i_signal_groups = self.find_tag_content(self.communication_package, "I-SIGNAL-GROUP")
        for i_signal_group in i_signal_groups:
            group_name = i_signal_group['SHORT-NAME']
            i_signal_refs = i_signal_group['I-SIGNAL-REFS']['I-SIGNAL-REF']
            for i_signal_ref in i_signal_refs:
                i_signal = i_signal_ref["#text"].rsplit("/", 1)[1]
                i_signal_group_map.setdefault(group_name, []).append({
                    "signal_name": i_signal,
                    "init_val": sig_data[i_signal]["init_val"],
                    "length": sig_data[i_signal]["length"],
                    "start_position": sig_2_pdu[i_signal]["start_position"],
                    "byte_order": sig_2_pdu[i_signal]["byte_order"]
                })

        i_sig_triggering_data = {}
        i_sig_triggering = self.find_tag_content(self.communication_cluster_package, "I-SIGNAL-TRIGGERING")
        # 遍历所有信号触发定义（I-SIGNAL-TRIGGERING）
        for sig in i_sig_triggering:
            sig_short_name = sig['SHORT-NAME']
            # 如果信号触发定义中没有 I-SIGNAL-REF，跳过当前信号
            if not sig.get("I-SIGNAL-REF"):
                i_sig_group_ref = sig['I-SIGNAL-GROUP-REF']['#text'].rsplit("/", 1)[1]
                i_sig_triggering_data[sig_short_name] = i_signal_group_map[i_sig_group_ref]
            else:
                # 从 I-SIGNAL-REF 中提取信号的引用，并存入 i_sig_triggering_data 字典
                # SHORT-NAME 是信号触发的名称，I-SIGNAL-REF 是信号的引用路径
                i_sig_ref = sig['I-SIGNAL-REF']['#text'].rsplit("/", 1)[1]
                i_sig_triggering_data[sig_short_name] = {
                    "signal_name": i_sig_ref,
                    "init_val": sig_data[i_sig_ref]["init_val"],
                    "length": sig_data[i_sig_ref]["length"],
                    "start_position": sig_2_pdu[i_sig_ref]["start_position"],
                    "byte_order": sig_2_pdu[i_sig_ref]["byte_order"]
                }

        return i_sig_triggering_data

    @staticmethod
    def handle_signals(signals, sig_data):
        """
        处理信号信息，将信号的长度、名称和初始值提取并存储到 sig_data 字典中。

        @param signals: 信号列表，包含每个信号的详细信息（如长度、初始值、系统信号引用等）。
        @param sig_data: 字典，用于存储处理后的信号数据，以信号的 SHORT-NAME 为键。
        @return: 无返回值，处理结果存储在 sig_data 字典中。
        """
        # 遍历信号列表，处理每个信号
        for sig in signals:
            # 提取信号的长度（LENGTH），并转换为整数
            length = int(sig['LENGTH'].split("*")[0])

            # 提取信号的初始值（INIT-VALUE），如果存在，则从 NUMERICAL-VALUE-SPECIFICATION 中获取 VALUE
            # 如果不存在初始值，则默认为 0
            init_val = int(sig['INIT-VALUE']['NUMERICAL-VALUE-SPECIFICATION']['VALUE'].split("*")[0]) if sig.get(
                "INIT-VALUE") else 0
            # 提取信号的系统信号名称（SYSTEM-SIGNAL-REF），通过 rsplit("/", 1)[1] 获取最后一级名称
            sig_name = sig['SYSTEM-SIGNAL-REF']['#text'].rsplit("/", 1)[1].split("*")[0]

            # 将信号的长度、名称和初始值存储到 sig_data 字典中
            # 使用信号的 SHORT-NAME 作为键
            sig_data[sig['SHORT-NAME'].split("*")[0]] = {
                "length": length,  # 信号的长度
                "length_row": sig['LENGTH'].split("*")[1],  # 信号的长度
                "signal_name": sig_name,  # 信号的名称
                "init_val": init_val  # 信号的初始值
            }

    def handle_sig_2_pdu_mapping(self, sig_2_pdu_mapping, sig_2_pdu):
        """
        处理信号到 PDU 的映射信息，并将结果存储到 sig_2_pdu 字典中。

        @param sig_2_pdu_mapping: 信号到 PDU 的映射列表（包含映射的详细信息）。
        @param sig_2_pdu: 字典，用于存储处理后的信号到 PDU 映射数据。
        @return: 无返回值，处理结果存储在 sig_2_pdu 字典中。
        """
        i_sig_group_triggering = self.find_tag_content(self.communication_package, "I-SIGNAL-GROUP")

        # 遍历所有信号到 PDU 的映射信息<I-SIGNAL-TO-I-PDU-MAPPING>
        for sig_2 in sig_2_pdu_mapping:
            # 如果是信号组
            if sig_2.get('I-SIGNAL-GROUP-REF'):
                # 从 'I-SIGNAL-GROUP-REF' 中提取信号名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
                group_name = sig_2.get('I-SIGNAL-GROUP-REF', {}).get('#text', "").rsplit("/", 1)[1].split("*")[0]
                # 实现函数，需要把group的每一个信号添加到sig_2_pdu
                self.get_sig_msg_group(group_name, i_sig_group_triggering, sig_2_pdu_mapping, sig_2_pdu)

            # 如果是信号
            if sig_2.get('I-SIGNAL-REF'):
                # 从 'I-SIGNAL-REF' 中提取信号名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
                name = sig_2.get('I-SIGNAL-REF', {}).get('#text', "").rsplit("/", 1)[1].split("*")[0]

                # 提取信号在 PDU 中的起始位置
                start_position = sig_2['START-POSITION'].split("*")[0]

                # 提取信号的字节序（PACKING-BYTE-ORDER）
                byte_order = sig_2['PACKING-BYTE-ORDER'].split("*")[0]

                # 将信号的起始位置和字节序存储到 sig_2_pdu 字典中，以信号名称为键
                sig_2_pdu[name] = {
                    "start_position": start_position,  # 信号在 PDU 中的起始位置
                    "start_position_row": sig_2['START-POSITION'].split("*")[1],
                    "byte_order": byte_order,  # 信号的字节序
                }

    def get_sig_msg_group(self, group_name, i_sig_group_triggering, sig_2_pdu_mapping, sig_2_pdu):
        # 获取信号组中所有的信号名称
        sig_group_name_list = self.handle_sig_group(group_name, i_sig_group_triggering)
        # 遍历信号组的信号名称
        for sig_name in sig_group_name_list:
            # 遍历所有的<I-SIGNAL-TO-I-PDU-MAPPING>
            for sig in sig_2_pdu_mapping:
                if not sig.get('I-SIGNAL-REF'):
                    continue
                # 从 'I-SIGNAL-REF' 中提取信号名称（通过 rsplit("/", 1)[1] 获取最后一级名称）
                name = sig.get('I-SIGNAL-REF', {}).get('#text', "").rsplit("/", 1)[1].split("*")[0]
                if name == sig_name.split("*")[0]:
                    sig_2_pdu[name] = {
                        "start_position": sig['START-POSITION'].split("*")[0],  # 信号在 PDU 中的起始位置
                        "start_position_row": sig['START-POSITION'].split("*")[1],
                        "byte_order": sig['PACKING-BYTE-ORDER'].split("*")[0],  # 信号的字节序
                    }

    def find_signal_info(self, sig_data, sig_2_pdu, sig_triggering_data, signal_list, i_signal_to_i_pdu_map_data,
                         pdu_ref_map):
        """
        查找信号相关信息，包括信号的触发信息、信号映射信息、信号周期等。

        @param sig_data: 字典，包含信号的详细数据（如信号名称、长度、起始位置等）。
        @param sig_2_pdu: 字典，映射信号到其所属的PDU（Protocol Data Unit）。
        @param sig_triggering_data: 字典，映射信号到其触发数据（Triggering Data）。
        @param signal_list: 列表，包含需要处理的信号名称。
        @param i_signal_to_i_pdu_map_data: 字典，I-SIGNAL到I-PDU的映射数据（未使用）。
        @param pdu_ref_map: 字典，映射PDU的引用信息，包含PDU的周期等信息。
        @return: 返回处理后的信号信息列表。
        """
        # 1.先找I-SIGNAL-MAPPING
        # 2.I-SIGNAL-TRIGGERING
        # 3.再找I-SIGNAL
        # 4.再找I-SIGNAL-TO-I-PDU-MAPPING
        # 信号分为单信号还是多信号

        # 初始化一个空列表，用于存储处理后的信号信息
        handle_signal_list = []

        # 如果信号列表中只有一个信号，直接调用单信号处理方法
        if len(signal_list) == 1:
            return self.find_single_signal_info(sig_data, sig_2_pdu, sig_triggering_data, signal_list,
                                                i_signal_to_i_pdu_map_data,
                                                pdu_ref_map)

        # 获取PDU的触发信息的短名称（假设pdu_ref_map的key是PDU的短名称）
        pdu_triggering_shortname = list(pdu_ref_map.keys())[0].split("*")[0]

        # 从PDU的短名称中提取周期时间（单位ms）
        # cycle_time = self.extract_period(pdu_triggering_shortname).split("*")[0]
        cycle_time = 0

        # 遍历信号列表中的每个信号
        for signal in signal_list:
            # 初始化一个空字典，用于存储当前信号的信息
            signal_info = {}

            # 检查当前信号是否在sig_triggering_data中
            if signal in sig_triggering_data:
                # 获取信号的触发引用（sig_ref）
                sig_ref = sig_triggering_data.get(signal)

                # 如果没有找到触发引用，跳过当前信号
                if not sig_ref:
                    continue

                if isinstance(sig_ref, list):
                    # 如果是列表，遍历每个引用并从 sig_data 中提取信息
                    for ref in sig_ref:
                        i_sig = sig_data[ref]
                        # 更新 signal_info
                        signal_info.update(i_sig)
                        signal_info.update(sig_2_pdu[ref])
                        # 将当前信号的信息添加到处理列表中
                        handle_signal_list.append(
                            [
                                signal_info["signal_name"],  # 信号名称
                                signal_info["start_position"],  # 信号在PDU中的起始位置
                                signal_info["length"],  # 信号的长度（位数）
                                0,  # 保留字段（默认为0）
                                signal_info["init_val"],  # 信号的初始值
                                0,  # 保留字段（默认为0）
                                cycle_time,  # 信号的周期时间（从PDU中提取）
                                0  # 保留字段（默认为0）
                            ]
                        )
                else:
                    # 从sig_data中获取信号的详细信息（通过sig_ref找到对应的信号数据）
                    i_sig = sig_data[sig_ref]
                    # 将信号的详细信息更新到signal_info字典中
                    signal_info.update(i_sig)
                    # 将信号到PDU的映射信息更新到signal_info字典中
                    signal_info.update(sig_2_pdu[sig_ref])

                    # 将当前信号的信息添加到处理列表中
                    handle_signal_list.append(
                        [
                            signal_info["signal_name"],  # 信号名称
                            signal_info["start_position"],  # 信号在PDU中的起始位置
                            signal_info["length"],  # 信号的长度（位数）
                            0,  # 保留字段（默认为0）
                            signal_info["init_val"],  # 信号的初始值
                            0,  # 保留字段（默认为0）
                            cycle_time,  # 信号的周期时间（从PDU中提取）
                            0  # 保留字段（默认为0）
                        ]
                    )

        # 返回处理后的信号信息列表
        return handle_signal_list

    def find_signal_info2(self, sig_data, sig_2_pdu, sig_triggering_data, signal_list, i_signal_to_i_pdu_map_data,
                          pdu_ref_map):
        """
        查找信号相关信息，包括信号的触发信息、信号映射信息、信号周期等。

        @param sig_data: 字典，包含信号的详细数据（如信号名称、长度、起始位置等）。
        @param sig_2_pdu: 字典，映射信号到其所属的PDU（Protocol Data Unit）。
        @param sig_triggering_data: 字典，映射信号到其触发数据（Triggering Data）。
        @param signal_list: 列表，包含需要处理的信号名称。
        @param i_signal_to_i_pdu_map_data: 字典，I-SIGNAL到I-PDU的映射数据（未使用）。
        @param pdu_ref_map: 字典，映射PDU的引用信息，包含PDU的周期等信息。
        @return: 返回处理后的信号信息列表。
        """
        # 1.先找I-SIGNAL-MAPPING
        # 2.I-SIGNAL-TRIGGERING
        # 3.再找I-SIGNAL
        # 4.再找I-SIGNAL-TO-I-PDU-MAPPING
        # 信号分为单信号还是多信号

        # 初始化一个空列表，用于存储处理后的信号信息
        handle_signal_list = []

        # 如果信号列表中只有一个信号，直接调用单信号处理方法
        if len(signal_list) == 1:
            return self.find_single_signal_info2(sig_data, sig_2_pdu, sig_triggering_data, signal_list,
                                                 i_signal_to_i_pdu_map_data,
                                                 pdu_ref_map)

        # 获取PDU的触发信息的短名称（假设pdu_ref_map的key是PDU的短名称）
        pdu_triggering_shortname = list(pdu_ref_map.keys())[0]

        # 从PDU的短名称中提取周期时间（单位ms）
        cycle_time = self.extract_period(pdu_triggering_shortname)

        # 遍历信号列表中的每个信号
        for signal in signal_list:
            # 初始化一个空字典，用于存储当前信号的信息
            signal_info = {}

            # 检查当前信号是否在sig_triggering_data中
            if signal.split("*")[0] in sig_triggering_data:

                # 获取信号的触发引用（sig_ref）
                sig_ref = sig_triggering_data.get(signal.split("*")[0])

                # 如果没有找到触发引用，跳过当前信号
                if not sig_ref:
                    continue

                # 从sig_data中获取信号的详细信息（通过sig_ref找到对应的信号数据）
                if isinstance(sig_ref, list):
                    # 如果是列表，遍历每个引用并从 sig_data 中提取信息
                    for ref in sig_ref:
                        i_sig = sig_data[ref]
                        # 更新 signal_info 或其他目标字典
                        signal_info.update(i_sig)
                        signal_info.update(sig_2_pdu[ref])
                        # 将当前信号的信息添加到处理列表中
                        handle_signal_list.append({
                            "ShortName": signal_info["signal_name"].split("*")[0] + "_group",
                            "ShortName_row": signal.split("*")[1],
                            "BitPosition": signal_info["start_position"],
                            "BitPosition_row": signal_info["start_position_row"],
                            "BitSize": signal_info["length"],
                            "BitSize_row": signal_info["length_row"],
                            "SignalInitValue": signal_info["init_val"],
                            "SignalInitValue_row": 0,
                            "cycle_time": cycle_time,
                            "byte_order": "BIG_ENDIAN" if signal_info[
                                                              'byte_order'] == "MOST-SIGNIFICANT-BYTE-FIRST" else "LITTLE_ENDIAN"
                        }

                        )
                else:
                    i_sig = sig_data[sig_ref]
                    # 将信号的详细信息更新到signal_info字典中
                    signal_info.update(i_sig)
                    # 将信号到PDU的映射信息更新到signal_info字典中
                    signal_info.update(sig_2_pdu[sig_ref])

                    # 将当前信号的信息添加到处理列表中
                    handle_signal_list.append({
                        "ShortName": signal_info["signal_name"].split("*")[0],
                        "ShortName_row": signal.split("*")[1],
                        "BitPosition": signal_info["start_position"],
                        "BitPosition_row": signal_info["start_position_row"],
                        "BitSize": signal_info["length"],
                        "BitSize_row": signal_info["length_row"],
                        "SignalInitValue": signal_info["init_val"],
                        "SignalInitValue_row": 0,
                        "cycle_time": cycle_time,
                        "byte_order": "BIG_ENDIAN" if signal_info[
                                                          'byte_order'] == "MOST-SIGNIFICANT-BYTE-FIRST" else "LITTLE_ENDIAN"
                    }

                    )

        # 返回处理后的信号信息列表
        return handle_signal_list

    def find_single_signal_info(self, sig_data, sig_2_pdu, sig_triggering_data, signal_list, i_signal_to_i_pdu_map_data,
                                pdu_ref_map):
        """
        查找单个信号的相关信息，包括信号的触发信息、信号映射信息、信号周期等。

        @param sig_data: 字典，包含信号的详细数据（如信号名称、长度、起始位置等）。
        @param sig_2_pdu: 字典，映射信号到其所属的PDU（Protocol Data Unit）。
        @param sig_triggering_data: 字典，映射信号到其触发数据（Triggering Data）。
        @param signal_list: 列表，包含需要处理的信号名称（此处假设只有一个信号）。
        @param i_signal_to_i_pdu_map_data: 字典，I-SIGNAL到I-PDU的映射数据，包含信号的起始位置。
        @param pdu_ref_map: 字典，映射PDU的引用信息，包含PDU名称及其周期等信息。
        @return: 返回包含信号信息的列表。
        """

        # 初始化一个空字典，用于存储当前信号的信息
        signal_info = {}

        # 初始化一个空列表，用于存储处理后的信号信息
        handle_signal_list = []

        # 获取信号列表中的第一个信号（此处假设 signal_list 只有一个信号）
        signal = signal_list[0]

        # 初始化周期时间为 0
        cycle_time = 0

        # 获取 PDU 的引用名称（假设 pdu_ref_map 的值是一个列表，取第一个元素）
        pdu_ref_name = list(pdu_ref_map.values())[0][0].split("*")[0]

        # 检查 PDU 引用名称是否存在于 I-SIGNAL-TO-I-PDU 映射数据中
        if pdu_ref_name in i_signal_to_i_pdu_map_data:
            # 如果存在，获取信号的起始位置
            signal_info['start_position'] = i_signal_to_i_pdu_map_data[pdu_ref_name]['start_position']
            signal_info['byte_order'] = i_signal_to_i_pdu_map_data[pdu_ref_name]['byte_order']

            # 提取 PDU 的周期时间（单位为 ms）
            cycle_time = self.extract_period(pdu_ref_name)

        # 检查信号是否存在于信号触发数据（sig_triggering_data）中
        if signal in sig_triggering_data:
            # 获取信号的触发引用（sig_ref）
            sig_ref = sig_triggering_data.get(signal)

            if isinstance(sig_ref, list):
                # 如果是列表，遍历每个引用并从 sig_data 中提取信息
                for ref in sig_ref:
                    i_sig = sig_data[ref]
                    signal_info.update(i_sig)
                    # 剔除无效数据
                    # 将当前信号的信息添加到处理列表中

                    handle_signal_list.append(
                        [
                            signal_info["signal_name"],  # 信号名称
                            signal_info["start_position"],  # 信号在 PDU 中的起始位置
                            signal_info["length"],  # 信号的长度（位数）
                            0,  # 保留字段（默认为 0）
                            signal_info["init_val"],  # 信号的初始值
                            0,  # 保留字段（默认为 0）
                            cycle_time,  # 信号的周期时间（从 PDU 中提取）
                            0  # 保留字段（默认为 0）
                        ]
                    )
            else:
                # 如果是单个引用（字符串）
                # 从信号数据（sig_data）中获取信号的详细信息
                i_sig = sig_data[sig_ref]
                # 将信号的详细信息更新到 signal_info 字典中
                signal_info.update(i_sig)

                # 剔除无效数据
                # 将当前信号的信息添加到处理列表中

                handle_signal_list.append(
                    [
                        signal_info["signal_name"],  # 信号名称
                        signal_info["start_position"],  # 信号在 PDU 中的起始位置
                        signal_info["length"],  # 信号的长度（位数）
                        0,  # 保留字段（默认为 0）
                        signal_info["init_val"],  # 信号的初始值
                        0,  # 保留字段（默认为 0）
                        cycle_time,  # 信号的周期时间（从 PDU 中提取）
                        0  # 保留字段（默认为 0）
                    ]
                )

        # 返回处理后的信号信息列表
        return handle_signal_list

    def find_single_signal_info2(self, sig_data, sig_2_pdu, sig_triggering_data, signal_list,
                                 i_signal_to_i_pdu_map_data,
                                 pdu_ref_map):
        """
        查找单个信号的相关信息，包括信号的触发信息、信号映射信息、信号周期等。

        @param sig_data: 字典，包含信号的详细数据（如信号名称、长度、起始位置等）。
        @param sig_2_pdu: 字典，映射信号到其所属的PDU（Protocol Data Unit）。
        @param sig_triggering_data: 字典，映射信号到其触发数据（Triggering Data）。
        @param signal_list: 列表，包含需要处理的信号名称（此处假设只有一个信号）。
        @param i_signal_to_i_pdu_map_data: 字典，I-SIGNAL到I-PDU的映射数据，包含信号的起始位置。
        @param pdu_ref_map: 字典，映射PDU的引用信息，包含PDU名称及其周期等信息。
        @return: 返回包含信号信息的列表。
        """

        # 初始化一个空字典，用于存储当前信号的信息
        signal_info = {}

        # 初始化一个空列表，用于存储处理后的信号信息
        handle_signal_list = []

        # 获取信号列表中的第一个信号（此处假设 signal_list 只有一个信号）
        signal = signal_list[0].split("*")[0]

        # 初始化周期时间为 0
        cycle_time = 0

        # 获取 PDU 的引用名称（假设 pdu_ref_map 的值是一个列表，取第一个元素）
        pdu_ref_name = list(pdu_ref_map.values())[0][0]

        # 检查 PDU 引用名称是否存在于 I-SIGNAL-TO-I-PDU 映射数据中
        if pdu_ref_name in i_signal_to_i_pdu_map_data:
            # 如果存在，获取信号的起始位置
            signal_info['start_position'] = i_signal_to_i_pdu_map_data[pdu_ref_name]['start_position']
            signal_info['start_position_row'] = i_signal_to_i_pdu_map_data[pdu_ref_name]['start_position_row']
            signal_info['byte_order'] = i_signal_to_i_pdu_map_data[pdu_ref_name]['byte_order']

            # 提取 PDU 的周期时间（单位为 ms）
            cycle_time = self.extract_period(pdu_ref_name)

        # 检查信号是否存在于信号触发数据（sig_triggering_data）中
        if signal in sig_triggering_data:
            # 获取信号的触发引用（sig_ref）
            sig_ref = sig_triggering_data.get(signal)

            if isinstance(sig_ref, list):
                # 如果是列表，遍历每个引用并从 sig_data 中提取信息
                for ref in sig_ref:
                    i_sig = sig_data[ref]
                    signal_info.update(i_sig)
                    signal_info.update(sig_2_pdu[ref])
                    handle_signal_list.append(
                        {
                            "ShortName": signal_info["signal_name"] + "_group",
                            # "name_row": signal.split("*")[1],
                            "ShortName_row": signal_list[0].split("*")[1],
                            "BitPosition": signal_info["start_position"],
                            "BitPosition_row": signal_info["start_position_row"],
                            "BitSize": signal_info["length"],
                            "BitSize_row": signal_info["length_row"],
                            "SignalInitValue": signal_info["init_val"],
                            "SignalInitValue_row": 0,
                            "cycle_time": cycle_time,
                            "byte_order": "BIG_ENDIAN" if signal_info[
                                                              'byte_order'] == "MOST-SIGNIFICANT-BYTE-FIRST" else "LITTLE_ENDIAN"
                        }
                    )
            else:
                # 如果是单个引用（字符串）
                # 从信号数据（sig_data）中获取信号的详细信息
                i_sig = sig_data[sig_ref]
                # 将信号的详细信息更新到 signal_info 字典中
                signal_info.update(i_sig)

                # 剔除无效数据
                # 将当前信号的信息添加到处理列表中
                handle_signal_list.append(
                    {
                        "ShortName": signal_info["signal_name"],
                        # "name_row":signal.split("*")[1],
                        "ShortName_row": signal_list[0].split("*")[1],
                        "BitPosition": signal_info["start_position"],
                        "BitPosition_row": signal_info["start_position_row"],
                        "BitSize": signal_info["length"],
                        "BitSize_row": signal_info["length_row"],
                        "SignalInitValue": signal_info["init_val"],
                        "SignalInitValue_row": 0,
                        "cycle_time": cycle_time,
                        "byte_order": "BIG_ENDIAN" if signal_info[
                                                          'byte_order'] == "MOST-SIGNIFICANT-BYTE-FIRST" else "LITTLE_ENDIAN"
                    }
                )

        # 返回处理后的信号信息列表
        return handle_signal_list

    @staticmethod
    def extract_period(input_string):
        """
        从字符串中提取周期信息（以 ms 结尾的数字）。
        如果没有匹配到，返回 0。

        :param input_string: str，要解析的输入字符串
        :return: int，提取到的周期值（如果没有匹配到，返回 0）
        """
        # 使用正则表达式提取以 "ms" 结尾的数字
        pattern = r'(\d+)ms'
        match = re.search(pattern, input_string)

        # 如果匹配到，则返回数字；否则返回 0
        if match:
            return int(match.group(1))
        else:
            return 0

    def get_node_type(self, lin_cluster_name):
        master_contents = self.find_tag_content(self.ecu_instance_package, "LIN-MASTER")
        for content_data in master_contents:
            if content_data["SHORT-NAME"] in lin_cluster_name:
                return "master"
        return "slave"

    def extracting_lin_frame(self):
        """
        提取 LIN 的 message 并处理相关数据。

        @return: 返回一个字典，包含以下内容：
            1. LinIfFrame: LIN 帧的相关信息列表。
            2. LinIfScheduleTable: LIN 调度表的相关信息列表。
            3. LinIfEntry: LIN 调度表中条目的相关信息列表。
        """
        cluster_datas = []

        # 从通信集群包中查找所有的 LIN 帧触发器
        lin_clusters = self.dict_to_list(self.find_tag_content(self.communication_cluster_package, "LIN-CLUSTER"))

        for lin_cluster in lin_clusters:
            lin_cluster_name = lin_cluster["SHORT-NAME"]
            cluster_data = {
                "ShortName": lin_cluster_name,
                "NodeType": self.get_node_type(lin_cluster_name),
                "LinIfFrame": {},
                "LinIfScheduleTable": [],
            }
            # 1. 生成frame信息
            # 初始化帧映射字典，用于存储帧的相关信息
            frame_map = {}
            # 初始化发送帧的索引
            tx_index = 0
            # 初始化帧引用映射字典，用于存储帧短名称与帧名称的映射关系
            frame_ref_map = {}
            lin_frames = self.dict_to_list(self.find_tag_content(lin_cluster, "LIN-FRAME-TRIGGERING"))
            # 遍历所有的 LIN 帧信息
            for frame in lin_frames:
                # 提取帧的名称和端口引用
                ref_name = frame["FRAME-REF"]['#text'].rsplit("/", 1)[1]
                port_ref = self.find_tag_content(frame, 'FRAME-PORT-REF')[0]
                port_ref_name = port_ref['#text'].rsplit("/", 1)[1].lower()

                # 将帧短名称与帧名称的映射关系存储到 frame_ref_map 中
                frame_ref_map[frame["SHORT-NAME"]] = ref_name

                # 根据端口引用的方向（"out" 或其他）判断帧的发送或接收方向
                if "out" in port_ref_name:
                    # 如果是发送方向，生成发送 PDU 的引用名称
                    rx_pdu_ref = 'EcuC_Pub_DSTPDUID_o' + ref_name + '_' + str(int(frame["IDENTIFIER"]))

                    # 将发送帧的信息存储到 frame_map 中
                    frame_map[ref_name] = {
                        "LinIfFrameShortName": ref_name,  # 帧的短名称
                        "LinIfPid": int(frame["IDENTIFIER"]),  # 帧的标识符
                        "LinIfChecksumType": frame['LIN-CHECKSUM'],  # 帧的校验和类型
                        "LinIfPduDirectionShortName": "LinIfRxPdu",  # PDU 的方向短名称
                        "RxPduRef": "",  # 接收 PDU 的引用（发送帧不需要）
                        "TxPduId": tx_index,  # 发送 PDU 的 ID
                        "LinIfTxPduRef": rx_pdu_ref,  # 发送 PDU 的引用
                    }
                    # 增加发送帧的索引
                    tx_index += 1
                else:
                    # 如果是接收方向，生成接收 PDU 的引用名称
                    rx_pdu_ref = 'EcuC_Sub_PDUID_o' + ref_name + '_' + str(int(frame["IDENTIFIER"]))

                    # 将接收帧的信息存储到 frame_map 中
                    frame_map[ref_name] = {
                        "LinIfFrameShortName": ref_name,  # 帧的短名称
                        "LinIfPid": int(frame["IDENTIFIER"]),  # 帧的标识符
                        "LinIfChecksumType": frame['LIN-CHECKSUM'],  # 帧的校验和类型
                        "LinIfPduDirectionShortName": "LinIfRxPdu",  # PDU 的方向短名称
                        "RxPduRef": rx_pdu_ref,  # 接收 PDU 的引用
                        "TxPduId": "",  # 发送 PDU 的 ID（接收帧不需要）
                        "LinIfTxPduRef": "",  # 发送 PDU 的引用（接收帧不需要）
                    }
            cluster_data["LinIfFrame"] = frame_map
            # 2. 生成ScheduleTable、Entry信息
            # 提取调度表和条目信息
            schedule_tables_list = self.extracting_schedule_tables(lin_cluster, frame_ref_map)
            cluster_data["LinIfScheduleTable"] = schedule_tables_list
            cluster_datas.append(cluster_data)

        # 3. 更新frame信息
        # 从通信包中查找所有的 LIN 无条件帧，更新信息至帧信息
        lin_un_frames = self.find_tag_content(self.communication_package, "LIN-UNCONDITIONAL-FRAME")
        # 遍历所有的 LIN 无条件帧
        for frame in lin_un_frames:
            # 提取帧的短名称和长度
            name = frame["SHORT-NAME"]
            length = int(frame["FRAME-LENGTH"])

            # 更新 frame_map 中对应帧的长度信息
            for cluster_data in cluster_datas:
                frame_data = cluster_data["LinIfFrame"]
                if name in frame_data:
                    frame_data[name].update({
                        "LinIfLength": length,  # 帧的长度
                    })

        # 返回包含帧信息、调度表信息和条目信息的字典
        return cluster_datas

    def extracting_schedule_tables(self, lin_cluster, frame_ref_map):
        """
        提取 LIN 的 message 并处理相关数据。

        @param frame_ref_map: 一个字典，映射帧触发器的引用到具体的帧信息。
        @return: 返回两个列表：
            1. schedule_tables_list: 包含调度表的相关信息。
            2. entry_list: 包含调度表中每个条目的详细信息。
        """
        # 从通信集群包中查找所有的 LIN 调度表
        schedule_tables = self.find_tag_content(lin_cluster, "LIN-SCHEDULE-TABLE")

        # 初始化调度表列表，包含一个默认调度表
        schedule_tables_list = [{
            "LinIfScheduleTableShortName": "NULLSchedule",  # 调度表的短名称
            "LinIfResumePosition": "CONTINUE_AT_IT_POINT",  # 恢复位置，默认值为继续当前点
            "LinIfRunMode": "RUN_CONTINUOUS",  # 运行模式，默认值为连续运行
            "LinIfScheduleMode": "LINTP_APPLICATIVE_SCHEDULE",  # 调度模式，默认值为应用调度
            "LinIfScheduleTableIndex": 0,  # 调度表索引，默认值为0
            "LinIfEntrys": []
        }]

        # 初始化条目列表，用于存储调度表中的条目信息
        entry_list = []

        # 遍历所有的调度表
        for index, table in enumerate(schedule_tables):
            # 提取调度表的短名称和运行模式
            name = table['SHORT-NAME']
            run_mode = table['RUN-MODE']
            fmt_table_data = {
                "LinIfScheduleTableShortName": name,  # 当前调度表的短名称
                "LinIfResumePosition": "START_FROM_BEGINNING",  # 恢复位置，设置为从头开始
                "LinIfRunMode": run_mode,  # 当前调度表的运行模式
                "LinIfScheduleMode": "LINTP_APPLICATIVE_SCHEDULE",  # 调度模式，设置为应用调度
                "LinIfScheduleTableIndex": index + 1,  # 调度表索引，从1开始递增
                "LinIfEntrys": []
            }
            # 查找当前调度表中的所有条目
            entrys = self.find_tag_content(table, 'APPLICATION-ENTRY')

            # 遍历调度表中的条目
            for i, entry in enumerate(entrys):
                # 提取条目的延迟时间、在表中的位置以及帧触发器引用
                delay = entry['DELAY']
                position = entry['POSITION-IN-TABLE']
                trigger_ref = entry['FRAME-TRIGGERING-REF']['#text'].rsplit("/", 1)[1]

                # 将条目信息添加到条目列表中
                fmt_table_data["LinIfEntrys"].append({
                    "EntryShortName": f"ZCT_Lin1Schedule01_{i + 1}",  # 条目的短名称，格式化为调度表名称加索引
                    "LinIfDelay": delay,  # 条目的延迟时间
                    "LinIfEntryIndex": i,  # 条目的索引，从0开始递增
                    "LinIfFrameRef": frame_ref_map[trigger_ref],  # 条目关联的帧引用，从 frame_ref_map 中获取
                })
            # 将当前调度表的信息添加到调度表列表中
            schedule_tables_list.append(fmt_table_data)

        # 返回调度表列表和条目列表
        return schedule_tables_list

    def parse_lin_tp_config(self):
        # 构建LinTpChannel信息
        lintp_channels = self.find_tag_content(self.communication_package, "LIN-TP-CONFIG")
        lintp_channel_map = {}
        for lintp_channel in lintp_channels:
            lintp_channel_short_name = lintp_channel["SHORT-NAME"]
            communication_cluster_ref = lintp_channel["COMMUNICATION-CLUSTER-REF"]["#text"]
            fmt_communication_cluster_ref = communication_cluster_ref.rsplit("/", 1)[1]
            lintp_channel_map[lintp_channel_short_name] = {
                "short_name": lintp_channel_short_name,
                "channel_ref": fmt_communication_cluster_ref,
                "tp_address": {},
                "tp_nodes": {},
                "tp_connections": []
            }
            # 构建TP-ADDRESSS数据映射
            tp_addresss = self.dict_to_list(lintp_channel["TP-ADDRESSS"]["TP-ADDRESS"])
            for tp_address in tp_addresss:
                tp_address_short_name = tp_address["SHORT-NAME"]
                address = tp_address["TP-ADDRESS"]
                lintp_channel_map[lintp_channel_short_name]["tp_address"][tp_address_short_name] = {
                    "short_name": tp_address_short_name,
                    "address": address
                }
            # 构建TP-NODES数据映射
            tp_nodes = self.dict_to_list(lintp_channel["TP-NODES"]["LIN-TP-NODE"])
            for tp_node in tp_nodes:
                tp_node_short_name = tp_node["SHORT-NAME"]
                tp_address_ref = tp_node["TP-ADDRESS-REF"]["#text"]
                fmt_tp_address_ref = tp_address_ref.rsplit("/", 1)[1]
                lintp_channel_map[lintp_channel_short_name]["tp_nodes"][tp_node_short_name] = {
                    "short_name": tp_node_short_name,
                    "tp_address_ref": fmt_tp_address_ref
                }
            # 构建TP-CONNECTIONS数据映射
            tp_connections = self.dict_to_list(lintp_channel["TP-CONNECTIONS"]["LIN-TP-CONNECTION"])
            for tp_connection in tp_connections:
                data_pdu_ref = tp_connection["DATA-PDU-REF"]["#text"].rsplit("/", 1)[1]
                lin_tp_n_sdu_ref = tp_connection["LIN-TP-N-SDU-REF"]["#text"].rsplit("/", 1)[1]
                receiver_ref = tp_connection["RECEIVER-REFS"]["RECEIVER-REF"]["#text"].rsplit("/", 1)[1]
                transmitter_ref = tp_connection["TRANSMITTER-REF"]["#text"].rsplit("/", 1)[1]
                timeout_as = tp_connection["TIMEOUT-AS"]
                timeout_cr = tp_connection["TIMEOUT-CR"]
                timeout_cs = tp_connection["TIMEOUT-CS"]
                lintp_channel_map[lintp_channel_short_name]["tp_connections"].append({
                    "data_pdu_ref": data_pdu_ref,
                    "lin_tp_n_sdu_ref": lin_tp_n_sdu_ref,
                    "receiver_ref": receiver_ref,
                    "transmitter_ref": transmitter_ref,
                    "timeout_as": timeout_as,
                    "timeout_cr": timeout_cr,
                    "timeout_cs": timeout_cs,
                })
        # 构建PDU-TRIGGERING信息
        pdu_triggerings = self.find_tag_content(self.communication_cluster_package, "PDU-TRIGGERING")
        pdu_triggering_map = {}
        for pdu_triggering in pdu_triggerings:
            pdu_triggering_short_name = pdu_triggering["SHORT-NAME"]
            i_pdu_ref = pdu_triggering["I-PDU-REF"]["#text"]
            fmt_i_pdu_ref = i_pdu_ref.rsplit("/", 1)[1]
            pdu_triggering_map[fmt_i_pdu_ref] = {
                "i_pdu_ref": fmt_i_pdu_ref,
                "pdu_triggering_short_name": pdu_triggering_short_name
            }
        # 构建LIN-FRAME-TRIGGERING信息
        lin_frame_triggerings = self.find_tag_content(self.communication_cluster_package, "LIN-FRAME-TRIGGERING")
        lin_frame_triggering_map = {}
        for lin_frame_triggering in lin_frame_triggerings:
            frame_port_ref = lin_frame_triggering["FRAME-PORT-REFS"]["FRAME-PORT-REF"]["#text"]
            fmt_frame_port_ref = frame_port_ref.rsplit("/", 1)[1]
            frame_ref = lin_frame_triggering["FRAME-REF"]["#text"]
            fmt_frame_ref = frame_ref.rsplit("/", 1)[1]
            pdu_triggering_ref = \
                lin_frame_triggering["PDU-TRIGGERINGS"]["PDU-TRIGGERING-REF-CONDITIONAL"]["PDU-TRIGGERING-REF"]["#text"]
            fmt_pdu_triggering_ref_name = pdu_triggering_ref.rsplit("/", 1)[1]
            identifier = int(lin_frame_triggering["IDENTIFIER"])
            lin_frame_triggering_map[fmt_pdu_triggering_ref_name] = {
                "pdu_triggering_ref_name": fmt_pdu_triggering_ref_name,
                "frame_port_ref": fmt_frame_port_ref,
                "frame_ref": fmt_frame_ref,
                "identifier": identifier
            }
        # 构建DCM-I-PDU数据
        dcm_i_pdus = self.find_tag_content(self.communication_package, "DCM-I-PDU")
        dcm_i_pdu_map = {}
        for dcm_i_pdu in dcm_i_pdus:
            dcm_i_pdu_short_name = dcm_i_pdu["SHORT-NAME"]
            pdu_length = dcm_i_pdu["LENGTH"]
            dcm_i_pdu_map[dcm_i_pdu_short_name] = pdu_length

        # 构建数据
        channel_configs = []
        rx_nsdus = []
        tx_nsdus = []
        for channel_name, channel_data in lintp_channel_map.items():
            channel_configs.append({
                "short_name": channel_data["short_name"],
                "channel_ref": channel_data["channel_ref"]
            })
            for tp_connection in channel_data["tp_connections"]:
                data_pdu_ref = tp_connection["data_pdu_ref"]
                pdu_triggering_data = pdu_triggering_map[data_pdu_ref]
                pdu_triggering_short_name = pdu_triggering_data["pdu_triggering_short_name"]
                lin_frame_triggering_data = lin_frame_triggering_map[pdu_triggering_short_name]
                frame_port_ref = lin_frame_triggering_data["frame_port_ref"]
                lin_tp_n_sdu_ref = tp_connection["lin_tp_n_sdu_ref"]
                timeout_cr = tp_connection["timeout_cr"]
                timeout_as = tp_connection["timeout_as"]
                timeout_cs = tp_connection["timeout_cs"]
                transmitter_ref = tp_connection["transmitter_ref"]
                tp_address_ref = channel_data["tp_nodes"][transmitter_ref]["tp_address_ref"]
                tp_address = channel_data["tp_address"][tp_address_ref]["address"]
                if frame_port_ref.lower().rsplit("_")[1] == "in":
                    rx_nsdus.append({
                        "short_name": lin_tp_n_sdu_ref,
                        "channel_name": channel_name,
                        "dl": dcm_i_pdu_map[lin_tp_n_sdu_ref],
                        "ncr": timeout_cr,
                        "channel_ref": channel_data["channel_ref"],
                        "nad": tp_address,
                        "frame_name": lin_frame_triggering_data["frame_ref"],
                        "frame_id": lin_frame_triggering_data["identifier"],
                    })
                else:
                    tx_nsdus.append({
                        "short_name": lin_tp_n_sdu_ref,
                        "channel_name": channel_name,
                        "nas": timeout_as,
                        "ncs": timeout_cs,
                        "channel_ref": channel_data["channel_ref"],
                        "nad": tp_address,
                        "frame_name": lin_frame_triggering_data["frame_ref"],
                        "frame_id": lin_frame_triggering_data["identifier"],
                    })

        lin_tp_config = {
            "channel_configs": channel_configs,
            "rx_nsdus": rx_nsdus,
            "tx_nsdus": tx_nsdus,
        }
        return lin_tp_config

    def parse_doipint_config(self):
        channel_to_tp_sdu = {}
        tp_sdu_to_channel = {}
        can_tp_connections = self.find_tag_content(self.communication_package, "CAN-TP-CONNECTION")
        for can_tp_connection in can_tp_connections:
            tp_sdu_ref = can_tp_connection["TP-SDU-REF"]["#text"].rsplit("/", 1)[1]
            can_tp_channel_ref = can_tp_connection["CAN-TP-CHANNEL-REF"]["#text"].rsplit("/", 1)[1]
            tp_sdu_to_channel[tp_sdu_ref] = can_tp_channel_ref
            channel_to_tp_sdu.setdefault(can_tp_channel_ref, []).append(tp_sdu_ref)

        i_pdu_ref_to_name = {}
        name_to_i_pdu_ref = {}
        pdu_triggerings = self.find_tag_content(self.communication_cluster_package, "PDU-TRIGGERING")
        for pdu_triggering in pdu_triggerings:
            short_name = pdu_triggering["SHORT-NAME"]
            i_pdu_port_ref = pdu_triggering["I-PDU-PORT-REFS"]["I-PDU-PORT-REF"]["#text"].rsplit("/", 1)[1]
            i_pdu_ref = pdu_triggering["I-PDU-REF"]["#text"].rsplit("/", 1)[1]
            name_to_i_pdu_ref[short_name] = {
                "i_pdu_port_ref": i_pdu_port_ref,
                "i_pdu_ref": i_pdu_ref
            }
            i_pdu_ref_to_name[i_pdu_ref] = {
                "short_name": short_name,
                "i_pdu_port_ref": i_pdu_port_ref,
            }

        fmt_doip_connection = []
        doip_connections = self.find_tag_content(self.communication_package, "DO-IP-TP-CONNECTION")
        for doip_connection in doip_connections:
            source_address_ref = doip_connection["DO-IP-SOURCE-ADDRESS-REF"]["#text"].rsplit("/", 1)[1]
            target_address_ref = doip_connection["DO-IP-TARGET-ADDRESS-REF"]["#text"].rsplit("/", 1)[1]
            tp_sdu_ref = doip_connection["TP-SDU-REF"]["#text"].rsplit("/", 1)[1]
            fmt_doip_connection.append({
                "target_address_ref": target_address_ref,
                "source_address_ref": source_address_ref,
                "tp_sdu_ref": tp_sdu_ref
            })

        fmt_doip_logic_address_map = {}
        doip_logic_address = self.find_tag_content(self.communication_package, "DO-IP-LOGIC-ADDRESS")
        for doip_logic_address_data in doip_logic_address:
            fmt_doip_logic_address_map[doip_logic_address_data["SHORT-NAME"]] = doip_logic_address_data["ADDRESS"]

        res = {
            "channel_to_tp_sdu": channel_to_tp_sdu,
            "tp_sdu_to_channel": tp_sdu_to_channel,
            "i_pdu_ref_to_name": i_pdu_ref_to_name,
            "name_to_i_pdu_ref": name_to_i_pdu_ref,
            "doip_connections": fmt_doip_connection,
            "doip_logic_address_map": fmt_doip_logic_address_map
        }

        return res

    def parse_tcpip_config(self):
        fmt_ethernet_physical_channels = []
        ethernet_physical_channels = self.find_tag_content(self.communication_cluster_package,
                                                           "ETHERNET-PHYSICAL-CHANNEL")
        for ethernet_physical_channel in ethernet_physical_channels:
            short_name = ethernet_physical_channel["SHORT-NAME"]
            communication_connector_ref = \
                ethernet_physical_channel["COMM-CONNECTORS"]["COMMUNICATION-CONNECTOR-REF-CONDITIONAL"][
                    "COMMUNICATION-CONNECTOR-REF"]["#text"]
            fmt_communication_connector_ref = communication_connector_ref.rsplit("/", 1)[1]
            fmt_ethernet_physical_channels.append({
                "short_name": short_name,
                "communication_connector_ref": fmt_communication_connector_ref
            })

        fmt_vlan_memberships = {}
        vlan_memberships = self.find_tag_content(self.ecu_instance_package, "VLAN-MEMBERSHIP")
        for vlan_membership in vlan_memberships:
            default_priority = vlan_membership["DEFAULT-PRIORITY"]
            vlan_ref = vlan_membership["VLAN-REF"]["#text"]
            fmt_vlan_ref = vlan_ref.rsplit("/", 1)[1]
            fmt_vlan_memberships[fmt_vlan_ref] = default_priority

        fmt_ethernet_communication_connectors = []
        ethernet_communication_connectors = self.find_tag_content(self.ecu_instance_package,
                                                                  "ETHERNET-COMMUNICATION-CONNECTOR")
        for ethernet_communication_connector in ethernet_communication_connectors:
            short_name = ethernet_communication_connector["SHORT-NAME"]
            network_endpoint_refs = self.dict_to_list(
                ethernet_communication_connector["NETWORK-ENDPOINT-REFS"]["NETWORK-ENDPOINT-REF"])
            fmt_network_endpoint_refs = []
            for network_endpoint_ref in network_endpoint_refs:
                fmt_network_endpoint_ref = network_endpoint_ref["#text"].rsplit("/", 1)[1]
                fmt_network_endpoint_refs.append(fmt_network_endpoint_ref)
            fmt_ethernet_communication_connectors.append({
                "short_name": short_name,
                "network_endpoint_refs": fmt_network_endpoint_refs
            })

        fmt_multicast_connector_refs = []
        multicast_connector_refs = self.find_tag_content(self.communication_cluster_package, "MULTICAST-CONNECTOR-REF")
        for multicast_connector_ref in multicast_connector_refs:
            fmt_network_endpoint_ref = multicast_connector_ref["#text"].rsplit("/", 1)[1]
            fmt_multicast_connector_refs.append(fmt_network_endpoint_ref)

        fmt_network_endpoint = {}
        network_endpoints = self.find_tag_content(self.communication_cluster_package, "NETWORK-ENDPOINT")
        for network_endpoint in network_endpoints:
            short_name = network_endpoint["SHORT-NAME"]
            ipv_4_address = network_endpoint["NETWORK-ENDPOINT-ADDRESSES"]["IPV-4-CONFIGURATION"]["IPV-4-ADDRESS"]
            network_mask = network_endpoint["NETWORK-ENDPOINT-ADDRESSES"]["IPV-4-CONFIGURATION"].get("NETWORK-MASK", "")
            fmt_network_endpoint[short_name] = {
                "ipv_4_address": ipv_4_address,
                "network_mask": network_mask
            }

        res = {
            "ethernet_physical_channels": fmt_ethernet_physical_channels,
            "vlan_memberships": fmt_vlan_memberships,
            "ethernet_communication_connectors": fmt_ethernet_communication_connectors,
            "multicast_connector_refs": fmt_multicast_connector_refs,
            "network_endpoint": fmt_network_endpoint
        }
        return res

    def parse_soad_config(self):
        soad_config = {
            "SOCKET-CONNECTION-BUNDLE": self.find_tag_content(self.communication_cluster_package,
                                                              "SOCKET-CONNECTION-BUNDLE"),
            "SOCKET-ADDRESS": self.find_tag_content(self.communication_cluster_package, "SOCKET-ADDRESS"),
            "NETWORK-ENDPOINT": self.find_tag_content(self.communication_cluster_package, "NETWORK-ENDPOINT"),
        }
        return soad_config

    def parse_eth_config(self):
        can_frame_map = {}
        can_frame_data = self.find_tag_content(self.communication_package, "CAN-FRAME")
        for can_frame in can_frame_data:
            frame_length = can_frame["FRAME-LENGTH"]
            pdu_ref = can_frame['PDU-TO-FRAME-MAPPINGS']['PDU-TO-FRAME-MAPPING']['PDU-REF']['#text'].rsplit("/", 1)[1]
            can_frame_map[pdu_ref] = frame_length

        can_cluster_i_signal_triggering_map = {}
        can_cluster = self.find_tag_content(self.communication_cluster_package, "CAN-CLUSTER")
        pdu_triggerings = self.find_tag_content(can_cluster, "PDU-TRIGGERING")
        for pdu_triggering in pdu_triggerings:
            i_pdu_ref = pdu_triggering["I-PDU-REF"]["#text"].rsplit("/", 1)[1]
            i_signal_triggering_ref_list = self.find_tag_content(pdu_triggering, "I-SIGNAL-TRIGGERING-REF")
            for i_signal_triggering_ref in i_signal_triggering_ref_list:
                ref_name = i_signal_triggering_ref["#text"].rsplit("/", 1)[1]
                can_cluster_i_signal_triggering_map.setdefault(i_pdu_ref, []).append(ref_name)

        i_sig_triggering_data = self.handle_signal2()

        communication_connector_ref_map = {}
        ethernet_physical_channels = self.find_tag_content(
            self.communication_cluster_package['ELEMENTS']['ETHERNET-CLUSTER'], "ETHERNET-PHYSICAL-CHANNEL")
        for ethernet_physical_channel in ethernet_physical_channels:
            communication_connector_ref = \
                ethernet_physical_channel["COMM-CONNECTORS"]["COMMUNICATION-CONNECTOR-REF-CONDITIONAL"][
                    "COMMUNICATION-CONNECTOR-REF"]
            fmt_communication_connector_ref = communication_connector_ref["#text"].rsplit("/", 1)[1]
            pdu_triggerings = self.dict_to_list(ethernet_physical_channel["PDU-TRIGGERINGS"]["PDU-TRIGGERING"])
            for pdu_triggering in pdu_triggerings:
                short_name = pdu_triggering["SHORT-NAME"]
                i_pdu_port_ref = pdu_triggering["I-PDU-PORT-REFS"]["I-PDU-PORT-REF"]["#text"]
                fmt_i_pdu_port_ref = "in" if i_pdu_port_ref.rsplit("_", 1)[1].lower() == "in" else "out"
                i_pdu_ref = pdu_triggering["I-PDU-REF"]["#text"]
                fmt_i_pdu_ref = i_pdu_ref.rsplit("/", 1)[1]
                frame_length = can_frame_map.get(fmt_i_pdu_ref)
                if not frame_length:
                    continue
                pdu_triggering_data = {
                    "in_out": fmt_i_pdu_port_ref,
                    "cycle_time": self.extract_period(short_name),
                    "i_pdu_ref": fmt_i_pdu_ref,
                    "frame_length": frame_length,
                    "i_signal_triggering_ref_list": []
                }
                i_signal_triggering_ref_list = can_cluster_i_signal_triggering_map.get(fmt_i_pdu_ref, [])
                for i_signal_triggering_ref in i_signal_triggering_ref_list:
                    ref_i_signal_triggering = i_sig_triggering_data[i_signal_triggering_ref]
                    if isinstance(ref_i_signal_triggering, list):
                        pdu_triggering_data["i_signal_triggering_ref_list"].extend(ref_i_signal_triggering)
                    else:
                        pdu_triggering_data["i_signal_triggering_ref_list"].append(ref_i_signal_triggering)
                communication_connector_ref_map.setdefault(fmt_communication_connector_ref, []).append(
                    pdu_triggering_data)

        eth_config = {}
        for eth_data in self.data["eth"]:
            eth_short_name = eth_data["SHORT-NAME"]
            eth_config[eth_short_name] = communication_connector_ref_map.get(eth_short_name, [])

        return eth_config

    def parse_lin_config(self):
        i_sig_triggering_data = self.handle_signal2()

        lin_cluster_i_signal_triggering_map = {}
        lin_cluster = self.find_tag_content(self.communication_cluster_package, "LIN-CLUSTER")
        pdu_triggerings = self.find_tag_content(lin_cluster, "PDU-TRIGGERING")
        for pdu_triggering in pdu_triggerings:
            short_name = pdu_triggering["SHORT-NAME"]
            i_signal_triggering_ref_list = self.find_tag_content(pdu_triggering, "I-SIGNAL-TRIGGERING-REF")
            for i_signal_triggering_ref in i_signal_triggering_ref_list:
                ref_name = i_signal_triggering_ref["#text"].rsplit("/", 1)[1]
                lin_cluster_i_signal_triggering_map.setdefault(short_name, []).append(ref_name)

        lin_unconditional_frame_map = {}
        lin_unconditional_frames = self.find_tag_content(self.communication_package, "LIN-UNCONDITIONAL-FRAME")
        for lin_unconditional_frame in lin_unconditional_frames:
            frame_short_name = lin_unconditional_frame["SHORT-NAME"]
            frame_length = lin_unconditional_frame["FRAME-LENGTH"]
            lin_unconditional_frame_map[frame_short_name] = frame_length

        lin_cluster_map = {}
        lin_clusters = self.find_tag_content(self.communication_cluster_package, "LIN-CLUSTER")
        for lin_cluster in lin_clusters:
            lin_cluster_short_name = lin_cluster["SHORT-NAME"]
            lin_frame_triggerings = self.find_tag_content(lin_cluster, 'LIN-FRAME-TRIGGERING')
            for lin_frame_triggering in lin_frame_triggerings:
                short_name = lin_frame_triggering["SHORT-NAME"]
                frame_ref = lin_frame_triggering["FRAME-REF"]["#text"].rsplit("/", 1)[1]
                frame_port_ref = lin_frame_triggering["FRAME-PORT-REFS"]["FRAME-PORT-REF"]["#text"].rsplit("/", 1)[1]
                pdu_triggering_ref = \
                    lin_frame_triggering["PDU-TRIGGERINGS"]["PDU-TRIGGERING-REF-CONDITIONAL"]["PDU-TRIGGERING-REF"][
                        "#text"].rsplit("/", 1)[1]
                fmt_data = {
                    "frame_ref": frame_ref,
                    "frame_port_ref": frame_port_ref,
                    "in_out": "in" if frame_port_ref.rsplit("_", 1)[1].lower() == "in" else "out",
                    "cycle_time": self.extract_period(short_name),
                    "pdu_triggering_ref": pdu_triggering_ref,
                    "frame_length": lin_unconditional_frame_map[frame_ref],
                    "identifier": lin_frame_triggering["IDENTIFIER"],
                    "i_signal_triggering_ref_list": []
                }
                i_signal_triggering_ref_list = lin_cluster_i_signal_triggering_map.get(pdu_triggering_ref, [])
                for i_signal_triggering_ref in i_signal_triggering_ref_list:
                    ref_i_signal_triggering = i_sig_triggering_data[i_signal_triggering_ref]
                    if isinstance(ref_i_signal_triggering, list):
                        fmt_data["i_signal_triggering_ref_list"].extend(ref_i_signal_triggering)
                    else:
                        fmt_data["i_signal_triggering_ref_list"].append(ref_i_signal_triggering)

                lin_cluster_map.setdefault(lin_cluster_short_name, []).append(fmt_data)

        lin_communication_connector_map = {}
        lin_communication_connectors = self.find_tag_content(self.ecu_instance_package, "LIN-COMMUNICATION-CONNECTOR")
        for lin_communication_connector in lin_communication_connectors:
            comm_controller_ref = lin_communication_connector["COMM-CONTROLLER-REF"]["#text"].rsplit("/", 1)[1]
            lin_communication_connector_map[comm_controller_ref] = lin_cluster_map[comm_controller_ref]

        return lin_communication_connector_map

    def parse_msg_for_autotest(self, messages_info):
        """
        解析 autotest 所需要的数据
        @param messages_info:
        @return:
        """
        messages_info_new = {}
        for key in messages_info:
            if key != "input_arxml_path":
                messages_info_new[key] = messages_info[key]

        signal_data_list = []
        for ecu_name, message_map in messages_info_new.items():
            for dirs, messages in message_map.items():
                self.handle_signal_list(messages, signal_data_list, ecu_name, dirs)
        return signal_data_list

    @staticmethod
    def handle_signal_list(messages, signal_data_list, ecu_name, dirs):
        for message in messages:
            signal_list = message.get("signals")
            if not signal_list:
                continue
            for signal in signal_list:
                signal_data_list.append(
                    {
                        "signal_name": signal['ShortName'],
                        "message_name": message['msg_name'],
                        "ecu_name": ecu_name,
                        "start_bit": signal['BitPosition'],
                        "message_id": hex(int(message["msg_id"])),
                        "length": signal['BitSize'],
                        "message_length": message['msg_length'],
                        "direction": dirs.lower()
                    }
                )


def save_swc_data(file_path):
    start_time = time.perf_counter()
    logging.info(f"[performance test] 开始解析arxml")

    msg_data = parse_arxml_file_by_structure(file_path)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logging.info(f"[performance test] 解析arxml完成，耗时: {elapsed_time:.4f} 秒")

    from typing import Dict
    import json
    import os

    def get_knowledge(knowledge_file_path=None):
        try:
            # 构建knowledge.json文件的路径
            if not knowledge_file_path:
                knowledge_file_path = os.path.join(os.path.dirname(__file__), "resources", "knowledge.json")

            # 读取知识库文件
            with open(knowledge_file_path, 'r', encoding='utf-8') as f:
                knowledge_data = json.load(f)

            return knowledge_data
        except Exception as e:
            raise RuntimeError(f"Failed to fetch knowledge base: {e}")

    # 存储 trace_id 和 trace 信息的映射
    trace_info_map: Dict[str, dict] = {}

    requirement_metadata_template = {
        # "SummaryRequirementsTable": {},
        "RequirementsData": {
            "ECUConfiguration": {
                "EcuModel": {},
                "ClockAndPower": {},
                "MemoryMapping": {},
            },
            "CommunicationStack": {
                "Can": {},
                "Lin": {},
                "Eth": {},

                "GateWayConfiguration": {'SignalGateWay': {}, "PduGateWay": {}},
                "NetworkManagement": {},
            },
            "SystemServices": {
                "OS": {},
                "Wdg": {},
            },
            "RuntimeEnvironment": {
                "SWC": {},
                "Runnables": {},
                "Task": {},
            },
            "Diagnostic": {
                "CanDiag": {},
                "DcmDem": {},
            },
            "Storage": {
                "NvRamManager": {},
                "FeeEau": {},
            },
            "EcuAbstractionMCAL": {
                "Port": {},
                "DioAdcPwn": {},
                "SpiI2c": {},
                "Driver": {},
            },
            "CDD": {
                "SpecificSensorActuatorDriver": {},
                "Crypto": {},
                "Safety": {},
                "AVTP": [],
            },
        },
    }





    requirement_metadata = copy.deepcopy(requirement_metadata_template)
    com_module = requirement_metadata["RequirementsData"]["CommunicationStack"]
    com_module["Can"] = msg_data
    requirement_metadata["RequirementsData"]["Storage"]["NvRamManager"] = []
    requirement_metadata = {'AUTOSAR': requirement_metadata}

    parse_info_trace = transform_data(requirement_metadata)
    # if global_var.schema_mapping_flag:
    # make_show_data(parse_info_trace)

    # 深拷贝数据以避免修改原始对象
    processed_trace_data = copy.deepcopy(parse_info_trace)

    # 替换所有 trace 字段为 trace_id，并获取映射关系
    trace_id_map = replace_trace_with_id(processed_trace_data)

    # 将生成的 trace_id_map 合并到全局 trace_info_map 中
    trace_info_map.update(trace_id_map)

    # 准备保存到文件的数据（包含处理后的数据，其中 trace 已被替换为 trace_id）
    output_data = processed_trace_data

    output_dir = global_config.current_work_space['project_directory']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # 获取json输出路径
    arxml_requirement_metadata_file = os.path.join(
        output_dir,
        str(global_config.current_work_space['project_name']),
        "arxml_requirement_metadata_file.json"
    )
    global_config.previous_data['arxml_requirement_metadata_file'] = arxml_requirement_metadata_file
    # 写入json文件
    with open(arxml_requirement_metadata_file, 'w', encoding='utf-8') as f:
        f.write(ujson.dumps(output_data, ensure_ascii=False, indent=1))
    requirement_metadata_file_trace_map = os.path.join(
        output_dir,
        str(global_config.current_work_space['project_name']),
        "requirement_metadata_file_trace_map.json"
    )
    # 写入json文件
    with open(requirement_metadata_file_trace_map, 'w', encoding='utf-8') as f:
        f.write(ujson.dumps(trace_id_map, ensure_ascii=False, indent=1))


def transform_data(data):
    """
    递归遍历数据结构，将两两组合的键值对（如 "X" 和 "X_row"）转换为目标结构。
    @param data: 输入的字典或列表
    @param file_path: 文件路径
    @return: 转换后的数据
    """
    # 如果是字典
    if isinstance(data, dict):
        transformed = {}
        keys_to_remove = []  # 用于记录需要删除的 `_row` 键

        for key, value in data.items():
            # 检查是否存在与当前键配套的 `_row` 键
            row_key = f"{key}_row"
            src_key = f"{key}_src"
            if row_key in data:
                row_value = data[row_key]
                # 检查 row_value 是否是有效的数字
                if isinstance(row_value, int):  # 如果是整数，直接使用
                    row = row_value
                elif isinstance(row_value, str) and row_value.isdigit():  # 如果是数字字符串，转换为整数
                    row = int(row_value)
                else:
                    row = None  # 如果无效，设置为 None 或默认值

                current_data_src = ""
                if src_key in data:
                    current_data_src = data[src_key]
                    keys_to_remove.append(src_key)  # 记录 `_src` 键以便稍后移除
                # 构造目标结构
                transformed[key] = {
                    "value": value,
                    "trace": [
                        {
                            "file": current_data_src,
                            "row": row
                        }
                    ],
                    "type": "user"
                }
                keys_to_remove.append(row_key)  # 记录 `_row` 键以便稍后移除
            else:
                # 如果没有 `_row` 键，递归处理值
                transformed[key] = transform_data(value)

        # 删除已处理的 `_row` '_src' 键
        for row_key in keys_to_remove:
            del transformed[row_key]

        return transformed

    # 如果是列表，递归处理每个元素
    elif isinstance(data, list):
        return [transform_data(item) for item in data]

    # 如果是其他类型，直接返回
    else:
        return data


if __name__ == '__main__':
    file_path = r"D:\work\02-autosar-agent\01-doc\input\SWCMI.arxml"
    # parser = ExtractingARXML(r"D:\Users\kotei\Desktop\AI需求\can需求\canInput.arxml")
    parser = ExtractingARXMLPREH(file_path)
    # parser = ExtractingARXML(r"D:\leizi\A-work\AI-autosar\ZCT 25N3 20250403\Arxml\ZSDB225300_ZCT_AR-4.2.2_UnFlattened_V1_Swc_Fix.arxml")
    # data = parser.parse_tcpip_config()
    # data1 = parser.extracting_lin_frame()
    data = parser.extracting_can_msg2()
    # info = parser.parse_msg_for_autotest(data)
    # data = transform_data(data, file_path)
    # if global_var.schema_mapping_flag:
    #     make_show_data(data)
    # 指定 JSON 文件保存路径
    output_path = r"D:\work\02-autosar-agent\01-doc\input\output.json"

    # 将 data 输出到 JSON 文件
    with open(output_path, "w", encoding="utf-8") as json_file:
        # 使用 json.dump 格式化数据并写入文件
        ujson.dump(data, json_file, indent=4, ensure_ascii=False)
    pass





