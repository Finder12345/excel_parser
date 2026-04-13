# -*- coding: utf-8 -*-
"""
JSON 读写与容错提取工具。

纯函数，零LLM。
"""
import json
import logging
import os
import re
from typing import Any

from langchain.tools import tool

logger = logging.getLogger(__name__)


def save_json_core(data: Any, path: str, ensure_ascii: bool = False, indent: int = 2) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent, default=str)
    return os.path.abspath(path)


def load_json_core(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_json_from_text_core(text: str) -> Any:
    if not text or not text.strip():
        raise ValueError("输入文本为空")
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=True)
        if repaired:
            return repaired
    except ImportError:
        logger.warning("json_repair 未安装，跳过修复策略")
    except Exception:
        pass

    raise ValueError(f"无法从文本中提取有效 JSON: {text[:200]}...")


@tool
def save_json(data: str, path: str) -> str:
    """Save JSON content to a file path."""
    parsed = json.loads(data) if isinstance(data, str) else data
    return save_json_core(parsed, path)


@tool
def load_json(path: str) -> str:
    """Load a JSON file and return a JSON string."""
    data = load_json_core(path)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@tool
def extract_json_from_text(text: str) -> str:
    """Extract JSON content from free-form text and return JSON."""
    data = extract_json_from_text_core(text)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
