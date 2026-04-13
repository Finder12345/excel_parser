# -*- coding: utf-8 -*-
"""
Excel解析LangChain工具集

提供5个可被大模型调用的工具:
    1. excel_extract_sheet_range       - 阶段0: 解析Excel，识别路由/信号/NVM等sheet名称
    2. excel_extract_mapping_info      - 阶段1: 提取每个sheet的字段映射规则
    3. excel_generate_requirement_metadata - 阶段2: 生成AUTOSAR标准需求元数据
    4. excel_check_requirement_consistency - 阶段3: 需求一致性检查
    5. excel_full_parse                - 全流程: 串联阶段0~3一键完成

所有工具的输入/输出均为显式的文件路径（字符串），不依赖全局 config 传递中间状态。
核心逻辑完全复用 process_stage 下的 generate0~generate3。
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from core.data_config import middle_files_dir
from langchain.tools import tool

# ───────────── 核心阶段函数导入 ─────────────
# 兼容两种运行方式:
#   1. 作为包导入: from AutoSAR_Agent.tools.OMV_tools.parse_tool.move.excel_parse_tools import ...
#   2. 直接运行:   python excel_parse_tools.py
if __name__ == "__main__":
    # 直接运行时，将项目根目录加入 sys.path，使绝对导入可用
    _project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from tools.excel_utils.generate0 import (
        extract_sheet_range as _core_extract_sheet_range,
    )
    from tools.excel_utils.generate1 import (
        extract_mapping_info as _core_extract_mapping_info,
    )
    from tools.excel_utils.generate2 import (
        generate_requirement_metadata as _core_generate_requirement_metadata,
    )
    from tools.excel_utils.generate3 import (
        check_requirement_consistency as _core_check_requirement_consistency,
    )
    from tools.excel_utils.global_config_class import GlobalConfig
else:
    from .excel_utils.generate0 import (
        extract_sheet_range as _core_extract_sheet_range,
    )
    from .excel_utils.generate1 import (
        extract_mapping_info as _core_extract_mapping_info,
    )
    from .excel_utils.generate2 import (
        generate_requirement_metadata as _core_generate_requirement_metadata,
    )
    from .excel_utils.generate3 import (
        check_requirement_consistency as _core_check_requirement_consistency,
    )
    from .excel_utils.global_config_class import GlobalConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ───────────── 辅助函数: 构建 GlobalConfig ─────────────

def _build_config(
    excel_paths: Optional[List[str]] = None,
    output_dir: str = "",
    project_name: str = "default",
    previous_data: Optional[dict] = None,
) -> GlobalConfig:
    """
    根据显式参数构建 GlobalConfig 实例, 供核心函数使用。
    这样工具层只暴露路径参数, 内部转换为核心函数所需的 GlobalConfig。
    """
    cfg = GlobalConfig()

    # file_type_info
    if excel_paths:
        cfg.file_type_info = {"excel_path": list(excel_paths)}

    # current_work_space
    if output_dir:
        cfg.current_work_space = {
            "project_directory": output_dir,
            "project_name": project_name,
        }
    else:
        # 默认输出目录: 第一个Excel输入文件同级目录下的 output 文件夹
        if excel_paths:
            default_dir = str(Path(excel_paths[0]).resolve().parent / "output")
        else:
            default_dir = str(Path(__file__).resolve().parent / "output")
        cfg.current_work_space = {
            "project_directory": default_dir,
            "project_name": project_name,
        }

    # previous_data (阶段间传递的中间文件路径)
    if previous_data:
        for k, v in previous_data.items():
            cfg.previous_data[k] = v

    return cfg


def _ensure_output_dir(output_dir: str, project_name: str) -> str:
    """确保输出目录存在, 返回项目级输出目录路径。"""
    project_dir = os.path.join(output_dir, project_name)
    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
    return project_dir


# ═══════════════════════════════════════════════════════════
#  工具 1: 阶段0 — 解析Excel, 识别sheet名称
# ═══════════════════════════════════════════════════════════

@tool
def excel_extract_sheet_range(
    excel_paths: List[str],
    output_dir: str = str(Path(middle_files_dir).parent),  # data目录
    project_name: str = "middle_files",
) -> str:
    """
    【阶段0】解析Excel文件, 通过AI识别路由表sheet、CAN信号sheet、LIN信号/调度sheet、NVM sheet的名称。

    这是Excel解析全流程的第一步。输入待解析的Excel文件路径列表,
    AI会分析每个Excel的所有sheet名称, 智能识别出各模块（CAN路由、CAN信号、LIN信号、LIN调度、NVM）
    对应的sheet, 并将识别结果保存为JSON中间文件。

    Args:
        excel_paths: 待解析的Excel文件绝对路径列表。
                     支持 .xlsx / .xls / .xlsm 格式。
                     示例: ["D:/data/CMX_CCU_V29.xlsx", "D:/data/NVM_BlockList.xlsx"]
        output_dir:  中间结果输出目录的绝对路径。
                     若不传则默认为第一个Excel输入文件同级目录下的 output 文件夹。
        project_name: 项目名称, 会在 output_dir 下创建同名子目录。默认 "default"。

    Returns:
        生成的sheet识别结果JSON文件的绝对路径。
        该JSON包含 can_routing_data / can_signal_sheet_data /
        lin_signal_scheduler_data / nvm_data 四个字段。
        若失败返回包含 code=0 和 msg 的JSON字符串。
    """
    cfg = _build_config(
        excel_paths=excel_paths,
        output_dir=output_dir,
        project_name=project_name,
    )

    result = _core_extract_sheet_range(cfg)

    # 核心函数可能返回路径字符串(成功) 或 dict(失败)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


# ═══════════════════════════════════════════════════════════
#  工具 2: 阶段1 — 提取字段映射规则
# ═══════════════════════════════════════════════════════════

@tool
def excel_extract_mapping_info(
    sheet_range_json_path: str,
    output_dir: str = str(Path(middle_files_dir).parent),  # data目录
    project_name: str = "middle_files",
) -> str:
    """
    【阶段1】根据阶段0的sheet识别结果, 进一步提取每个sheet的字段映射规则(mapping info)。

    该阶段会读取阶段0输出的JSON文件, 对其中每个sheet调用AI分析表头结构,
    提取CAN路由表的行列映射、CAN/LIN信号表的字段与列名对应关系、NVM表的数据结构等。
    结果保存为 extract_params_info.json。

    Args:
        sheet_range_json_path: 阶段0输出的JSON文件路径
                               (即 extract_routing_data_and_signal_sheet_data.json 的绝对路径)。
        output_dir:  中间结果输出目录的绝对路径。
                     若不传则使用 sheet_range_json_path 所在目录的父目录。
        project_name: 项目名称, 会在 output_dir 下创建同名子目录。默认 "default"。

    Returns:
        生成的映射规则JSON文件 (extract_params_info.json) 的绝对路径。
        若失败返回包含 code=0 和 msg 的JSON字符串。
    """
    # 自动推断 output_dir
    if not output_dir:
        # sheet_range_json_path 一般在 output_dir/project_name/ 下
        output_dir = str(Path(sheet_range_json_path).resolve().parent.parent)
        project_name = Path(sheet_range_json_path).resolve().parent.name

    cfg = _build_config(
        output_dir=output_dir,
        project_name=project_name,
        previous_data={
            "extract_routing_data_and_signal_sheet_data": sheet_range_json_path,
        },
    )

    result = _core_extract_mapping_info(cfg)

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


# ═══════════════════════════════════════════════════════════
#  工具 3: 阶段2 — 生成AUTOSAR标准需求元数据
# ═══════════════════════════════════════════════════════════

@tool
def excel_generate_requirement_metadata(
    mapping_info_json_path: str,
    output_dir: str = str(Path(middle_files_dir).parent),  # data目录
    project_name: str = "middle_files",
) -> str:
    """
    【阶段2】根据阶段1的字段映射规则, 从Excel中逐行提取数据并生成AUTOSAR标准需求元数据。

    该阶段会读取阶段1输出的映射规则JSON, 然后回到原始Excel中按照映射规则
    逐行读取CAN路由、CAN信号、LIN信号/调度、NVM等数据, 将其组装为
    AUTOSAR标准的需求元数据结构(包含trace溯源信息), 保存为 requirement_metadata_file.json。

    Args:
        mapping_info_json_path: 阶段1输出的映射规则JSON文件路径
                                (即 extract_params_info.json 的绝对路径)。
        output_dir:  中间结果输出目录的绝对路径。
                     若不传则使用 mapping_info_json_path 所在目录的父目录。
        project_name: 项目名称, 会在 output_dir 下创建同名子目录。默认 "default"。

    Returns:
        生成的需求元数据JSON文件 (requirement_metadata_file.json) 的绝对路径。
        若失败返回包含 code=0 和 msg 的JSON字符串。
    """
    if not output_dir:
        output_dir = str(Path(mapping_info_json_path).resolve().parent.parent)
        project_name = Path(mapping_info_json_path).resolve().parent.name

    cfg = _build_config(
        output_dir=output_dir,
        project_name=project_name,
        previous_data={
            "extract_params_info_path": mapping_info_json_path,
        },
    )

    result = _core_generate_requirement_metadata(cfg)

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


# ═══════════════════════════════════════════════════════════
#  工具 4: 阶段3 — 需求一致性检查
# ═══════════════════════════════════════════════════════════

@tool
def excel_check_requirement_consistency(
    requirement_metadata_json_path: str,
    dbc_metadata_json_path: str = "",
    ldf_metadata_json_path: str = "",
    data_validate_flag: bool = True,
) -> str:
    """
    【阶段3】对生成的需求元数据进行一致性检查。

    支持三种检查场景:
    - 仅Excel: 只传入 requirement_metadata_json_path
    - Excel + DBC: 同时传入 dbc_metadata_json_path
    - Excel + LDF: 同时传入 ldf_metadata_json_path

    检查过程会对比不同来源的需求数据, 发现冲突后生成冲突报告Excel。
    报告为空表示需求一致, 非空则包含冲突详情。

    Args:
        requirement_metadata_json_path: 阶段2输出的需求元数据JSON文件路径
                                        (即 requirement_metadata_file.json 的绝对路径)。
        dbc_metadata_json_path: (可选) DBC解析后的需求元数据JSON文件路径。
        ldf_metadata_json_path: (可选) LDF解析后的需求元数据JSON文件路径。
        data_validate_flag: 是否启用数据schema校验, 默认True。

    Returns:
        一致性检查结果的JSON字符串, 包含:
        - code: 1=成功, 0=失败
        - msg: 信息
        - confirm_content: 确认内容(含冲突报告路径或通过提示)
    """
    previous_data = {
        "requirement_metadata_file_path": requirement_metadata_json_path,
        "data_validate_flag": data_validate_flag,
    }
    if dbc_metadata_json_path:
        previous_data["dbc_requirement_metadata_file_path"] = dbc_metadata_json_path
    if ldf_metadata_json_path:
        previous_data["ldf_requirement_metadata_file_path"] = ldf_metadata_json_path

    cfg = _build_config(previous_data=previous_data)

    result = _core_check_requirement_consistency(cfg)

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


# ═══════════════════════════════════════════════════════════
#  工具 5: 全流程一键解析
# ═══════════════════════════════════════════════════════════

@tool
def excel_full_parse(
    excel_paths: List[str],
    dbc_metadata_json_path: str = "",
    ldf_metadata_json_path: str = "",
    data_validate_flag: bool = True,
) -> str:
    """
    【全流程】一键完成Excel需求解析的完整流程（阶段0→1→2→3）。

    依次执行:
    1. 解析Excel, 识别各模块对应的sheet名称
    2. 提取每个sheet的字段映射规则
    3. 根据映射规则从Excel提取数据, 生成AUTOSAR标准需求元数据
    4. 对需求元数据进行一致性检查

    每个阶段的中间文件都会保存在 output_dir/project_name/ 目录下,
    方便后续查看和调试。

    Args:
        excel_paths: 待解析的Excel文件绝对路径列表。
                     支持 .xlsx / .xls / .xlsm 格式。
                     示例: ["D:/data/CMX_CCU_V29.xlsx", "D:/data/NVM_BlockList.xlsx"]
        dbc_metadata_json_path: (可选) DBC解析后的需求元数据JSON文件路径, 用于阶段3一致性检查。
        ldf_metadata_json_path: (可选) LDF解析后的需求元数据JSON文件路径, 用于阶段3一致性检查。
        data_validate_flag: 是否在阶段3启用数据schema校验, 默认True。

    Returns:
        全流程执行结果的JSON字符串, 包含:
        - code: 1=全部成功, 0=某阶段失败
        - stage_results: 各阶段的输出文件路径
          - stage0_sheet_range_path: 阶段0 sheet识别结果
          - stage1_mapping_info_path: 阶段1 映射规则
          - stage2_requirement_metadata_path: 阶段2 需求元数据
          - stage3_consistency_check_result: 阶段3 一致性检查结果
        - msg: 失败时的错误信息
    """
    output_dir = str(Path(middle_files_dir).parent)  # data目录
    project_name = "middle_files"

    stage_results = {
        "stage0_sheet_range_path": "",
        "stage1_mapping_info_path": "",
        "stage2_requirement_metadata_path": "",
        "stage3_consistency_check_result": None,
    }

    # ── 阶段0 ──
    logging.info("【全流程】开始阶段0: 解析Excel, 识别sheet名称...")
    cfg = _build_config(
        excel_paths=excel_paths,
        output_dir=output_dir,
        project_name=project_name,
    )
    stage0_result = _core_extract_sheet_range(cfg)

    if isinstance(stage0_result, dict) and stage0_result.get("code") == 0:
        return json.dumps({
            "code": 0,
            "msg": f"阶段0失败: {stage0_result.get('msg', '未知错误')}",
            "failed_stage": "stage0",
            "stage_results": stage_results,
        }, ensure_ascii=False, indent=2)

    sheet_range_path = str(stage0_result)
    stage_results["stage0_sheet_range_path"] = sheet_range_path
    logging.info(f"【全流程】阶段0完成, 输出: {sheet_range_path}")

    # ── 阶段1 ──
    logging.info("【全流程】开始阶段1: 提取字段映射规则...")
    # 复用同一个 cfg, 补充 previous_data
    cfg.previous_data["extract_routing_data_and_signal_sheet_data"] = sheet_range_path
    stage1_result = _core_extract_mapping_info(cfg)

    if isinstance(stage1_result, dict) and stage1_result.get("code") == 0:
        return json.dumps({
            "code": 0,
            "msg": f"阶段1失败: {stage1_result.get('msg', '未知错误')}",
            "failed_stage": "stage1",
            "stage_results": stage_results,
        }, ensure_ascii=False, indent=2)

    mapping_info_path = str(stage1_result)
    stage_results["stage1_mapping_info_path"] = mapping_info_path
    logging.info(f"【全流程】阶段1完成, 输出: {mapping_info_path}")

    # ── 阶段2 ──
    logging.info("【全流程】开始阶段2: 生成需求元数据...")
    cfg.previous_data["extract_params_info_path"] = mapping_info_path
    stage2_result = _core_generate_requirement_metadata(cfg)

    if isinstance(stage2_result, dict) and stage2_result.get("code") == 0:
        return json.dumps({
            "code": 0,
            "msg": f"阶段2失败: {stage2_result.get('msg', '未知错误')}",
            "failed_stage": "stage2",
            "stage_results": stage_results,
        }, ensure_ascii=False, indent=2)

    requirement_metadata_path = str(stage2_result)
    stage_results["stage2_requirement_metadata_path"] = requirement_metadata_path
    logging.info(f"【全流程】阶段2完成, 输出: {requirement_metadata_path}")

    # ── 阶段3 ──
    logging.info("【全流程】开始阶段3: 需求一致性检查...")
    cfg.previous_data["requirement_metadata_file_path"] = requirement_metadata_path
    cfg.previous_data["data_validate_flag"] = data_validate_flag
    if dbc_metadata_json_path:
        cfg.previous_data["dbc_requirement_metadata_file_path"] = dbc_metadata_json_path
    if ldf_metadata_json_path:
        cfg.previous_data["ldf_requirement_metadata_file_path"] = ldf_metadata_json_path

    stage3_result = _core_check_requirement_consistency(cfg)
    stage_results["stage3_consistency_check_result"] = stage3_result
    logging.info("【全流程】阶段3完成。")

    return json.dumps({
        "code": 1,
        "msg": f"""
            Excel全流程解析完,输出的metadata_json文件在：{output_dir}/{project_name}/requirement_metadata_file_simplify.json
            """,
        "stage_results": stage_results,
    }, ensure_ascii=False, indent=2)



# ───────────── 工具列表导出 (方便外部统一注册) ─────────────

excel_parse_tools = [
    excel_extract_sheet_range,
    excel_extract_mapping_info,
    excel_generate_requirement_metadata,
    excel_check_requirement_consistency,
    excel_full_parse,
]


if __name__ == "__main__":
    # ── 示例: 全流程调用 ──
    test_excel_paths = [
        # r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\AY5-G Project_CMX_EEA3.0_CCU_LIN_MIX_V1.4 - 增加诊断(LIN诊断相关).xlsx",
        r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\A02-Y_纯电AB平台_CMX_CCU_V29.2(G3 G.0-1)-20251201_Result.xlsx"
        # r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\CCU_MID_NVM(┤µ┤ó╣▄└φ╓╨╝Σ╝■─ú┐Θ)_BlockList_A664WD.xlsx"
        # r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\EEA3.0混动系列A（适用T09-N等）_CMX_CCU_LIN_MIX_V1.1_20250326（格式修正）.xlsx"
    ]
    # test_output_dir = r"D:\KoTEI_CODE\Agent_Autosar_Backend\data\output"
    # test_project_name = "test"

    # 全流程
    result = excel_full_parse.invoke({
        "excel_paths": test_excel_paths,
    })
    print(result)

    # # 也可以分阶段调用:
    # # 阶段0
    # stage0_path = excel_extract_sheet_range.invoke({
    #     "excel_paths": test_excel_paths,
    #     "output_dir": test_output_dir,
    #     "project_name": test_project_name,
    # })
    # print(f"阶段0输出: {stage0_path}")
    #
    # # 阶段1
    # stage1_path = excel_extract_mapping_info.invoke({
    #     "sheet_range_json_path": stage0_path,
    # })
    # print(f"阶段1输出: {stage1_path}")
    #
    # # 阶段2
    # stage2_path = excel_generate_requirement_metadata.invoke({
    #     "mapping_info_json_path": stage1_path,
    # })
    # print(f"阶段2输出: {stage2_path}")
    #
    # # 阶段3
    # stage3_result = excel_check_requirement_consistency.invoke({
    #     "requirement_metadata_json_path": stage2_path,
    # })
    # print(f"阶段3结果: {stage3_result}")
