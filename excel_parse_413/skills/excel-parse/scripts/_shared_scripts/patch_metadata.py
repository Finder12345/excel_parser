# -*- coding: utf-8 -*-
"""
元数据局部补丁工具。

纯函数，零LLM。
"""
import copy
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Union

from langchain.tools import tool

from .json_utils import load_json_core, save_json_core


def _parse_path(path: str) -> List[Union[str, int]]:
    tokens: List[Union[str, int]] = []
    for part in path.split("."):
        if not part:
            continue
        m = re.findall(r"([^[\]]+)|(\[(\d+)\])", part)
        for item in m:
            if item[0]:
                tokens.append(item[0])
            elif item[2]:
                tokens.append(int(item[2]))
    return tokens


def _set_by_tokens(data: Any, tokens: List[Union[str, int]], value: Any) -> None:
    cur = data
    for t in tokens[:-1]:
        cur = cur[t]
    cur[tokens[-1]] = value


def patch_metadata_core(metadata_path: str, patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = load_json_core(metadata_path)
    backup_path = metadata_path + ".bak." + datetime.now().strftime("%Y%m%d%H%M%S")
    save_json_core(copy.deepcopy(data), backup_path)

    patched = copy.deepcopy(data)
    count = 0
    for p in patches:
        field_path = p.get("field_path", "")
        if not field_path:
            continue
        tokens = _parse_path(field_path)
        _set_by_tokens(patched, tokens, p.get("new_value"))
        count += 1

    root, ext = os.path.splitext(metadata_path)
    patched_path = f"{root}.patched{ext or '.json'}"
    save_json_core(patched, patched_path)

    return {
        "patched_count": count,
        "backup_path": backup_path,
        "patched_metadata_path": patched_path,
    }


@tool
def patch_metadata(metadata_path: str, patches_json: str) -> str:
    """Tool wrapper for patch_metadata."""
    patches = json.loads(patches_json)
    result = patch_metadata_core(metadata_path, patches)
    return json.dumps(result, ensure_ascii=False, default=str)
