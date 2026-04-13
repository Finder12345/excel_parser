import json
import os
import re
import logging
from pathlib import Path

import ldfparser
from ldfparser.ldf import LDF
from ldfparser.schedule import LinFrameEntry, MasterRequestEntry, SlaveResponseEntry
from langchain.tools import tool


class EBLdfParser:
    def __init__(self):
        self.ldf_data_map = {}
        self.file_path = ""
        self.ldf = LDF()
        self.trace_info = {}

    @staticmethod
    def get_checksum_type(frame_id):
        if 0x00 <= frame_id <= 0x3b:
            return "ENHANCED"
        elif 0x3c <= frame_id <= 0x3d:
            return "CLASSIC"
        else:
            return "UNKNOWN"

    @staticmethod
    def get_pid(frame_id):
        pid_map = [
            0x80, 0xc1, 0x42, 0x03, 0xc4, 0x85, 0x06, 0x47, 0x08, 0x49, 0xca, 0x8b, 0x4c, 0x0d, 0x8e, 0xcf,
            0x50, 0x11, 0x92, 0xd3, 0x14, 0x55, 0xd6, 0x97, 0xd8, 0x99, 0x1a, 0x5b, 0x9c, 0xdd, 0x5e, 0x1f,
            0x20, 0x61, 0xe2, 0xa3, 0x64, 0x25, 0xa6, 0xe7, 0xa8, 0xe9, 0x6a, 0x2b, 0xec, 0xad, 0x2e, 0x6f,
            0xf0, 0xb1, 0x32, 0x73, 0xb4, 0xf5, 0x76, 0x37, 0x78, 0x39, 0xba, 0xfb, 0x3c, 0x7d, 0xfe, 0xbf,
            0x80, 0xc1, 0x42, 0x03, 0xc4, 0x85, 0x06, 0x47, 0x08, 0x49, 0xca, 0x8b, 0x4c, 0x0d, 0x8e, 0xcf,
            0x50, 0x11, 0x92, 0xd3, 0x14, 0x55, 0xd6, 0x97, 0xd8, 0x99, 0x1a, 0x5b, 0x9c, 0xdd, 0x5e, 0x1f,
            0x20, 0x61, 0xe2, 0xa3, 0x64, 0x25, 0xa6, 0xe7, 0xa8, 0xe9, 0x6a, 0x2b, 0xec, 0xad, 0x2e, 0x6f,
            0xf0, 0xb1, 0x32, 0x73, 0xb4, 0xf5, 0x76, 0x37, 0x78, 0x39, 0xba, 0xfb, 0x3c, 0x7d, 0xfe, 0xbf,
            0x80, 0xc1, 0x42, 0x03, 0xc4, 0x85, 0x06, 0x47, 0x08, 0x49, 0xca, 0x8b, 0x4c, 0x0d, 0x8e, 0xcf,
            0x50, 0x11, 0x92, 0xd3, 0x14, 0x55, 0xd6, 0x97, 0xd8, 0x99, 0x1a, 0x5b, 0x9c, 0xdd, 0x5e, 0x1f,
            0x20, 0x61, 0xe2, 0xa3, 0x64, 0x25, 0xa6, 0xe7, 0xa8, 0xe9, 0x6a, 0x2b, 0xec, 0xad, 0x2e, 0x6f,
            0xf0, 0xb1, 0x32, 0x73, 0xb4, 0xf5, 0x76, 0x37, 0x78, 0x39, 0xba, 0xfb, 0x3c, 0x7d, 0xfe, 0xbf,
            0x80, 0xc1, 0x42, 0x03, 0xc4, 0x85, 0x06, 0x47, 0x08, 0x49, 0xca, 0x8b, 0x4c, 0x0d, 0x8e, 0xcf,
            0x50, 0x11, 0x92, 0xd3, 0x14, 0x55, 0xd6, 0x97, 0xd8, 0x99, 0x1a, 0x5b, 0x9c, 0xdd, 0x5e, 0x1f,
            0x20, 0x61, 0xe2, 0xa3, 0x64, 0x25, 0xa6, 0xe7, 0xa8, 0xe9, 0x6a, 0x2b, 0xec, 0xad, 0x2e, 0x6f,
            0xf0, 0xb1, 0x32, 0x73, 0xb4, 0xf5, 0x76, 0x37, 0x78, 0x39, 0xba, 0xfb, 0x3c, 0x7d, 0xfe, 0xbf
        ]
        if frame_id >= len(pid_map):
            return ""
        return pid_map[frame_id]

    def _extract_trace_info(self, file_path):
        trace_info = {
            "message": {},
            "signal": {},
            'signal_start_position': {},
            "schedule_table": {},
            "node": {}
        }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            inside_nodes_section = False
            inside_signals_section = False
            inside_frames_section = False
            inside_schedule_section = False
            current_schedule_table = ''

            frame_ct = 0
            schedule_ct = 0

            for line_number, line in enumerate(lines, start=1):
                line = line.strip()

                if line.startswith("Nodes {"):
                    inside_nodes_section = True
                    continue

                elif line.startswith("Signals {"):
                    inside_signals_section = True
                    continue

                elif line.startswith("Frames {"):
                    inside_frames_section = True
                    continue
                elif line.startswith("Schedule_tables {"):
                    inside_schedule_section = True
                    continue

                elif line == "}":
                    frame_ct, inside_frames_section, inside_nodes_section, inside_schedule_section, inside_signals_section, schedule_ct = self.handle_end_point(
                        frame_ct, inside_frames_section, inside_nodes_section, inside_schedule_section,
                        inside_signals_section, schedule_ct)
                    continue

                self.handle_nodes_section(inside_nodes_section, line, line_number, trace_info)

                self.handle_signal_section(inside_signals_section, line, line_number, trace_info)

                frame_ct = self.handle_frame_section(frame_ct, inside_frames_section, line, line_number, trace_info)

                schedule_ct, current_schedule_table = self.handle_schedule_section(current_schedule_table,
                                                                                   inside_schedule_section, line,
                                                                                   line_number, schedule_ct, trace_info)

        except Exception as e:
            import traceback
            logging.error(traceback.format_exc())
            logging.error(f"Error parsing LDF file for trace: {e}")

        return trace_info

    def handle_end_point(self, frame_ct, inside_frames_section, inside_nodes_section, inside_schedule_section,
                         inside_signals_section, schedule_ct):
        if inside_nodes_section:
            inside_nodes_section = False
        elif inside_signals_section:
            inside_signals_section = False
        elif inside_frames_section:
            if frame_ct <= 0:
                inside_frames_section = False
            else:
                frame_ct -= 1
        elif inside_schedule_section:
            if schedule_ct <= 0:
                inside_schedule_section = False
            else:
                schedule_ct -= 1
        return frame_ct, inside_frames_section, inside_nodes_section, inside_schedule_section, inside_signals_section, schedule_ct

    def handle_schedule_section(self, current_schedule_table, inside_schedule_section, line, line_number, schedule_ct,
                                trace_info):
        if inside_schedule_section:
            schedule_match = re.match(r'^(\w+) {', line)
            if schedule_match:
                schedule_ct += 1
                schedule_table_name = schedule_match.group(1)
                trace_info['schedule_table'][schedule_table_name] = {}
                current_schedule_table = schedule_table_name
            frame_match = re.match(r'^(\w+) delay', line)
            if frame_match:
                frame_name = frame_match.group(1)
                trace_info['schedule_table'][current_schedule_table][frame_name] = line_number
        return schedule_ct, current_schedule_table

    def handle_frame_section(self, frame_ct, inside_frames_section, line, line_number, trace_info):
        if inside_frames_section:
            frame_match = re.match(r'^(\w+):', line)
            if frame_match:
                frame_ct += 1
                frame_name = frame_match.group(1)
                frame_id_match = re.match(r'^(\w+):\s*(\d+)', line)
                if frame_id_match:
                    frame_id = frame_id_match.group(2)
                    full_frame_key = f"{frame_name}-{frame_id}"
                    trace_info['message'][full_frame_key] = line_number
                    trace_info['message'][frame_name] = line_number
                else:
                    trace_info['message'][frame_name] = line_number
            signal_match = re.match(r'^(\w+),', line)
            if signal_match:
                signal_name = signal_match.group(1)
                trace_info['signal_start_position'][signal_name] = line_number
        return frame_ct

    def handle_signal_section(self, inside_signals_section, line, line_number, trace_info):
        if inside_signals_section:
            signal_match = re.match(r'^(\w+):', line)
            if signal_match:
                signal_name = signal_match.group(1)
                trace_info['signal'][signal_name] = line_number

    def handle_nodes_section(self, inside_nodes_section, line, line_number, trace_info):
        if inside_nodes_section:
            master_match = re.match(r'^Master:\s*(\w+)', line)
            if master_match:
                master_name = master_match.group(1)
                trace_info['node'][master_name] = line_number

            slaves_match = re.match(r'^Slaves:\s*(.*)', line)
            if slaves_match:
                slaves_text = slaves_match.group(1)
                slaves_text = slaves_text.rstrip(';')
                slave_names = [name.strip() for name in slaves_text.split(',')]
                for slave_name in slave_names:
                    if slave_name:
                        trace_info['node'][slave_name] = line_number

    def fmt_trace_data(self, value, row=None, trace_type="user"):
        res = {
            "value": value,
            "trace": [{"file": self.file_path, "row": row}],
            "type": trace_type
        }
        return res

    def parse_file(self, file_path, node_name):
        self.file_path = file_path
        self.trace_info = self._extract_trace_info(file_path)

        self.ldf = ldfparser.parse_ldf(path=file_path)
        channel_name = self.ldf.get_channel()
        if not channel_name:
            file_name_with_ext = os.path.basename(file_path)
            channel_name = os.path.splitext(file_name_with_ext)[0]

        if self.ldf.get_master().name == node_name:
            node_type = "master"
            node = self.ldf.get_master()
        else:
            node_type = "slave"
            node = self.ldf.get_slave(node_name)

        response_error = self.make_channel_data(channel_name, node, node_type)
        node_frame_names = self.get_node_frame_names(node)
        self.make_frame_data(channel_name, node_frame_names, node_name, node_type, response_error)

    def make_channel_data(self, channel_name, node, node_type):
        response_error = node.response_error.name if hasattr(node, "response_error") and node.response_error else ""
        self.ldf_data_map.setdefault(channel_name, {}).update({
            "channel_name": channel_name,
            "protocol_version": self.ldf.get_protocol_version(),
            "node_type": node_type,
            "configured_nad": node.configured_nad if hasattr(node, "configured_nad") else "",
            "function_id": node.product_id.function_id if hasattr(node, "product_id") and hasattr(node.product_id,
                                                                                                  "function_id") else "",
            "initial_nad": node.initial_nad if hasattr(node, "initial_nad") else "",
            "nas_timeout": node.n_as_timeout if hasattr(node, "n_as_timeout") else "",
            "supplier_id": node.product_id.supplier_id if hasattr(node, "product_id") and hasattr(node.product_id,
                                                                                                  "supplier_id") else "",
            "variant_id": node.product_id.variant if hasattr(node, "product_id") and hasattr(node.product_id,
                                                                                             "variant") else "",
            "response_error": response_error,
            "response_error_frame_name": "",
            "frames": []
        })
        return response_error

    def get_node_frame_names(self, node):
        if hasattr(node, "configurable_frames"):
            node_frame_names = [i.name for i in node.configurable_frames.values()] if node.configurable_frames else []
        else:
            node_frame_names = []
        return node_frame_names

    def make_frame_data(self, channel_name, node_frame_names, node_name, node_type, response_error):
        normal_frames = self.ldf.frames
        for normal_frame in normal_frames:
            frame_name = normal_frame.name
            if normal_frame._get_signal(response_error) if response_error else None:
                self.ldf_data_map[channel_name]["response_error_frame_name"] = frame_name

            if frame_name in node_frame_names or node_type == "master":
                frame_id = normal_frame.frame_id
                frame_line_number = self.trace_info["message"].get(f"{frame_name}-{frame_id}",
                                                                   self.trace_info["message"].get(frame_name))
                direction = "TX" if normal_frame.publisher.name == node_name else "RX"

                frame_data = {
                    "frame_name": self.fmt_trace_data(frame_name, frame_line_number, "user"),
                    "tx_rx": self.fmt_trace_data(direction, frame_line_number, "design"),
                    "frame_id": self.fmt_trace_data(frame_id, frame_line_number, "user"),
                    "frame_length": self.fmt_trace_data(normal_frame.length, frame_line_number, "user"),
                    "checksum_type": self.fmt_trace_data(self.get_checksum_type(frame_id), frame_line_number, "design"),
                    "pid": self.fmt_trace_data(self.get_pid(frame_id), frame_line_number, "design"),
                    "frame_type": self.fmt_trace_data("UNCONDITIONAL", trace_type="default"),
                    "signals": []
                }
                signals = normal_frame.signal_map
                for start_position, signal in signals:
                    signal_line_number = self.trace_info["signal"].get(signal.name)
                    start_position_line_number = self.trace_info["signal_start_position"].get(signal.name)

                    fmt_signal_data = {
                        "ShortName": self.fmt_trace_data(signal.name, signal_line_number, "user"),
                        "SignalInitValue": self.fmt_trace_data(signal.init_value, signal_line_number, "user"),
                        "BitSize": self.fmt_trace_data(signal.width, signal_line_number, "user"),
                        "BitPosition": self.fmt_trace_data(start_position, start_position_line_number, "user"),
                        "SignalEndianness": self.fmt_trace_data("BIG_ENDIAN", trace_type="default"),
                    }
                    frame_data["signals"].append(fmt_signal_data)

                self.ldf_data_map[channel_name]["frames"].append(frame_data)

    def parse_files(self, ldf_config_list):
        for ldf_data in ldf_config_list:
            self.parse_file(ldf_data["ldf_path"], ldf_data["node_name"])

    def parse_lin_tp_config(self):
        lin_tp_config = {
            "channel_configs": [],
            "rx_nsdus": [],
            "tx_nsdus": [],
        }
        return lin_tp_config

    def extracting_lin_frame(self):
        cluster_datas = []
        for channel_name, channel_data in self.ldf_data_map.items():
            fmt_data = {
                "ShortName": channel_name,
                "NodeType": channel_data["node_type"],
                "protocol_version": channel_data["protocol_version"],
                "configured_nad": channel_data["configured_nad"],
                "function_id": channel_data["function_id"],
                "initial_nad": channel_data["initial_nad"],
                "nas_timeout": channel_data["nas_timeout"],
                "supplier_id": channel_data["supplier_id"],
                "variant_id": channel_data["variant_id"],
                "response_error": channel_data["response_error"],
                "response_error_frame_name": "",
                "LinIfFrame": {},
                "LinIfScheduleTable": [],
            }
            for frame_data in channel_data["frames"]:
                frame_name = frame_data["frame_name"]
                frame_id = frame_data["frame_id"]
                tx_rx = frame_data["tx_rx"]
                frame_map = {}
                tx_index = 0
                if tx_rx == "Tx":
                    rx_pdu_ref = 'EcuC_Pub_DSTPDUID_o' + frame_name + '_' + str(int(frame_id))

                    frame_map[frame_name] = {
                        "LinIfFrameShortName": frame_name,
                        "LinIfPid": int(frame_id),
                        "LinIfChecksumType": frame_data["checksum_type"],
                        "LinIfPduDirectionShortName": "LinIfRxPdu",
                        "RxPduRef": "",
                        "TxPduId": tx_index,
                        "LinIfTxPduRef": rx_pdu_ref,
                        "LinIfLength": frame_data["frame_length"]
                    }
                    tx_index += 1
                else:
                    rx_pdu_ref = 'EcuC_Sub_PDUID_o' + frame_name + '_' + str(int(frame_id))

                    frame_map[frame_name] = {
                        "LinIfFrameShortName": frame_name,
                        "LinIfPid": int(frame_id),
                        "LinIfChecksumType": frame_data["checksum_type"],
                        "LinIfPduDirectionShortName": "LinIfRxPdu",
                        "RxPduRef": rx_pdu_ref,
                        "TxPduId": "",
                        "LinIfTxPduRef": "",
                        "LinIfLength": frame_data["frame_length"]
                    }
                fmt_data["LinIfFrame"] = frame_map
            cluster_datas.append(fmt_data)
        return cluster_datas

    def parse_schedule_tables(self):
        tables = self.ldf.get_schedule_tables()
        channel_name = self.ldf.get_channel()
        if not channel_name:
            file_name_with_ext = os.path.basename(self.file_path)
            channel_name = os.path.splitext(file_name_with_ext)[0]

        schedule_tables_data = {channel_name: {}}
        for table_data in tables:
            schedule_tables_data[channel_name][table_data.name] = []
            schedule_list = table_data.schedule
            for schedule_data in schedule_list:
                if isinstance(schedule_data, LinFrameEntry):
                    frame_name = schedule_data.frame.name
                elif isinstance(schedule_data, MasterRequestEntry):
                    frame_name = self.ldf.master_request_frame.name
                elif isinstance(schedule_data, SlaveResponseEntry):
                    frame_name = self.ldf.slave_response_frame.name
                else:
                    continue
                delay = schedule_data.delay
                frame_name_trace = self.fmt_trace_data(frame_name,
                                                       self.trace_info['schedule_table'].get(table_data.name, {}).get(
                                                           frame_name))
                delay_trace = self.fmt_trace_data(delay, self.trace_info['schedule_table'].get(table_data.name, {}).get(
                    frame_name))
                schedule_tables_data[channel_name][table_data.name].append(
                    {'frame_name': frame_name_trace, 'tans_time': str(delay_trace)})
        return schedule_tables_data

    def parse_lin_message_info(self):
        lin_communication_connector_map = {}
        for channel_name, channel_data in self.ldf_data_map.items():
            lin_communication_connector_map.setdefault(channel_name, {'RX': [], 'TX': []})
            frames = channel_data["frames"]
            for frame_data in frames:
                frame_name = frame_data["frame_name"]
                frame_id = frame_data["frame_id"]
                frame_length = frame_data["frame_length"]
                frame_type = frame_data["frame_type"]
                frame_pid = frame_data["pid"]
                tx_rx = frame_data["tx_rx"]
                fmt_data = {
                    "FrameName": frame_name,
                    "direction": tx_rx,
                    "FrameLength": frame_length,
                    "LinId": frame_id,
                    "FrameSendType": frame_type,
                    "ProtectedId": frame_pid,
                    "signals": frame_data["signals"]
                }
                lin_communication_connector_map[channel_name][tx_rx['value']].append(fmt_data)

        return lin_communication_connector_map


def parse_ldf_to_intermediate(ldf_path: str, node_names: list) -> dict:
    """
    解析LDF文件并生成带追溯信息的中间结果

    Args:
        ldf_path: LDF文件的绝对路径
        node_names: 要解析的节点名称列表

    Returns:
        包含LDF数据映射和调度表信息的字典
    """
    ldf_parser = EBLdfParser()
    ldf_parser.parse_files([
        {"ldf_path": ldf_path, "node_name": n} for n in node_names
    ])

    lin_signal_data_ldf = ldf_parser.parse_lin_message_info()
    lin_schedule_info_ldf = ldf_parser.parse_schedule_tables()

    requirement_metadata = {
        "AUTOSAR": {
            "RequirementsData": {
                "CommunicationStack": {
                    "Lin": {
                        "LinSignal": lin_signal_data_ldf,
                        "LinSchedule": lin_schedule_info_ldf
                    }
                }
            }
        }
    }

    # parse_res = {
    #         "name": "xdm requirement metadata",
    #         "path": requirement_metadata,
    #     }

    ldf_file_path = Path(ldf_path)
    output_path = ldf_file_path.parent / "ldf_schema.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(requirement_metadata, f, ensure_ascii=False, indent=2, default=str)

    return output_path


def parse_ldf_list_to_intermediate(ldf_paths: list, node_names: list = ["CCU"]) -> dict:
    """
    解析多个LDF文件并生成带追溯信息的统一中间结果

    Args:
        ldf_paths: LDF文件的绝对路径列表
        node_names: 要解析的节点名称列表

    Returns:
        包含LDF数据映射和调度表信息的字典
    """
    combined_lin_signal_data = {}
    combined_lin_schedule_info = {}

    for ldf_path in ldf_paths:
        ldf_parser = EBLdfParser()
        ldf_parser.parse_files([
            {"ldf_path": ldf_path, "node_name": n} for n in node_names
        ])

        lin_signal_data = ldf_parser.parse_lin_message_info()
        lin_schedule_info = ldf_parser.parse_schedule_tables()

        # 合并信号数据
        for channel, data in lin_signal_data.items():
            if channel not in combined_lin_signal_data:
                combined_lin_signal_data[channel] = {"RX": [], "TX": []}
            combined_lin_signal_data[channel]["RX"].extend(data.get("RX", []))
            combined_lin_signal_data[channel]["TX"].extend(data.get("TX", []))

        # 合并调度表数据
        for channel, tables in lin_schedule_info.items():
            if channel not in combined_lin_schedule_info:
                combined_lin_schedule_info[channel] = {}
            for table_name, table_data in tables.items():
                if table_name not in combined_lin_schedule_info[channel]:
                    combined_lin_schedule_info[channel][table_name] = []
                combined_lin_schedule_info[channel][table_name].extend(table_data)

    requirement_metadata = {
        "AUTOSAR": {
            "RequirementsData": {
                "CommunicationStack": {
                    "Lin": {
                        "LinSignal": combined_lin_signal_data,
                        "LinSchedule": combined_lin_schedule_info
                    }
                }
            }
        }
    }

    if ldf_paths:
        first_ldf_path = Path(ldf_paths[0])
        output_path = first_ldf_path.parent / "combined_ldf_schema.json"
    else:
        output_path = Path("../..") / "combined_ldf_schema.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(requirement_metadata, f, ensure_ascii=False, indent=2, default=str)

    return output_path


@tool
def parse_ldf_intermediate(ldf_path: str, node_names=["CCU"]) -> dict:
    """
    解析LDF文件，提取LIN帧和信号信息，生成带行号追溯的中间结果文件

    Args:
        ldf_path: LDF文件的绝对路径
        node_names: 要解析的节点名称列表

    Returns:
        包含解析结果和输出文件路径的字典
    """
    return parse_ldf_to_intermediate(ldf_path, node_names)


@tool
def parse_ldf_list_intermediate(ldf_paths: list, node_names=["CCU"]) -> dict:
    """
    解析多个LDF文件，提取LIN帧和信号信息，生成带行号追溯的统一中间结果文件

    Args:
        ldf_paths: LDF文件的绝对路径列表
        node_names: 要解析的节点名称列表

    Returns:
        包含解析结果和输出文件路径的字典
    """
    return parse_ldf_list_to_intermediate(ldf_paths, node_names)


if __name__ == "__main__":
    ldf_file_path = [r"D:\Projects\Agent_Autosar_Backend\data\LIN1.ldf"]

    ldf_path = r"D:\Projects\Agent_Autosar_Backend\data\LIN1.ldf"

    node_list = ["CCU"]
    result = parse_ldf_intermediate.invoke({"ldf_path": ldf_path, "node_names": node_list})
    # result2 = parse_ldf_list_intermediate.invoke({"ldf_paths": ldf_file_path, "node_names": node_list})
    print(f"Result: {result}")
    # print(f"Result2: {result2}")
    print(f"LDF解析完成")
