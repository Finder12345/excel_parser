import xml.etree.ElementTree as ET
import json
from collections import OrderedDict

def parse_lst(element):
    """处理 d:lst 标签"""
    name = element.attrib['name']
    result = {name: []}
    for child in element:
        child_ans = parse_element(child)
        if child_ans is not None:
            result[name].append(child_ans)
    return result if bool(result) else None


def parse_ctr(element):
    """处理 d:ctr 标签"""
    name = element.attrib['name']
    result = {name: {}}
    for child in element:
        child_ans = parse_element(child)
        if child_ans is not None:
            result[name].update(child_ans)
    return result if bool(result) else None


def parse_chc(element):
    """处理 d:chc 标签"""
    name = element.attrib['name']
    result = {name: {}}
    if 'value' in element.attrib:
        result[name]["chc_value"] = element.attrib['value']
    for child in element:
        child_ans = parse_element(child)
        if child_ans is not None:
            result[name].update(child_ans)
    return result if bool(result) else None


def parse_var_or_ref(element):
    """处理 d:var 和 d:ref 标签"""
    name = element.attrib.get('name', '')
    value = element.attrib.get('value', '')
    result = {name: value} if name else {}
    for child in element:
        if child.tag.endswith('a') and child.attrib.get('name') == "ENABLE":
            result[f"{name}/ENABLE"] = child.attrib.get('value', '')
    return result if bool(result) else None


def parse_default(element):
    """处理其他未匹配的标签"""
    result = {}
    for child in element:
        child_ans = parse_element(child)
        if child_ans is not None:
            result.update(child_ans)
    return result if bool(result) else None


def parse_element(element):
    """解析 XML 元素并转换为 JSON 结构"""
    tag_handlers = {
        'lst': parse_lst,
        'ctr': parse_ctr,
        'chc': parse_chc,
        'var': parse_var_or_ref,
        'ref': parse_var_or_ref,
    }

    # 获取标签类型
    tag_suffix = element.tag.split('}')[-1]  # 去除命名空间前缀
    handler = tag_handlers.get(tag_suffix)

    if handler:
        result = handler(element)
    else:
        result = parse_default(element)

    return result


def xml_to_json(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    return parse_element(root)
