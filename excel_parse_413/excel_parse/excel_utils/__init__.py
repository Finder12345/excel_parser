# -*- coding: utf-8 -*-
"""
excel_utils 包初始化
提供 python_project_root，指向 OMV_tools/ 目录
"""
from pathlib import Path

# 路径计算: excel_utils → move → parse_tool → OMV_tools
python_project_root = Path(__file__).resolve().parent.parent.parent.parent
