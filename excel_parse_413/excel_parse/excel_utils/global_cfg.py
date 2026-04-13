import os
import time
from . import python_project_root
from .global_config_class import GlobalConfig

# 创建全局配置实例（会写在文件里）
global_config = GlobalConfig()


# 初始化全局配置数据（需要写在文件里的放在这里）
def init_global_config():
    global_config.base_ref_value_map = {}
    global_config.self_ref_map = {}

    # global_config.is_ori_summary_requirements_path = True
    # trcv_list
    global_config.trcv_list = []

    global_config.chat_id = ""

    # 自动化测试 日志路径
    global_config.auto_test_log_path = ""

    # 记录excel 异常的情景
    global_config.excel_exception_list = []

    # 解析开始时间
    global_config.parse_start_time = time.time()

    # 记录解析耗时
    global_config.spend_time = 0

    # 记录解析报错的堆栈信息
    global_config.parse_exception_dict = {}

    # 记录xdm输出路径（EB工具交互时使用）
    global_config.xdm_output_path = ""

    global_config.default_eb_config = {}
    global_config.default_eb_ct = 0
    global_config.srs_default_ct = 0
    global_config.srs_design_ct = 0

    # 执行任务记录 包括arxml/excel到srs的解析 srs到xdm的导出
    global_config.task_dict = {}

    # 当前执行的项目id
    global_config.project_id = ''

    # 当前执行的任务id
    global_config.current_task_id = ''

    # 当前执行的用户id
    global_config.user_id = ''

    global_config.file_type_info = {
        # "swc_path": [],
        # "swc_path": r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\A02-Y_纯电AB平台_CMX_CCU_V29.2(G3 G.0-1)-20251201_Result.xlsx"
        # 'arxml_path': r"D:\test\autosar agent\arxml_all\ZSDB225102_ZCT_AR-4.2.2_UnFlattened_V1_Com_Fix.arxml",
        # 'EcuC_base_xdm': r"D:\test\autosar agent\eb\base_xdm\EcuC_base.xdm",
        # 'CanSM_base_xdm': r"D:\test\autosar agent\eb\base_xdm\CanSM_4.6.0.xdm"
    }

    global_config.current_work_space = {'project_directory': os.path.join(python_project_root, "output_file"),
                                        "modules": 'all',
                                        "knowledge_file_path": os.path.join(python_project_root, "resources", "knowledge.json"),
                                        }

    # 记录大模型消耗的token总数
    global_config.llm_spend_token = {
        "arxml_parse": 0,  # 解析一次arxml消耗的总token
        "excel_parse": 0,  # 解析一次excel消耗的总token
    }

    # 定义通道名称的定位信息
    global_config.channel_trace_info = {}

    # 记录通道和节点的映射关系
    global_config.dbc_channel_node_map = {}

    # 工具间数据传递
    global_config.previous_data = {}

    global_config.parse_count = 0

    global_config.byte_order = 'Intel'
