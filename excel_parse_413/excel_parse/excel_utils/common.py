# -*- coding: utf-8 -*-
"""
@File    : common.py
@Date    : 2025--08-19 13:47
@Desc    : Description of the file
@Author  : lei
"""

from .global_cfg import global_config
from .dep_llm import call_model


def get_sheet_name(sheet_names, get_sheet_name_prompt, table):
    import json
    import re
    from json_repair import loads, repair_json

    def extract_json(content):
        try:
            return json.loads(content)
        except Exception:
            pass

        pattern = r"```json(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            json_content = matches[0].strip()
            json_content = json_content.replace("None", "null").replace("True", "true").replace("False", "false")
            return json.loads(json_content)

        processed_content = content.replace("None", "null").replace("True", "true").replace("False", "false")
        repaired = repair_json(processed_content)
        return loads(repaired)

    query = f"""
          请从以下名称列表列表中，找到表示{table}的名称：
          {sheet_names}
          """

    res = call_model(
        query.replace("{", "{{").replace("}", "}}"),
        get_sheet_name_prompt.replace("{", "{{").replace("}", "}}"),
    )

    # dep_llm.call_model 已不返回 token；兼容这里的统计逻辑
    spend_token = 0

    if isinstance(res, tuple):
        res, spend_token = res

    global_config.llm_spend_token["excel_parse"] += spend_token

    res_json = str(res).replace("{{", "{").replace("}}", "}")
    sheet_name = extract_json(res_json).get("name", "")
    return sheet_name
