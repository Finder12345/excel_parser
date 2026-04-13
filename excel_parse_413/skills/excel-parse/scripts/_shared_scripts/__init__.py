# -*- coding: utf-8 -*-
"""
Excel 解析共享脚本包。

提供通用的 Excel I/O、数据组装、验证、溯源等原子化工具。
所有脚本零领域知识、零LLM，纯数据操作。

双层架构：
- *_core() 纯函数：可直接 import 调用（适合 Claude Code 等外部 Agent）
- @tool 包装函数：注册到 LangChain 工具系统（适合本项目 LangGraph Agent）
"""

# ── 工具函数 ──
from .column_utils import (
    col_index_to_letter, col_index_to_letter_core,
    col_letter_to_index, col_letter_to_index_core,
)
from .json_utils import (
    save_json, save_json_core,
    load_json, load_json_core,
    extract_json_from_text, extract_json_from_text_core,
)
from .add_trace import add_trace, add_trace_core, add_trace_batch_core
from .normalize_value import normalize_value, normalize_value_core

# ── Excel I/O ──
from .list_sheets import list_sheets, list_sheets_core
from .read_sheet import read_sheet, read_sheet_core
from .get_header_sample import get_header_sample, get_header_sample_core
from .get_column_letter_mapping import get_column_letter_mapping, get_column_letter_mapping_core
from .sheet_to_column_json import sheet_to_column_json, sheet_to_column_json_core
from .read_cell_range import read_cell_range, read_cell_range_core

# ── 数据处理 ──
from .extract_columns_by_mapping import extract_columns_by_mapping, extract_columns_by_mapping_core
from .build_module_metadata import build_module_metadata, build_module_metadata_core
from .build_routing_metadata import build_routing_metadata, build_routing_metadata_core
from .finalize_routing_metadata import finalize_routing_metadata, finalize_routing_metadata_core
from .finalize_can_metadata import finalize_can_metadata, finalize_can_metadata_core
from .finalize_lin_metadata import finalize_lin_metadata, finalize_lin_metadata_core, finalize_lin_schedule, finalize_lin_schedule_core
from .finalize_nvm_metadata import finalize_nvm_metadata, finalize_nvm_metadata_core
from .assemble_full_metadata import assemble_full_metadata, assemble_full_metadata_core
from .match_by_intersection import match_by_intersection, match_by_intersection_core
from .locate_trace import locate_trace, locate_trace_core
from .read_source_cell import read_source_cell, read_source_cell_core
from .reparse_field import reparse_field, reparse_field_core
from .reparse_row import reparse_row, reparse_row_core
from .reparse_module_fields import reparse_module_fields, reparse_module_fields_core
from .patch_metadata import patch_metadata, patch_metadata_core
from .diff_metadata import diff_metadata, diff_metadata_core
from .export_diagnostic_report import export_diagnostic_report, export_diagnostic_report_core

# ── 验证 ──
from .validate_field_mapping import validate_field_mapping, validate_field_mapping_core
from .validate_metadata_schema import validate_metadata_schema, validate_metadata_schema_core
from .check_consistency import check_consistency, check_consistency_core
from .simplify_metadata import simplify_metadata, simplify_metadata_core


# ── 所有 @tool 包装的工具列表（便于 LangGraph 注册） ──
all_tools = [
    # 工具函数
    col_index_to_letter,
    col_letter_to_index,
    save_json,
    load_json,
    extract_json_from_text,
    add_trace,
    normalize_value,
    # Excel I/O
    list_sheets,
    read_sheet,
    get_header_sample,
    get_column_letter_mapping,
    sheet_to_column_json,
    read_cell_range,
    # 数据处理
    extract_columns_by_mapping,
    build_module_metadata,
    build_routing_metadata,
    finalize_routing_metadata,
    finalize_can_metadata,
    finalize_lin_metadata,
    finalize_lin_schedule,
    finalize_nvm_metadata,
    assemble_full_metadata,
    match_by_intersection,
    locate_trace,
    read_source_cell,
    reparse_field,
    reparse_row,
    reparse_module_fields,
    patch_metadata,
    diff_metadata,
    export_diagnostic_report,
    # 验证
    validate_field_mapping,
    validate_metadata_schema,
    check_consistency,
    simplify_metadata,
]
