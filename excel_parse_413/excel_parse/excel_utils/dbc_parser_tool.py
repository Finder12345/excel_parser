import json
import os
import re
from pathlib import Path

import canmatrix
from langchain.tools import tool


class DbcParser(object):
    """
    解析 dbc 报文
    """

    def __init__(self):
        pass

    @staticmethod
    def parse(dbc_path):
        trace_info = DbcParser.parse_dbc_for_trace(dbc_path)
        db = DbcParser._load_dbc_file(dbc_path)

        dbname = Path(dbc_path).stem

        messages_info = {}
        for message in db.frames:
            message_info = DbcParser._create_message_info(message, dbc_path, trace_info)

            for signal in message.signals:
                signal_info = DbcParser._create_signal_info(signal, message.cycle_time, trace_info)
                message_info["signals"].append(signal_info)

            DbcParser._process_transmitters(message, message_info, messages_info)
            DbcParser._process_receivers(message, message_info, messages_info)

        return dbname, messages_info, trace_info

    @staticmethod
    def _load_dbc_file(dbc_path):
        db = canmatrix.formats.loadp(dbc_path)
        if isinstance(db, dict):
            db = list(db.values())[0]
        return db

    @staticmethod
    def _create_message_info(message, dbc_path, trace_info):
        attributes = message.attributes
        return {
            "__line_number__": trace_info.get("message", {}).get(f"{message.name}-{message.arbitration_id.id}"),
            "__file_path__": dbc_path,
            "name": message.name,
            "msg_name": message.name,
            "id": message.arbitration_id.id,
            "msg_id": message.arbitration_id.id,
            "length": message.size,
            "msg_length": message.size,
            "is_extended_frame": message.arbitration_id.extended,
            "is_fd": message.is_fd,
            "send_type": None,
            "signals": [],
            "msg_type": message.attributes.get('VFrameFormat', ""),
            "cycle_time": message.cycle_time,
            "attribute": DbcParser.get_message_attribute(attributes, message.name)
        }

    @staticmethod
    def _create_signal_info(signal, cycle_time, trace_info):
        return {
            "__line_number__": trace_info.get("signal", {}).get(f"{signal.name}", 0),
            "ShortName": signal.name,
            "BitPosition": signal.start_bit,
            "BitSize": signal.size,
            "is_signed": signal.is_signed,
            "factor": int(signal.factor) if hasattr(signal, 'factor') and signal.factor is not None else None,
            "offset": int(signal.offset) if hasattr(signal, 'offset') and signal.offset is not None else None,
            "unit": signal.unit,
            "SignalInitValue": int(signal.initial_value) if hasattr(signal,
                                                                    'initial_value') and signal.initial_value is not None else None,
            "cycle_time": cycle_time,
            "receivers": signal.receivers,
            "SignalEndianness": "LITTLE_ENDIAN" if signal.is_little_endian else "BIG_ENDIAN"
        }

    @staticmethod
    def _process_transmitters(message, message_info, messages_info):
        if hasattr(message, 'transmitters') and message.transmitters:
            for sender in message.transmitters:
                if sender not in messages_info:
                    messages_info[sender] = {}
                messages_info[sender].setdefault("TX", []).append(message_info)

    @staticmethod
    def _process_receivers(message, message_info, messages_info):
        if hasattr(message, 'receivers') and message.receivers:
            for receiver in message.receivers:
                if receiver not in messages_info:
                    messages_info[receiver] = {}
                messages_info[receiver].setdefault("RX", []).append(message_info)

    def parse_dbcs(self, dbc_config_list):
        msg_info = {}
        for dbc in dbc_config_list:
            dbname, messages_info, trace_info = self.parse(dbc['dbc_path'])
            node_name = dbc['node_name']
            channel = dbname
            data = messages_info.get(node_name)
            if not data:
                continue
            if not data.get("RX"):
                data['RX'] = []
            if not data.get('TX'):
                data["TX"] = []
            if channel in msg_info:
                existing_data = msg_info[channel]
                existing_data['RX'].extend(data.get('RX', []))
                existing_data['TX'].extend(data.get('TX', []))
            else:
                msg_info[channel] = data
        parse_info = {
            "AUTOSAR": {
                "RequirementsData": {
                    "CommunicationStack": {
                        "Can": msg_info,
                    }
                }
            }
        }
        return parse_info

    @staticmethod
    def get_delay_time(attributes):
        if attributes.get('GenMsgDelayTime') and attributes.get('GenMsgDelayTime').value:
            return attributes.get('GenMsgDelayTime').value // 1000
        return None

    @staticmethod
    def get_nr_reption(attributes):
        if attributes.get('GenMsgNrOfRepetition') and attributes.get('GenMsgNrOfRepetition').value:
            return attributes.get('GenMsgNrOfRepetition').value
        return None

    @staticmethod
    def get_msg_send_type(attributes):
        if attributes.get('GenMsgSendType', None):
            choices = attributes.get('GenMsgSendType', None).definition.choices
            value = attributes.get('GenMsgSendType', None).value
            return choices[value]
        return None

    @staticmethod
    def get_message_attribute(attributes, message_name):
        attribute = 'Normal'
        name = message_name.lower()
        if attributes.get('NmAsrMessage') and attributes.get('NmAsrMessage').value == 1:
            attribute = 'NmAsrMessage'
        if 'DiagState' in attributes or 'diagst' in name or 'allfunc' in name:
            attribute = 'DiagState'
        if 'DiagRequest' in attributes or 'diagreq' in name and 'allfunc' not in name:
            attribute = 'DiagRequest'
        if 'DiagResponse' in attributes or 'diagres' in name and 'allfunc' not in name:
            attribute = 'DiagResponse'
        if 'xcp' in name:
            attribute = 'Xcp'

        return attribute

    def parse_dbc_for_autotest(self, dbc_config_list):
        signal_data_list = []
        for dbc in dbc_config_list:
            dbname, messages_info, trace_info = self.parse(dbc['dbc_path'])
            for ecu_name, message_map in messages_info.items():
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
                        "signal_name": signal['name'],
                        "message_name": message['name'],
                        "ecu_name": ecu_name,
                        "start_bit": signal['start_bit'],
                        "message_id": hex(message["id"]),
                        "length": signal['length'],
                        "message_length": message['length'],
                        "direction": dirs.lower()
                    }
                )

    @staticmethod
    def parse_dbc_for_trace(file_path):
        trace_info = {
            "message": {},
            "signal": {},
            "db_name": {},
            "node": {}

        }
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        for line_number, line in enumerate(lines, start=1):
            line = line.strip()

            message_match = re.match(r'^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)', line)
            if message_match:
                message_id = message_match.group(1)
                message_name = message_match.group(2)
                trace_info['message'][f"{message_name}-{message_id}"] = line_number
                continue

            signal_match = re.match(r'^SG_\s+(\w+)', line)
            if signal_match:
                signal_name = signal_match.group(1)
                trace_info['signal'][f"{signal_name}"] = line_number

            ba_pattern = re.compile(r'^BA_\s+"DBName"\s+"(.*?)"\s*;')
            db_name_match = ba_pattern.search(line)
            if db_name_match:
                db_name = db_name_match.group(1)
                trace_info['db_name'][db_name] = line_number

            node_pattern = re.compile(r'^BU_:\s+(.*)$')
            node_match = node_pattern.search(line)
            if node_match:
                nodes = node_match.group(1).split()
                for node in nodes:
                    trace_info['node'][node] = line_number

        return trace_info

    @staticmethod
    def get_message_type(message):
        message_type_map = {
            (True, True): "EXTENDED_FD_CAN",
            (True, False): "EXTENDED_NO_FD_CAN",
            (False, True): "CANFDStandard",
            (False, False): "CANStandard",
        }
        is_extended = getattr(message, 'extended', False)
        is_fd = False

        return message_type_map.get((is_extended, is_fd), "CANStandard")


def parse_dbc_to_intermediate(dbc_path: str, node_names: list = ["CCU"]) -> dict:
    """
    解析DBC文件并生成带追溯信息的中间结果

    Args:
        dbc_path: DBC文件的绝对路径
        node_names: 要解析的节点名称列表

    Returns:
        包含数据库名称、报文信息和追溯信息的字典
    """
    dbname, messages_info, trace_info = DbcParser.parse(dbc_path)

    channel = dbname
    msg_info = {}
    for node_name, data in messages_info.items():
        if node_name not in node_names:
            continue
        if not data.get("RX"):
            data['RX'] = []
        if not data.get('TX'):
            data["TX"] = []
        if channel not in msg_info:
            msg_info[channel] = {"RX": [], "TX": []}
        msg_info[channel]['RX'].extend(data.get('RX', []))
        msg_info[channel]['TX'].extend(data.get('TX', []))

    parse_info = {
        "AUTOSAR": {
            "RequirementsData": {
                "CommunicationStack": {
                    "Can": msg_info,
                }
            }
        }
    }

    # parse_res  ={
    #             "name": "ldf requirement metadata",
    #             "path": parse_info,
    #         }

    dbc_file_path = Path(dbc_path)
    output_path = dbc_file_path.parent / "dbc_schema.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parse_info, f, ensure_ascii=False, indent=2, default=str)
    print(output_path)
    return output_path


def parse_dbc_list_to_intermediate(dbc_paths: list, node_names: list = ["CCU"]) -> dict:
    """
    解析多个DBC文件并生成带追溯信息的统一中间结果

    Args:
        dbc_paths: DBC文件的绝对路径列表
        node_names: 要解析的节点名称列表

    Returns:
        包含解析结果和输出文件路径的字典
    """
    combined_msg_info = {}

    for dbc_path in dbc_paths:
        dbname, messages_info, trace_info = DbcParser.parse(dbc_path)
        channel = dbname

        for node_name, data in messages_info.items():
            if node_name not in node_names:
                continue
            if not data.get("RX"):
                data['RX'] = []
            if not data.get('TX'):
                data["TX"] = []
            if channel not in combined_msg_info:
                combined_msg_info[channel] = {"RX": [], "TX": []}
            combined_msg_info[channel]['RX'].extend(data.get('RX', []))
            combined_msg_info[channel]['TX'].extend(data.get('TX', []))

    parse_info = {
        "AUTOSAR": {
            "RequirementsData": {
                "CommunicationStack": {
                    "Can": combined_msg_info,
                }
            }
        }
    }

    if dbc_paths:
        first_dbc_path = Path(dbc_paths[0])
        output_path = first_dbc_path.parent / "combined_dbc_schema.json"
    else:
        output_path = Path("../..") / "combined_dbc_schema.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parse_info, f, ensure_ascii=False, indent=2, default=str)
    print(output_path)
    return output_path


@tool
def parse_dbc_intermediate(dbc_path: str, node_names=["CCU"]) -> dict:
    """
    解析DBC文件，提取CAN报文和信号信息，生成带行号追溯的中间结果文件

    Args:
        dbc_path: DBC文件的绝对路径
        node_names: 要解析的节点名称列表

    Returns:
        包含解析结果和输出文件路径的字典
    """
    return parse_dbc_to_intermediate(dbc_path, node_names)


@tool
def parse_dbc_list_intermediate(dbc_paths: list, node_names=["CCU"]) -> dict:
    """
    解析多个DBC文件，提取CAN报文和信号信息，生成带行号追溯的统一中间结果文件

    Args:
        dbc_paths: DBC文件的绝对路径列表
        node_names: 要解析的节点名称列表

    Returns:
        包含解析结果和输出文件路径的字典
    """
    return parse_dbc_list_to_intermediate(dbc_paths, node_names)


if __name__ == "__main__":
    dbc_file_path = [
        r"D:\Projects\Agent_Autosar_Backend\data\CCU_CANFD1.dbc",
        r"D:\Projects\Agent_Autosar_Backend\data\CCU_CANFD3.dbc",
    ]
    node_list = ["CCU"]
    # result = parse_dbc_list_intermediate.invoke({"dbc_paths": dbc_file_path, "node_names": node_list})
    # print(f"Result: {result}")

    dbc_path = r"D:\Projects\Agent_Autosar_Backend\data\CCU_CANFD1.dbc"
    result2 = parse_dbc_intermediate.invoke({"dbc_path": dbc_path, "node_names": node_list})
    print(f"Result: {result2}")
    print(f"DBC解析完成")
