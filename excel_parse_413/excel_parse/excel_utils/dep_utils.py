# -*- coding: utf-8 -*-
"""Utility helpers used by the standalone script.

Self-contained: stdlib + third-party only.
"""

from __future__ import annotations

import io
import json
import os
import stat
import time
from typing import Any
import logging
import platform
import ujson
import re

from json_repair import repair_json,loads


def remove_file_with_retry(file_path):
    """尝试删除文件，如果遇到权限问题，尝试修改权限后再删除"""
    try:
        os.remove(file_path)
    except PermissionError as e:
        # 修改文件权限，给当前用户完全控制权
        os.chmod(file_path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
        os.remove(file_path)



def set_readonly_safe(file_path, data):
    """安全的跨平台只读设置"""
    if os.path.exists(file_path):
        remove_file_with_retry(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(ujson.dumps(data, ensure_ascii=False, indent=1))
    try:
        if platform.system() == "Windows":
            # Windows: 使用只读属性
            # Windows 也会处理 stat 常量，但行为与Linux不同
            os.chmod(file_path, stat.S_IREAD)
        else:
            # Linux/Unix/Mac: 标准设置
            os.chmod(file_path,
                     stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception as e:
        logging.error(f"Error setting file read-only attribute: {str(e)}")


def read_first_n_lines(file_path, n):
    # 通过循环逐行读取文件的前n行。
    # 适用于大文件，内存效率高。
    lines = ''
    with open(file_path, 'r', encoding='utf-8') as file:
        for line_number, line in enumerate(file, 1):  # 行号从1开始计数
            if line_number > n:
                break  # 读完n行后退出循环
            lines += line  # 将处理后的行添加到列表
    return lines

def extract_json(content):
    is_json = False
    try:
        json.loads(content)
        is_json = True
    except Exception as e:
        pass
    if is_json:
        return json.loads(content)
    pattern = r"```json(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    if len(matches):
        # 预处理内容，将 Python 特有值转换为 JSON 格式
        json_content = matches[0].strip()
        json_content = json_content.replace('None', 'null')  # Python None -> JSON null
        json_content = json_content.replace('True', 'true')  # Python True -> JSON true
        json_content = json_content.replace('False', 'false')  # Python False -> JSON false
        return json.loads(json_content)
    else:
        # 预处理内容，替换 Python 特有值
        processed_content = content.replace('None', 'null').replace('True', 'true').replace('False', 'false')
        repaired = repair_json(processed_content)
        return loads(repaired)


def update_srs_value(val, val_type="design", trace=None):
    """

    """

    return {
        "value": val,
        "type": val_type,
        "trace": trace if trace else [],

    }
