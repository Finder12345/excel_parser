# -*- coding: utf-8 -*-
"""
导出诊断报告。

纯函数，零LLM。
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from langchain.tools import tool

from .json_utils import save_json_core
from .locate_trace import locate_trace_core


def export_diagnostic_report_core(metadata_path: str, error_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    for ef in error_fields:
        field_path = ef.get("field_path", "")
        error_msg = ef.get("error_msg", "")
        located = locate_trace_core(metadata_path, field_path) if field_path else {"value": None, "trace": []}
        items.append({
            "field_path": field_path,
            "error_msg": error_msg,
            "value": located.get("value"),
            "trace": located.get("trace", []),
        })

    report = {
        "metadata_path": metadata_path,
        "generated_at": datetime.now().isoformat(),
        "total": len(items),
        "items": items,
    }

    base_dir = os.path.dirname(os.path.abspath(metadata_path))
    report_path = os.path.join(base_dir, f"diagnostic_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
    save_json_core(report, report_path)

    return {
        "report_path": report_path,
        "summary": {
            "total": len(items),
            "with_trace": sum(1 for x in items if x.get("trace")),
        },
    }


@tool
def export_diagnostic_report(metadata_path: str, error_fields_json: str) -> str:
    """Tool wrapper for export_diagnostic_report."""
    error_fields = json.loads(error_fields_json)
    result = export_diagnostic_report_core(metadata_path, error_fields)
    return json.dumps(result, ensure_ascii=False, default=str)
