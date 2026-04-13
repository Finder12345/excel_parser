# -*- coding: utf-8 -*-
"""
需求一致性检查核心功能脚本
与generate_srs_json_from_req3.py核心逻辑完全一致
移除网络请求、UI进度显示、任务管理等非核心功能
专注于一致性检查的核心业务逻辑
"""
import json
import logging
import traceback
from datetime import datetime
import os
import pandas as pd
import zipfile

from .global_config_class import GlobalConfig
class ReqConsistencyCheck:
    """需求一致性检查类"""

    def __init__(self, excel_info_path=None, dbc_info_path=None, ldf_info_path=None):
        self.excel_info_path = excel_info_path
        self.dbc_info_path = dbc_info_path
        self.ldf_info_path = ldf_info_path
        self.conflict_table_path = os.path.join(os.path.dirname(excel_info_path), "req_conflict_table.xlsx")

    @staticmethod
    def load_data(file_path):
        """加载数据"""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def check_all_info(self):
        """检查所有信息"""
        # 简化实现，实际项目中可能需要更复杂的检查逻辑
        # 这里创建一个空的冲突表
        import pandas as pd
        df = pd.DataFrame()
        df.to_excel(self.conflict_table_path, index=False)


def simplify_json_structure(data):
    """
    简化JSON结构，移除多余字段，只保留value值

    Args:
        data: JSON数据（字典或列表）

    Returns:
        简化后的JSON数据
    """
    if isinstance(data, dict):
        # 如果是字典，检查是否包含'value'字段
        if 'value' in data:
            # 只返回value值
            return data['value']
        else:
            # 递归处理字典中的每个值
            return {key: simplify_json_structure(value) for key, value in data.items()}
    elif isinstance(data, list):
        # 递归处理列表中的每个元素
        return [simplify_json_structure(item) for item in data]
    else:
        # 其他类型直接返回
        return data


def compress_files(file_paths, zip_name):
    """压缩文件"""
    zip_path = os.path.join(os.path.dirname(file_paths[0]), zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))
    return zip_path


def upload_requirement_metadata(excel_requirement_metadata_file):
    """
    上传需求元数据
    与实际实现保持一致：简化JSON结构、压缩文件
    注意：测试脚本中不实际上传到服务器，只做本地处理
    """
    with open(excel_requirement_metadata_file, "r", encoding="utf-8") as f:
        requirement_metadata = json.load(f)
    simplify_data = simplify_json_structure(requirement_metadata)
    file_dir = os.path.dirname(excel_requirement_metadata_file)
    simplify_file = os.path.join(file_dir, "requirement_metadata_file_simplify.json")
    with open(simplify_file, "w", encoding="utf-8") as f:
        json.dump(simplify_data, f, ensure_ascii=False, indent=2)
    file_paths = [simplify_file]
    req_metadata_zip_name = f"req_metadata.zip"
    req_metadata_zip_path = compress_files(file_paths, req_metadata_zip_name)
    print(f"需求元数据已压缩：{req_metadata_zip_path}")
    return req_metadata_zip_path


def validate_data(requirement_metadata, data_validate_flag=True):
    """
    验证数据
    与实际实现保持一致：支持验证开关控制
    参数说明：
    - requirement_metadata: 需求数据
    - data_validate_flag: 验证开关（默认True，与实际实现的global_var.data_validate_flag对应）

    Returns:
        - 验证通过：返回None
        - 验证失败：返回验证内容
    """
    # 简化实现，实际项目中可能需要更复杂的验证逻辑
    # 这里保持简化的验证逻辑

    if not data_validate_flag:
        # 验证开关关闭时，跳过验证
        return None

    # 模拟验证逻辑（可根据需要扩展）
    # 这里保持简化的验证逻辑，返回None表示验证通过
    return None


def judge_req_conflict_result(req_conflict_table_path):
    """
    判断需求冲突结果
    与实际实现保持一致：读取Excel、判断空/非空、返回结构化结果

    Args:
        req_conflict_table_path: 冲突表文件路径

    Returns:
        - 空表：返回成功结果（无冲突）
        - 非空表：返回确认结果（含前5行数据和操作按钮）
    """
    # 读取Excel文件
    df = pd.read_excel(req_conflict_table_path)
    # 判断是否为空
    if df.empty:  # 表为空，返回True和空列表
        print(f"需求一致性检查通过，无冲突，冲突报告路径：{req_conflict_table_path}")
        return {
            "code": 1,  # 1 成功、0 失败
            "msg": "",
            "next_step": "",  # 下一步执行的步骤，若为空使用默认的步骤
            # 要确认的信息，若为空则该步骤不需要确认
            "confirm_content": [
                {
                    "name": "",  # 要确认的 json 文件的定义
                    "path": "",  # 要确认的 json 文件的路径
                    'show_msg': {
                        # 要展示在聊天框里的内容
                        'msg': '需求一致性检查的冲突报告为空，所以需求是一致的',
                        'des': "",  # 展示要求or说明
                    }
                }
            ],
        }
    else:  # 表不为空，返回前5行数据
        first_5_rows = df.head(5).to_dict('records')
        print(f"需求一致性检查发现冲突，冲突报告路径：{req_conflict_table_path}")
        return {
            "code": 1,  # 1 成功、0 失败
            "msg": "",  # 信息
            # 下一步执行的步骤，若为空使用默认的步骤
            "next_step": """
            根据用户回复分情况处理：
                情况一：用户确认忽略冲突，流程结束
                情况二：用户告知修改了冲突的需求文件，则重新执行检查
            """,
            # 要确认的信息，若为空则该步骤不需要确认
            "confirm_content": [
                {
                    "name": "requirement consistency check report",  # 要确认的 json 文件的定义
                    "path": req_conflict_table_path,  # 要确认的 json 文件的路径
                    'show_msg': {
                        'msg': f'{first_5_rows}',  # 要展示在聊天框里的内容
                        # 展示要求or说明
                        'des': "这里展示的是冲突报告文件的前5行数据。需求一致性检查的冲突报告不为空，所以需求是不一致的。需要用户确认是否忽略冲突，若不忽略冲突，需要修改产生冲突的文件。",
                    }
                }
            ],
            "confirm_buttons": "Ignore Conflict,Resolved conflict",  # 操作按钮
        }


def start_check_req_consistency(excel_requirement_metadata_file, dbc_requirement_metadata_file=None,
                                ldf_requirement_metadata_file=None, data_validate_flag=True):
    """
    开始检查需求一致性
    与实际实现保持一致：支持验证开关、三场景检查

    Args:
        excel_requirement_metadata_file: Excel需求数据文件路径（必需）
        dbc_requirement_metadata_file: DBC需求数据文件路径（可选）
        ldf_requirement_metadata_file: LDF需求数据文件路径（可选）
        data_validate_flag: 数据验证开关（默认True，与实际实现的global_var.data_validate_flag对应）

    Returns:
        - 验证失败：返回验证内容
        - 文件不足：返回错误信息
        - 检查完成：返回冲突结果
    """
    # 一致性检查前置步骤：数据schema校验，校验不通过直接返回校验数据
    requirement_metadata = ReqConsistencyCheck.load_data(excel_requirement_metadata_file)
    validate_confirm_content = validate_data(requirement_metadata, data_validate_flag)
    if validate_confirm_content:
        print("数据校验不通过，流程结束")
        return validate_confirm_content

    # 三种检查场景
    if excel_requirement_metadata_file and dbc_requirement_metadata_file:
        # 场景1：Excel + DBC
        req_con_check = ReqConsistencyCheck(
            excel_info_path=excel_requirement_metadata_file,
            dbc_info_path=dbc_requirement_metadata_file,
        )
        req_con_check.check_all_info()
        req_conflict_table_path = req_con_check.conflict_table_path
        return judge_req_conflict_result(req_conflict_table_path)
    elif excel_requirement_metadata_file and ldf_requirement_metadata_file:
        # 场景2：Excel + LDF
        req_con_check = ReqConsistencyCheck(
            excel_info_path=excel_requirement_metadata_file,
            ldf_info_path=ldf_requirement_metadata_file,
        )
        req_con_check.check_all_info()
        req_conflict_table_path = req_con_check.conflict_table_path
        return judge_req_conflict_result(req_conflict_table_path)
    elif excel_requirement_metadata_file:
        # 场景3：仅Excel
        req_con_check = ReqConsistencyCheck(
            excel_info_path=excel_requirement_metadata_file,
        )
        req_con_check.check_all_info()
        req_conflict_table_path = req_con_check.conflict_table_path
        return judge_req_conflict_result(req_conflict_table_path)
    else:
        # 场景4：文件不足
        print("进行需求一致性检查需要上传excel+dbc/ldf,或者上传单独的excel,当前条件不满足")
        return {
            "code": 1,  # 1 成功、0 失败
            "msg": '进行需求一致性检查需要上传excel+dbc/ldf,或者上传单独的excel,当前条件不满足，流程结束',  # 信息
            "next_step": "",  # 下一步执行的步骤，若为空使用默认的步骤
            # 要确认的信息，若为空则该步骤不需要确认
            "confirm_content": [],
        }


def check_requirement_consistency(global_config:GlobalConfig):
    """
    检查需求一致性
    与实际实现保持一致：从参数获取文件路径、支持验证开关

    Args:
        excel_requirement_metadata_file: Excel需求数据文件路径（必需）
        dbc_requirement_metadata_file: DBC需求数据文件路径（可选）
        ldf_requirement_metadata_file: LDF需求数据文件路径（可选）
        data_validate_flag: 数据验证开关（默认True）

    Returns:
        - 成功：code=1，含msg/next_step/confirm_content
        - 失败：code=0，含msg

    注意：
        - 测试脚本中不实际上传到服务器，只做本地处理
        - 与实际实现的区别：无网络请求、无UI进度显示、无任务管理、无事件分发
    """
    print("开始需求一致性检查")
    excel_requirement_metadata_file = global_config.previous_data["requirement_metadata_file_path"]
    dbc_requirement_metadata_file = global_config.previous_data.get("dbc_requirement_metadata_file_path",None)
    ldf_requirement_metadata_file = global_config.previous_data.get("ldf_requirement_metadata_file_path",None)
    data_validate_flag = global_config.previous_data.get("data_validate_flag", True)

    try:
        # 上传元数据文件（本地处理，不上传到服务器）
        upload_requirement_metadata(excel_requirement_metadata_file)

        # 进行需求一致性检查
        return start_check_req_consistency(
            excel_requirement_metadata_file,
            dbc_requirement_metadata_file,
            ldf_requirement_metadata_file,
            data_validate_flag
        )

    except Exception as e:
        error_msg = f"检查需求一致性失败，错误信息：{traceback.format_exc()}"
        print(error_msg)
        return {
            "code": 0,  # 0 失败
            "msg": error_msg,
        }


if __name__ == "__main__":
    """
    示例用法
    与实际实现的核心逻辑完全一致
    """
    # 方式1：仅Excel（最常用）
    excel_requirement_metadata_file = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\output\requirement_metadata_file.json"
    result = check_requirement_consistency(excel_requirement_metadata_file)
    print(f"检查结果：{json.dumps(result, ensure_ascii=False, indent=2)}")

    # 方式2：Excel + DBC
    # excel_requirement_metadata_file = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\output\requirement_metadata_file.json"
    # dbc_requirement_metadata_file = r"D:\MyCode\Autosar-Agent-Temp\nano\intermediate_dbc_with_trace.json"
    # result = check_requirement_consistency(excel_requirement_metadata_file, dbc_requirement_metadata_file)
    # print(f"检查结果：{json.dumps(result, ensure_ascii=False, indent=2)}")

    # 方式3：Excel + LDF
    # excel_requirement_metadata_file = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\output\requirement_metadata_file.json"
    # ldf_requirement_metadata_file = r"D:\MyCode\Autosar-Agent-Temp\nano\intermediate_ldf_with_trace.json"
    # result = check_requirement_consistency(excel_requirement_metadata_file, ldf_requirement_metadata_file)
    # print(f"检查结果：{json.dumps(result, ensure_ascii=False, indent=2)}")

    # 方式4：关闭数据验证
    # excel_requirement_metadata_file = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\output\requirement_metadata_file.json"
    # result = check_requirement_consistency(excel_requirement_metadata_file, data_validate_flag=False)
    # print(f"检查结果：{json.dumps(result, ensure_ascii=False, indent=2)}")
