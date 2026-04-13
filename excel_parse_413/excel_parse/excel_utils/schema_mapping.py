import logging
import os
import ujson
from pathlib import Path

def clear_data(data):
    if "value" in data:
        data.pop("type", None)
        data.pop("trace", None)
        data.pop("col", None)
        data.pop("row", None)


def make_schema_tree(data):
    if isinstance(data, dict):
        if "value" in data:
            data["show_type"] = type(data["value"]).__name__
            clear_data(data)
            return
        for k, v in data.items():
            if isinstance(v, dict):
                make_schema_tree(v)
                data[k] = {'data': v, "show_key": k}
            elif isinstance(v, list) and v:
                data[k] = v[0:1]
                for _item in data[k]:
                    make_schema_tree(_item)

    elif isinstance(data, list) and data:
        data = data[0:1]
        for _item in data:
            make_schema_tree(_item)


# 类型映射字典
TYPE_MAPPING = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
}


def safe_convert_type(value, target_type_name):
    """
    安全地将值转换为目标类型
    Args:
        value: 要转换的值
        target_type_name: 目标类型名称（字符串形式）

    Returns:
        转换后的值
    """
    if value is None:
        return value
    if target_type_name not in TYPE_MAPPING:
        logging.info(f"Unsupported target type: {target_type_name}")
        return value

    try:
        target_type = TYPE_MAPPING[target_type_name]
        return target_type(value)
    except (ValueError, TypeError) as e:
        logging.info(f"Type conversion failed: {value} -> {target_type_name}, error: {e}")
        return value


# 常量映射key
common_key_mapping = ['CHANNEL_NAME', 'SCHEDULE_TABLE', 'ROUTE_TYPE', 'NVM_SHEET']


def process_list_data(data, schema):
    """处理列表类型数据的递归转换"""
    if not data or not schema:
        return
    for _index, _item in enumerate(data):
        make_show_data_by_schema(_item, schema[0])


def process_common_key_dict(data, schema):
    """处理包含通用键的字典类型数据"""
    if not data or not schema:
        return

    keys_list = list(data.keys())
    schema_keys = list(schema.keys())
    common_key = schema_keys[0]

    for k in keys_list:
        v = data[k]
        if isinstance(v, dict):
            make_show_data_by_schema(v, schema[common_key]['data'])
        elif isinstance(v, list):
            process_list_data(v, schema[common_key])


def process_normal_key_dict(data, schema):
    """处理不包含通用键的字典类型数据"""
    if not data or not schema:
        return

    keys_list = list(data.keys())
    for k in keys_list:
        if k not in schema:
            continue

        v = data[k]
        if isinstance(v, dict):
            if k != schema[k]['show_key']:
                data[schema[k]['show_key']] = v
                data.pop(k)
            make_show_data_by_schema(v, schema[k]['data'])
        elif isinstance(v, list) and v:
            if not schema[k]:
                logging.info(f"List element types are inconsistent, please check schema!")
            process_list_data(v, schema[k])


def make_show_data_by_schema(data, schema):
    if not data or not schema:
        return

    if isinstance(data, dict):
        # 包含value字段的基础类型节点直接返回
        if "value" in data:
            return

        schema_keys = list(schema.keys())
        # 判断是否为通用键类型
        if any(common_key == schema_keys[0] for common_key in common_key_mapping):
            process_common_key_dict(data, schema)
        else:
            process_normal_key_dict(data, schema)

    elif isinstance(data, list):
        process_list_data(data, schema)


def make_show_data(data):
    try:
        file_path = os.path.join(Path(__file__).parent, "schema.json")
        print(f"这个校验的file_path是:{file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            schema = ujson.load(f)
        make_show_data_by_schema(data, schema)
    except Exception as e:
        import traceback
        logging.info(traceback.format_exc())
        logging.info(f"make_show_data error: {e}")
