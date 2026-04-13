from typing import Dict
import openpyxl
from pathlib import Path
import os
import json
from . import python_project_root


class WorkbookParser:
    def __init__(self):
        self.workbook_data = {}

    def parse_excel(self, file_paths):
        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        for file_path in file_paths:
            if not os.path.exists(file_path):
                return
            if not file_path.endswith(('.xlsx', '.xls', '.xlsm')):
                continue
            if file_path in self.workbook_data:
                continue
            workbook = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
            self.workbook_data[file_path] = workbook

    def parse_and_get_single_excel(self, file_path):
        if not os.path.exists(file_path):
            return
        if not file_path.endswith(('.xlsx', '.xls', '.xlsm')):
            return
        if file_path in self.workbook_data:
            return self.workbook_data[file_path]

        workbook = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
        self.workbook_data[file_path] = workbook
        return workbook



wbparser = WorkbookParser()

support_route_type = ['LIN_to_CAN', 'LIN_to_ETH', 'CAN_to_LIN', 'CAN_to_CAN', 'LLCE', 'CAN_to_ETH', 'ETH_to_LIN',
                      'ETH_to_CAN', 'ETH_to_ETH', 'E2E_Message_Rebuild_Route']

schema_mapping_flag = True

data_validate_flag = True

# 创建全局变量字典（保存在内存里，不需要写在文件里的放在这里）
global_data = {}


def get_knowledge(knowledge_file_path=None):
    try:
        # 构建knowledge.json文件的路径 - 使用 python_project_root 而非硬编码
        if not knowledge_file_path:
            knowledge_file_path = Path(__file__).resolve().parent/"knowledge.json"

        # 如果文件不存在，返回默认知识库
        if not Path(knowledge_file_path).exists():
            return get_default_knowledge()

        # 读取知识库文件
        with open(knowledge_file_path, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)

        return knowledge_data
    except Exception:
        # 离线/本地运行允许缺失 knowledge.json；返回默认知识库
        return get_default_knowledge()


def get_default_knowledge():
    """返回默认知识库，与 generate0.py 中的 KnowledgeBase.get_default_knowledge 保持一致"""
    return {
        "sheet_info": {
            "can_routing": {
                "sheet_name_key_words": ["路由", "routing", "gateway"],
                "sheet_description": ["包含CAN消息路由信息的表格", "Gateway routing table"],
                "fields": {
                    "sourceSignalName": {"mapping_name": ["源信号名", "Source Signal Name", "Src Signal"]},
                    "sourcePduName": {"mapping_name": ["源PDU名", "Source PDU Name", "Src PDU"]},
                    "sourcePduId": {"mapping_name": ["源PDU ID", "Source PDU ID", "Src PDU ID"]},
                    "destinationSignalName": {"mapping_name": ["目标信号名", "Dest Signal Name", "Dst Signal"]},
                    "destinationPduName": {"mapping_name": ["目标PDU名", "Dest PDU Name", "Dst PDU"]},
                    "destinationPduId": {"mapping_name": ["目标PDU ID", "Dest PDU ID", "Dst PDU ID"]},
                    "routingType": {"mapping_name": ["路由类型", "Routing Type", "Route Type"]},
                    "isLLCE": {"mapping_name": ["是否LLCE", "LLCE", "Is LLCE"]},
                    "sourceChannelIdentifier": {"mapping_name": ["S"]},
                    "destinationChannelIdentifier": {"mapping_name": ["D"]},
                    "sourceDestinationChannelIdentifier": {"mapping_name": ["S/D"]},
                }
            },
            "can_signal": {
                "sheet_name_key_words": ["信号", "signal", "CAN"],
                "sheet_description": ["包含CAN信号定义的表格", "CAN signal definition table"]
            },
            "lin_signal": {
                "sheet_name_key_words": ["LIN", "lin"],
                "sheet_description": ["包含LIN信号定义的表格", "LIN signal definition table"]
            },
            "lin_schedule": {
                "sheet_name_key_words": ["调度", "schedule", "LIN"],
                "sheet_description": ["包含LIN调度信息的表格", "LIN schedule table"]
            },
            "nvm_block": {
                "sheet_name_key_words": ["NVM", "存储", "memory"],
                "sheet_description": ["包含存储配置信息的表格", "NVM configuration table"]
            }
        }
    }


kb = get_knowledge() # 初始化知识库


CAN_MODULE = "CAN"
LIN_MODULE = "LIN"
ETH_MODULE = "ETH"
NVM_MODULE = "NVM"
DIAG_MODULE = "DIAG"
input_modules = []

# 记录已生成的mentadata路径
file_save_dir_1 = ""
GLOBAL_CACHE: Dict[str, str] = {}
is_file_same = False
input_file_path = []

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

if __name__ == '__main__':
    excel_path = r"D:\\KoTEI_CODE\\Agent_Autosar_Backend\\data\\A02-Y_纯电AB平台_CMX_CCU_V29.2(G3 G.0-1)-20251201_Result.xlsx"

    wb = WorkbookParser()
    ans = wb.parse_and_get_single_excel(excel_path)
    print(ans)
