"""
@FileName: metadata_to_front.py
@Description:
@Author: ztw
@Time: 2026/1/19 16:15
"""
import json
import ujson
import logging
import os
import random
import shutil
import sys
import uuid
from typing import Dict, List, Any, Set

from . import global_var
from .global_cfg import global_config



class JsonTransformer:
    # 固定的description内容
    MSG_DESCRIPTION = "MessageName"
    SIG_DESCRIPTION = "SignalName"
    CHA_DESCRIPTION = "ChannelName"
    NA_DESCRIPTION = "Name"


    def __init__(self, origin_path: str = None, origin_data: Dict[str, Any] = None):
        if origin_path and origin_data:
            raise ValueError("只能传入 origin_path 或 origin_data 中的一个")
        if not origin_path and not origin_data:
            raise ValueError("必须传入 origin_path 或 origin_data 中的一个")

        self.origin_path = origin_path
        if origin_path:
            self.origin_data = self._load_origin_json(origin_path)
        else:
            self.origin_data = origin_data

        self.origin_data = self._preprocess_json(self.origin_data)
        self.used_ids: Set[int] = set()
        self.result: List[Dict[str, Any]] = []
        self.process_count = 0

    def _preprocess_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            for key, val in data.items():
                if key == "file_path" and isinstance(val, str):
                    data[key] = {"value": val}
                elif (key in {"signals","block","targets","message_rules","local_ecus","endians","source","target"}) and isinstance(val, list):
                    data[key] = {"data": val}
                else:
                    data[key] = self._preprocess_json(val)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                data[idx] = self._preprocess_json(item)
        remove_msg_data = remove_msg_send_type(data)
        return remove_msg_data

    def _load_origin_json(self, path: str) -> Dict[str, Any]:
        try:
            # print(f"🔍 开始读取文件：{path}")
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # print(f"✅ 文件读取完成，数据大小：{sys.getsizeof(data)} bytes")
            logging.info(f"✅ File read completed, data size: {sys.getsizeof(data)} bytes")
            return data
        except Exception as e:
            raise Exception(f"File read failed：{str(e)}")

    def _generate_random_id(self) -> int:
        while True:
            random_id = random.randint(1, 2147483647)
            if random_id not in self.used_ids:
                self.used_ids.add(random_id)
                return random_id

    def _get_root_node_name(self) -> str:
        return next(iter(self.origin_data.keys())) if self.origin_data else "AUTOSAR"

    def _is_bottom_node(self, node_data: Any) -> bool:
        return isinstance(node_data, dict) and "value" in node_data and "trace" in node_data

    def _safe_copy(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._safe_copy(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._safe_copy(v) for v in data]
        else:
            return data

    def _is_empty_node(self, node: Dict[str, Any]) -> bool:
        return node.get("label", "") == "" and isinstance(node.get("children", []), list) and len(
            node.get("children", [])) == 0

    def _reorder_msg_id_after_msg_name(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将msg_id节点移动到msg_name节点的后面
        :param config_data: 原始config数据
        :return: 重新排序后的config数据
        """
        if not isinstance(config_data, dict):
            return config_data

        # 如果同时包含msg_name和msg_id，进行重新排序
        if "msg_name" in config_data and "msg_id" in config_data:
            # 新建有序字典，保持原有顺序的同时调整msg_id位置
            ordered_keys = []
            msg_id_entry = None

            # 先遍历所有键，收集除了msg_id之外的键
            for key in config_data.keys():
                if key == "msg_id":
                    msg_id_entry = (key, config_data[key])
                else:
                    ordered_keys.append(key)

            # 找到msg_name的位置，在其后插入msg_id
            if "msg_name" in ordered_keys:
                msg_name_index = ordered_keys.index("msg_name")
                ordered_keys.insert(msg_name_index + 1, "msg_id")

            # 构建重新排序后的字典
            reordered_config = {}
            for key in ordered_keys:
                if key == "msg_id" and msg_id_entry:
                    reordered_config[key] = msg_id_entry[1]
                else:
                    reordered_config[key] = config_data[key]

            return reordered_config

        return config_data

    def _add_index_to_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        为config包住的每个对象添加index字段
        :param config_data: 原始config数据（字典格式，key为对象名，value为对象内容）
        :return: 添加index后的config数据
        """
        reordered_config = self._reorder_msg_id_after_msg_name(config_data)
        # 复制原始数据，避免修改源数据
        config_with_index = self._safe_copy(reordered_config)

        # 按对象顺序遍历，添加index（从1开始）
        for idx, (obj_key, obj_value) in enumerate(config_with_index.items(), start=1):
            # 为每个对象添加index字段（确保对象是字典类型）
            if isinstance(obj_value, dict):
                obj_value["_index"] = idx
        return config_with_index

    # ========== 新增：递归移动signals节点 ==========
    def _move_signals_to_sibling_children(self, node):
        """递归遍历节点树，将signals节点移动到前一个同级节点的children中"""
        if not isinstance(node, dict) or "children" not in node:
            return node

        children = node["children"]
        new_children = []
        prev_node = None

        for child in children:
            # 先递归处理子节点的子节点
            self._move_signals_to_sibling_children(child)

            if child.get("label") == "signals" and prev_node is not None:
                # 如果当前节点是signals，并且有前一个节点，就移动过去
                if "children" not in prev_node:
                    prev_node["children"] = []
                prev_node["children"].append(child)
            else:
                new_children.append(child)
                prev_node = child

        node["children"] = new_children
        return node

    def _set_child_description(self, node, default_desc):
        """递归给所有节点（包括中间节点和叶子节点）设置默认的 description"""
        if isinstance(node, dict):
            # 1. 先给当前节点（包括中间节点）设置 description
            if "description" not in node or node["description"] == self.MSG_DESCRIPTION:
                node["description"] = default_desc
            # 2. 再递归处理所有子节点
            for key, child in node.items():
                if isinstance(child, (dict, list)):
                    self._set_child_description(child, default_desc)
        elif isinstance(node, list):
            # 处理列表中的每个元素
            for item in node:
                self._set_child_description(item, default_desc)

    def _get_node_description(self, node_name: str) -> str:
        if node_name == "signals":
            return self.SIG_DESCRIPTION
        elif node_name in {"RequirementsData"}:
            return self.NA_DESCRIPTION
        else:
            return self.MSG_DESCRIPTION

    def _process_special_dict_node(self, current_node: Dict, current_data: Dict, current_name: str) -> bool:
        """核心修复：排除AUTOSAR所有子节点，且仅对明确的特殊节点处理"""
        child_keys = set(current_data.keys())
        # 判断是否仅包含"value"和"modules"两个子节点（顺序无关）
        target_prefixes = ["Application_Table_", "Diagnostic_Table_"]
        if (child_keys == {"value", "modules"} or
                current_name in {"file_path", "SRM", "FDM", "RLS", "SSMF", "SSMR", "PADS"} or
                any(current_name.startswith(prefix) for prefix in target_prefixes)):
            if any(current_name.startswith(prefix) for prefix in target_prefixes):
                current_node["description"] = "ScheduleName"
                transformed_data = {"schedule_name": {"value": current_name}}
            elif current_name in {"file_path"}:
                current_node["description"] = "Name"
                transformed_data = {}
            else:
                current_node["description"] = "Name"
                transformed_data = {"name": {"value": current_name}}
            current_node["config"] = self._safe_copy(current_data)  # 保留原始结构
            for key, val in current_data.items():
                # 所有子节点统一转为 value 包裹格式
                transformed_data[key] = {"value": self._safe_copy(val)}
            config_with_index = self._add_index_to_config(transformed_data)
            current_node["config"] = config_with_index
            current_node["children"] = []  # 清空children
            return True
        if current_name == "common":
            current_node["config"] = self._safe_copy(current_data)  # 保留原始结构
            # transformed_data = {"msg_name": {"value": current_name}}
            # for key, val in current_data.items():
            #     # 所有子节点统一转为 value 包裹格式
            #     transformed_data[key] = {"value": self._safe_copy(val)}
            config_with_index = self._add_index_to_config(current_node["config"])
            current_node["config"] = config_with_index
            current_node["children"] = []  # 清空children
            return True
        else:
            return False

    def _process_signals_node(self, current_node: Dict, current_data: Any) -> None:
        signals_data = current_data.get("data", [])
        for idx, item in enumerate(signals_data):
            if isinstance(item, dict):
                item_label = f"signals_item_{idx}"
                if "FrameName" in item and self._is_bottom_node(item["FrameName"]):
                    item_label = item["FrameName"].get("value", item_label)
                elif "ShortName" in item and self._is_bottom_node(item["ShortName"]):
                    item_label = item["ShortName"].get("value", item_label)
                elif  "ShortName" in item:
                    if isinstance(item["ShortName"], dict):
                        item_label = item["ShortName"].get("value", item_label)
                    else:
                        # 如果是字符串，直接赋值
                        item_label = item["ShortName"]

                first_value = next(iter(item.values())) if item else None
                if isinstance(first_value, dict) and "value" in first_value:
                    config_with_index = self._add_index_to_config(self._safe_copy(item))
                    signals_item_node = {
                        "id": self._generate_random_id(),
                        "label": item_label,
                        "description": self.SIG_DESCRIPTION,
                        "config": config_with_index,
                        "children": []
                    }
                    if not self._is_empty_node(signals_item_node):
                        current_node["children"].append(signals_item_node)
                else:
                    transformed_data = {}
                    for key, value in item.items():
                        transformed_data[key] = {
                            "value": self._safe_copy(value)
                        }
                    config_with_index = self._add_index_to_config(transformed_data)
                    signals_item_node = {
                        "id": self._generate_random_id(),
                        "label": item_label,
                        "description": self.SIG_DESCRIPTION,
                        "config": config_with_index,
                        "children": []
                    }
                    if not self._is_empty_node(signals_item_node):
                        current_node["children"].append(signals_item_node)
            else:
                child_node = {
                    "id": self._generate_random_id(),
                    "label": str(item),
                    "description": self.SIG_DESCRIPTION,
                    "children": []
                }
                if not self._is_empty_node(child_node):
                    current_node["children"].append(child_node)

    def _process_targets_node(self, current_node: Dict, current_data: Any) -> None:
        targets_data = current_data.get("data", [])
        for idx, item in enumerate(targets_data):
            if isinstance(item, dict):
                item_label = f"targets_item_{idx}"
                if "destinationChannelName" in item and isinstance(item["destinationChannelName"], dict) and "value" in \
                        item["destinationChannelName"]:
                    item_label = item["destinationChannelName"]["value"]
                elif "destinationPduName" in item and isinstance(item["destinationPduName"],
                                                                 dict) and "value" in item["destinationPduName"]:
                    item_label = item["destinationPduName"]["value"]

                config_with_index = self._add_index_to_config(self._safe_copy(item))
                targets_item_node = {
                    "id": self._generate_random_id(),
                    "label": item_label,
                    "description": self.CHA_DESCRIPTION,
                    "config": config_with_index,
                    "children": []
                }
                if not self._is_empty_node(targets_item_node):
                    current_node["children"].append(targets_item_node)
            else:
                child_node = {
                    "id": self._generate_random_id(),
                    "label": str(item),
                    "description": self.CHA_DESCRIPTION,
                    "children": []
                }
                if not self._is_empty_node(child_node):
                    current_node["children"].append(child_node)

    def _process_block_node(self, current_node: Dict, current_data: Any) -> None:
        block_data = current_data.get("data", [])
        for idx, item in enumerate(block_data):
            if isinstance(item, dict):
                item_label = f"block_item_{idx}"
                if "Name" in item and self._is_bottom_node(item["Name"]):
                    item_label = item["Name"].get("value", item_label)
                elif "ShortName" in item and self._is_bottom_node(item["ShortName"]):
                    item_label = item["ShortName"].get("value", item_label)

                config_with_index = self._add_index_to_config(self._safe_copy(item))
                block_item_node = {
                    "id": self._generate_random_id(),
                    "label": item_label,
                    "description": self.SIG_DESCRIPTION,
                    "config": config_with_index,
                    "children": []
                }
                if not self._is_empty_node(block_item_node):
                    current_node["children"].append(block_item_node)
            else:
                child_node = {
                    "id": self._generate_random_id(),
                    "label": str(item),
                    "description": self.SIG_DESCRIPTION,
                    "children": []
                }
                if not self._is_empty_node(child_node):
                    current_node["children"].append(child_node)

    def _process_special_list_node(self, current_node: Dict, current_data: List, current_name: str) -> bool:
        if current_name in ["RX", "TX", "NvRamManager", "SignalGateWay", "PduGateWay", "E2E_Message_Rebuild_Route",
                            "LLCE", "CAN_to_CAN"] and len(current_data) > 0:
            for item in current_data:
                if isinstance(item, dict) and "source" in item and "targets" in item:
                    pair_label = "SourceTargetsPair"
                    source_channel = item["source"].get("sourceChannelName", {})
                    if isinstance(source_channel, dict):
                        pair_label = source_channel.get("value", pair_label)

                    # 2. 如果为空，取 sourceSignalName.value
                    if not pair_label or pair_label == "SourceTargetsPair":
                        source_signal = item["source"].get("sourceSignalName", {})
                        if isinstance(source_signal, dict):
                            pair_label = source_signal.get("value", pair_label)

                    # 3. 如果还是为空，取 sourcePduName.value
                    if not pair_label or pair_label == "SourceTargetsPair":
                        source_pdu = item["source"].get("sourcePduName", {})
                        if isinstance(source_pdu, dict):
                            pair_label = source_pdu.get("value", pair_label)

                    # 为这一对 source 和 targets 创建一个容器节点
                    pair_node = {
                        "id": self._generate_random_id(),
                        "label": pair_label,
                        "description": self.CHA_DESCRIPTION,
                        "children": []
                    }

                    # 处理 source
                    source_node = self._process_node_iterative(item["source"],
                                                               node_name=f"temp_{random.randint(1, 1000)}")
                    # 找到外层的 source 节点，直接把它挂到 pair_node 下
                    # for child in source_node["children"]:
                    #     if child["label"] == "source":
                    #         # 直接将整个 source 节点添加到 pair_node
                    #         pair_node["children"].append(child)
                    #     else:
                    #         # 如果没有外层 source 节点，就用它本身
                    #         child["label"] = "source"
                    #         pair_node["children"].append(child)
                    source_wrapper = {
                        "id": self._generate_random_id(),
                        "label": "source",
                        "description": self.CHA_DESCRIPTION,
                        "children": source_node["children"]
                    }
                    pair_node["children"].append(source_wrapper)

                    # 处理 targets
                    targets_node = self._process_node_iterative(item["targets"],
                                                                node_name="targets")
                    targets_wrapper = {
                        "id": self._generate_random_id(),
                        "label": "targets",
                        "description": self.CHA_DESCRIPTION,
                        "children": targets_node["children"]
                    }
                    pair_node["children"].append(targets_wrapper)

                    # 将配对容器添加到当前节点
                    current_node["children"].append(pair_node)
                else:
                    temp_node = self._process_node_iterative(item, node_name=f"temp_{random.randint(1, 1000)}")
                    current_node["children"].extend(
                        [child for child in temp_node["children"] if not self._is_empty_node(child)]
                    )
            return True
        else:
            return False

    def _process_complete_dict_logic(self, current_node: Dict, current_data: Dict, stack: List) -> bool:
        """
        原封不动封装注释里的完整字典逻辑（含特殊分支、普通分支、signals 分离）
        返回值：bool - 表示是否处理了特殊分支（用于外层判断是否 continue）
        """
        # 1. 分离 signals_data（原逻辑：先把 signals 从 current_data 中取出）
        signals_data = None
        normal_data = {}
        for key, val in current_data.items():
            if key == "signals":
                signals_data = val
            else:
                normal_data[key] = val
        # 剩余的普通数据
        normal_data = current_data
        normal_keys = list(normal_data.keys())
        normal_count = len(normal_keys)

        # 2. 原注释里的【特殊分支1】：frame_name + tans_time（互斥）
        if normal_count == 2 and "frame_name" in normal_keys and "tans_time" in normal_keys:
            config_with_index = self._add_index_to_config(self._safe_copy(normal_data))
            frame_name = config_with_index.get("frame_name", "")
            frame_name_value = frame_name.get("value", "frame_name") if isinstance(frame_name,
                                                                                   dict) else frame_name or "frame_name"
            current_node["description"] = self.MSG_DESCRIPTION
            current_node["label"] = frame_name_value
            current_node["config"] = config_with_index
            # 处理完特殊分支，最后挂接 signals
            # self._append_signals_to_node(current_node, signals_data, stack)
            return True  # 告诉外层：已处理特殊分支，需 continue

        # 3. 原注释里的【特殊分支2】：FrameName（互斥）
        elif "FrameName" in normal_keys and not ("frame_name" in normal_keys or "tans_time" in normal_keys):
            msg_name_data = normal_data.get("FrameName", "FrameName")
            if isinstance(msg_name_data, dict):
                frame_label = msg_name_data.get("value", "FrameName")
            else:
                frame_label = str(msg_name_data)
            config_with_index = self._add_index_to_config(self._safe_copy(normal_data))
            frame_node = {
                "id": self._generate_random_id(),
                "label": frame_label,
                "description": self.MSG_DESCRIPTION,
                "config": config_with_index,
                "children": []
            }
            if not self._is_empty_node(frame_node):
                current_node["children"].append(frame_node)
            # 处理完特殊分支，最后挂接 signals
            self._append_signals_to_node(current_node, signals_data, stack)
            # return True  # 告诉外层：已处理特殊分支，需 continue

        # 4. 原注释里的【特殊分支3】：msg_name（互斥）
        elif "msg_name" in normal_keys and not ("frame_name" in normal_keys or "tans_time" in normal_keys):
            msg_name_data = normal_data.get("msg_name", "msg_name")
            if isinstance(msg_name_data, dict):
                frame_label = msg_name_data.get("value", "msg_name")
            else:
                frame_label = str(msg_name_data)
            config_with_index = self._add_index_to_config(self._safe_copy(normal_data))
            frame_node = {
                "id": self._generate_random_id(),
                "label": frame_label,
                "description": self.MSG_DESCRIPTION,
                "config": config_with_index,
                "children": []
            }
            if not self._is_empty_node(frame_node):
                current_node["children"].append(frame_node)
            # 处理完特殊分支，最后挂接 signals
            self._append_signals_to_node(current_node, signals_data, stack)
            # return True  # 告诉外层：已处理特殊分支，需 continue

        # 5. 原注释里的【特殊分支4】：sourceChannelName（互斥）
        elif "sourceChannelName" in normal_keys and not ("frame_name" in normal_keys or "tans_time" in normal_keys):
            frame_label = "sourceChannelName"
            source_channel = normal_data.get("sourceChannelName", {})
            if isinstance(source_channel, dict):
                frame_label = source_channel.get("value", frame_label)
            if frame_label == "sourceChannelName":
                source_signal = normal_data.get("sourceSignalName", {})
                if isinstance(source_signal, dict):
                    frame_label = source_signal.get("value", frame_label)
            if frame_label == "sourceChannelName":
                source_pdu = normal_data.get("sourcePduName", {})
                if isinstance(source_pdu, dict):
                    frame_label = source_pdu.get("value", frame_label)
            config_with_index = self._add_index_to_config(self._safe_copy(normal_data))
            frame_node = {
                "id": self._generate_random_id(),
                "label": frame_label,
                "description": self.CHA_DESCRIPTION,
                "config": config_with_index,
                "children": []
            }
            if not self._is_empty_node(frame_node):
                current_node["children"].append(frame_node)
            # 处理完特殊分支，最后挂接 signals
            self._append_signals_to_node(current_node, signals_data, stack)
            # return True  # 告诉外层：已处理特殊分支，需 continue

        # 6. 原注释里的【普通分支】：normal_count == 1
        elif normal_count == 1:
            key, val = next(iter(normal_data.items()))
            if self._is_bottom_node(val):
                leaf_label = val.get("value", key)
                config_with_index = self._add_index_to_config({key: self._safe_copy(val)})
                leaf_node = {
                    "id": self._generate_random_id(),
                    "label": leaf_label,
                    "description": self.MSG_DESCRIPTION,
                    "config": config_with_index,
                    "children": []
                }
                if not self._is_empty_node(leaf_node):
                    current_node["children"].append(leaf_node)
            else:
                child_node = {
                    "id": self._generate_random_id(),
                    "label": key,
                    "description": self.MSG_DESCRIPTION,
                    "children": []
                }
                if not self._is_empty_node(child_node):
                    current_node["children"].append(child_node)
                    stack.append((child_node, val, key))  # 原逻辑：入栈局部 stack
            # 处理完普通分支，最后挂接 signals
            self._append_signals_to_node(current_node, signals_data, stack)
            return False  # 告诉外层：普通分支，无需 continue

        # 7. 原注释里的【普通分支】：normal_count > 1
        else:
            for key in normal_keys:
                val = normal_data[key]
                if self._is_bottom_node(val):
                    leaf_label = val.get("value", key)
                    config_with_index = self._add_index_to_config({key: self._safe_copy(val)})
                    leaf_node = {
                        "id": self._generate_random_id(),
                        "label": leaf_label,
                        "description": self.MSG_DESCRIPTION,
                        "config": config_with_index,
                        "children": []
                    }
                    if not self._is_empty_node(leaf_node):
                        current_node["children"].append(leaf_node)
                else:
                    child_node = {
                        "id": self._generate_random_id(),
                        "label": key,
                        "description": self.MSG_DESCRIPTION,
                        "children": []
                    }
                    if not self._is_empty_node(child_node):
                        current_node["children"].append(child_node)
                        stack.append((child_node, val, key))  # 原逻辑：入栈局部 stack
            # 处理完普通分支，最后挂接 signals
            self._append_signals_to_node(current_node, signals_data, stack)
            return False  # 告诉外层：普通分支，无需 continue

    def _append_signals_to_node(self, parent_node: Dict, signals_data: Any, stack: List) -> None:
        """抽离 signals 挂接逻辑，确保和原代码完全一致（入栈，不递归）"""
        if signals_data is None:
            return
        # 原逻辑：创建 signals 节点，入栈局部 stack（触发专属处理器）
        # signals_node = self._create_base_node("signals", self.SIG_DESCRIPTION)
        # signals_node = {
        #     "id": self._generate_random_id(),
        #     "label": "signals",
        #     "description": self.SIG_DESCRIPTION,
        #     "children": [],
        #     "config": {}
        # }
        # parent_node["children"].append(signals_node)
        # stack.append((signals_node, signals_data, "signals"))  # 关键：用局部 stack，入栈后走专属处理器
        signals_node = self._process_node_iterative(signals_data, "signals")
        if not self._is_empty_node(signals_node):
            parent_node["children"].append(signals_node)

    def _process_normal_list_logic(self, current_node: Dict, current_data: List, stack: List) -> None:
        """
        封装普通列表处理逻辑，保持原 inline 效果：
        - 优先从 msg_name / FrameName / sourceChannelName 提取 value 作为标签
        - 否则用字典第一个键，或 Item_{idx}
        - 创建节点并推入局部栈，不递归
        """
        for idx in range(len(current_data)):
            item = current_data[idx]
            if isinstance(item, dict):
                if "msg_name" in item and self._is_bottom_node(item["msg_name"]):
                    item_label = item["msg_name"].get("value", f"Item_{idx}")
                elif "FrameName" in item and self._is_bottom_node(item["FrameName"]):
                    item_label = item["FrameName"].get("value", f"Item_{idx}")
                elif "sourceChannelName" in item and self._is_bottom_node(item["sourceChannelName"]):
                    item_label = item["sourceChannelName"].get("value", f"Item_{idx}")
                else:
                    first_key = next(iter(item.keys()), f"Item_{idx}")
                    item_label = first_key
            else:
                item_label = f"Item_{idx}"

            child_node = {
                "id": self._generate_random_id(),
                "label": item_label,
                "description": self.MSG_DESCRIPTION,
                "children": []
            }
            if not self._is_empty_node(child_node):
                current_node["children"].append(child_node)
                stack.append((child_node, item, item_label))

    def _process_node_iterative(self, node_data: Any, node_name: str) -> Dict[str, Any]:
        root = {
            "id": self._generate_random_id(),
            "label": node_name,
            "description": self.MSG_DESCRIPTION,
            "children": []
        }
        stack = [(root, node_data, node_name)]

        while stack:
            current_node, current_data, current_name = stack.pop()
            self.process_count += 1


            current_node["description"] = self._get_node_description(current_name)

            # if self.process_count % 100 == 0:
            #     print(f"🔄 已处理 {self.process_count} 个节点，当前节点：{current_name[:50]}")


            if current_name == "signals":
                self._process_signals_node(current_node, current_data)
                continue



            if current_name == "targets":
                self._process_targets_node(current_node, current_data)
                continue

            if current_name == "block":
                self._process_block_node(current_node, current_data)
                continue

            if isinstance(current_data, list):
                if self._process_special_list_node(current_node, current_data, current_name):
                    continue

                self._process_normal_list_logic(current_node, current_data, stack)
                continue

            if isinstance(current_data, dict):
                # child_keys = list(current_data.keys())
                # child_count = len(child_keys)

                if self._process_special_dict_node(current_node, current_data, current_name):
                    continue
                is_special_branch = self._process_complete_dict_logic(current_node, current_data, stack)
                # 若处理了特殊分支，执行原逻辑的 continue
                if is_special_branch:
                    continue
                continue

            else:
                current_node["label"] = str(current_data)
                current_node["children"] = []

        def filter_empty_nodes(node):
            if not isinstance(node, dict):
                return node
            if "children" in node and isinstance(node["children"], list):
                node["children"] = [filter_empty_nodes(child) for child in node["children"] if
                                    not self._is_empty_node(child)]
            return node if not self._is_empty_node(node) else None

        filtered_root = filter_empty_nodes(root)
        return filtered_root if filtered_root is not None else {
            "id": self._generate_random_id(),
            "label": "",
            "description": self.MSG_DESCRIPTION,
            "children": []
        }

    def transform(self) -> List[Dict[str, Any]]:
        # print("🔍 开始转换JSON结构...")
        self.process_count = 0

        root_node_name = self._get_root_node_name()
        root_data = self.origin_data.get(root_node_name, {})

        if not isinstance(root_data, dict):
            # print(f"⚠️ 警告：root_data 不是字典，而是 {type(root_data)}，将包装为字典节点保留内容")
            logging.warning(f"⚠️ Warning: root_data is not a dictionary, it's {type(root_data)}, will wrap as dictionary node to preserve content")
            root_data = {
                "original_content": root_data
            }

        root = {
            "id": self._generate_random_id(),
            "label": root_node_name,
            "description": self.NA_DESCRIPTION,
            "children": []
        }

        for child_key in root_data.keys():
            child_data = root_data[child_key]
            child_node = self._process_node_iterative(child_data, child_key)
            if not self._is_empty_node(child_node):
                root["children"].append(child_node)

        # ========== 调用递归函数移动signals节点 ==========
        root = self._move_signals_to_sibling_children(root)

        self.result = [root]
        # print(f"✅ 转换完成！总共处理 {self.process_count} 个节点")
        logging.info(f"✅ Conversion completed! Total {self.process_count} nodes processed")
        return self.result

    # def _replace_trace_with_id(self, data):
    #     """
    #     内部方法：递归替换所有trace字段为唯一ID，并更新全局映射字典
    #     """
    #     if isinstance(data, dict):
    #         for key, value in data.items():
    #             if key == "trace" and isinstance(value, list) and len(value) > 0:
    #                 # 生成唯一UUID（也可以换成纯数字ID，按需调整）
    #                 trace_id = str(uuid.uuid4())
    #                 # 保存映射关系到全局字典（图3结构）
    #                 global_var.trace_id_map[trace_id] = value
    #                 # 替换trace内容为ID（图2结构）
    #                 data[key] = trace_id
    #             else:
    #                 self._replace_trace_with_id(value)
    #     elif isinstance(data, list):
    #         for item in data:
    #             self._replace_trace_with_id(item)
    #     return data

    def save_to_target_path(self, data=None) -> str:
        output_dir = global_config.current_work_space["project_directory"]
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if data is None:
            target_dir = os.path.join(
                output_dir,
                str(global_config.current_work_space["project_name"]),
                "requirement_metadata_file_tree.json"
            )
            save_data = self.result
        else:
            target_dir = os.path.join(
                output_dir,
                str(global_config.current_work_space["project_name"]),
                "requirement_metadata_file_trace_map.json"
            )
            global_var.trace_id_map = data
            save_data = data

        # 如果传入了 data，就用它；否则用 self.result
        # save_data = data if data is not None else self.result

        with open(target_dir, 'w', encoding='utf-8') as f:
            f.write(ujson.dumps(save_data, ensure_ascii=False, indent=1))
            # f.write(ujson.dumps(requirement_metadata, ensure_ascii=False, indent=1))

        if global_var.file_save_dir_1 and os.path.exists(global_var.file_save_dir_1):
            target_output_dir = os.path.join(global_var.file_save_dir_1, "output_json")
            os.makedirs(target_output_dir, exist_ok=True)
            shutil.copy2(target_dir, target_output_dir)
        # print(f"文件已保存到：{target_dir}")
        return target_dir

# 删除与FrameSendType同级的MsgSendType字段
def remove_msg_send_type(data):
    """
    递归遍历字典，删除所有与 FrameSendType 同级的 MsgSendType 字段
    """
    if isinstance(data, dict):
        # 检查当前字典中是否同时存在 MsgSendType 和 FrameSendType
        if "MsgSendType" in data and "FrameSendType" in data:
            del data["MsgSendType"]

        # 递归处理所有子字典
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                remove_msg_send_type(value)
    elif isinstance(data, list):
        # 递归处理列表中的每个元素
        for item in data:
            if isinstance(item, (dict, list)):
                remove_msg_send_type(item)
    return data

# def replace_trace_with_id(data):
#     """
#     递归遍历 JSON 结构，将所有 trace 字段替换为唯一 ID，并在 trace_id_map 中记录映射关系
#     """
#     # global trace_id_map
#     if isinstance(data, dict):
#         for key, value in data.items():
#             if key == "trace" and isinstance(value, list) and len(value) > 0:
#                 # 生成唯一 ID
#                 trace_id = str(uuid.uuid4())
#                 # 保存映射关系
#                 global_var.trace_id_map[trace_id] = value
#                 # trace_id_map[trace_id] = value
#                 # 替换 trace 字段内容为 ID
#                 data[key] = trace_id
#             else:
#                 # 递归处理子节点
#                 replace_trace_with_id(value)
#     elif isinstance(data, list):
#         for item in data:
#             replace_trace_with_id(item)
#     return data

def replace_trace_with_id(data: Any) -> Dict[str, Any]:
    """
    递归替换所有 trace 字段为唯一 ID，并返回映射字典
    返回值：(处理后的数据, trace_id_map 字典)
    """
    trace_id_map = {}

    def _replace(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "trace" and isinstance(value, list) and len(value) > 0:
                    trace_id = str(uuid.uuid4())
                    trace_id_map[trace_id] = value
                    node[key] = trace_id
                else:
                    _replace(value)
        elif isinstance(node, list):
            for item in node:
                _replace(item)

    # 深拷贝数据，避免修改原始对象
    # processed_data = ujson.loads(ujson.dumps(data))
    _replace(data)
    return trace_id_map

def replace_trace_with_id(data: Any) -> Dict[str, Any]:
    """
    递归替换所有 trace 字段为唯一 ID，并返回映射字典
    返回值：(处理后的数据, trace_id_map 字典)
    """
    trace_id_map = {}

    def _replace(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "trace" and isinstance(value, list) and len(value) > 0:
                    trace_id = str(uuid.uuid4())
                    trace_id_map[trace_id] = value
                    node[key] = trace_id
                else:
                    _replace(value)
        elif isinstance(node, list):
            for item in node:
                _replace(item)

    # 深拷贝数据，避免修改原始对象
    # processed_data = ujson.loads(ujson.dumps(data))
    _replace(data)
    return trace_id_map

if __name__ == "__main__":
    # 原始JSON路径
    raw_json_path = r"D:\project\test\lin\requirement_metadata_file.json"

    # 执行转换与保存
    converter = JsonTransformer(raw_json_path)
    converter.transform()
    # converter.save_to_target_path()

    # trace_id_map = replace_trace_with_id(converter.result)
    # converter.save_to_target_path()
    # converter.save_to_target_path(trace_id_map)


    output_dir = global_config.current_work_space["project_directory"]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    target_dir = os.path.join(
        output_dir,
        str(global_config.current_work_space["project_name"]),
        "requirement_metadata_file_tree_trace.json"
    )
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    with open(target_dir, "w", encoding="utf-8") as f:
        json.dump(traces_with_ids, f, indent=4, ensure_ascii=False)
    logging.info(f"成功提取并保存 {len(traces_with_ids)} 条 trace 记录到 {target_dir}")