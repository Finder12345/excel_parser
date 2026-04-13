# -*- coding: utf-8 -*-
"""列出 Excel 文件中的所有 sheet 名称。"""
import json
import openpyxl
from langchain.tools import tool


def list_sheets_core(file_path: str):
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    names = wb.sheetnames
    wb.close()
    return names


@tool
def list_sheets(file_path: str) -> str:
    """List all worksheet names in an Excel file."""
    return json.dumps(list_sheets_core(file_path), ensure_ascii=False)
