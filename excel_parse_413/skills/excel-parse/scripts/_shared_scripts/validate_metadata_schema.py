# -*- coding: utf-8 -*-
"""按 schema 校验元数据结构。"""
import json
from typing import Any, Dict, List

from langchain.tools import tool


def _type_name(v: Any) -> str:
    return type(v).__name__


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _validate(metadata: Any, schema: Any, path: str, errors: List[str]) -> None:
    if isinstance(schema, dict):
        if not isinstance(metadata, dict):
            errors.append(f"type mismatch at {path or '<root>'}: expect dict, got {_type_name(metadata)}")
            return
        for key, sub_schema in schema.items():
            child_path = _join(path, key)
            if key not in metadata:
                errors.append(f"missing key: {child_path}")
                continue
            _validate(metadata[key], sub_schema, child_path, errors)
        return

    if isinstance(schema, list):
        if not isinstance(metadata, list):
            errors.append(f"type mismatch at {path or '<root>'}: expect list, got {_type_name(metadata)}")
            return
        if schema:
            item_schema = schema[0]
            for idx, item in enumerate(metadata):
                _validate(item, item_schema, f"{path}[{idx}]", errors)
        return

    if schema is None:
        return

    if isinstance(schema, bool):
        expect = bool
    elif isinstance(schema, int):
        expect = int
    elif isinstance(schema, float):
        expect = float
    elif isinstance(schema, str):
        expect = str
    else:
        return

    if expect is int and isinstance(metadata, bool):
        errors.append(f"type mismatch at {path or '<root>'}: expect int, got bool")
        return
    if not isinstance(metadata, expect):
        errors.append(f"type mismatch at {path or '<root>'}: expect {expect.__name__}, got {_type_name(metadata)}")


def validate_metadata_schema_core(metadata: Any, schema: Any) -> Dict[str, Any]:
    errors: List[str] = []
    _validate(metadata, schema, "", errors)
    return {'valid': len(errors) == 0, 'errors': errors}


@tool
def validate_metadata_schema(metadata_json: str, schema_json: str) -> str:
    """Validate metadata against a schema definition."""
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
    schema = json.loads(schema_json) if isinstance(schema_json, str) else schema_json
    result = validate_metadata_schema_core(metadata, schema)
    return json.dumps(result, ensure_ascii=False, default=str)
