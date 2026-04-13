import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from . import python_project_root


class GlobalConfig:
    """支持混合访问方式的全局配置管理器"""

    def __init__(self):
        _config_dir = os.path.join(python_project_root, "output_file")
        if not os.path.exists(_config_dir):
            os.makedirs(_config_dir)
        self._config_file = os.path.join(_config_dir, "global_config.json")
        self._data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """从JSON文件加载配置"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # 递归包装加载的字典
                    self._data = self._wrap_dict(loaded_data, self._save_config)
                # print(f"配置已从 {self._config_file} 加载")
            except Exception as e:
                # print(f"加载配置文件失败: {e}, 使用空配置")
                self._data = self._wrap_dict({}, self._save_config)
        else:
            # print(f"配置文件 {self._config_file} 不存在，使用空配置")
            self._data = self._wrap_dict({}, self._save_config)

    def _wrap_dict(self, data: Dict[str, Any], save_callback: callable) -> Dict[str, Any]:
        """递归包装字典，使其支持属性式访问"""
        wrapped = DictWrapper(data, save_callback)
        return wrapped

    def _save_config(self) -> None:
        """保存配置到JSON文件"""
        try:
            # 在保存前解包所有DictWrapper对象
            data_to_save = self._unwrap_dict(self._data)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"save_config failed: {e}")

    def _unwrap_dict(self, data: Any) -> Any:
        """递归解包DictWrapper对象为普通字典"""
        if isinstance(data, DictWrapper):
            return {k: self._unwrap_dict(v) for k, v in data._data.items()}
        elif isinstance(data, dict):
            return {k: self._unwrap_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._unwrap_dict(item) for item in data]
        elif isinstance(data, Path):
            return str(data)
        else:
            return data

    def unwrap_dict(self, data: Any) -> Any:
        return self._unwrap_dict(data)

    def __getattr__(self, name: str) -> Any:
        """通过属性访问配置项"""
        if name.startswith('_'):
            return super().__getattribute__(name)

        if hasattr(self._data, name):
            return getattr(self._data, name)
        else:
            # 如果属性不存在，尝试从_data字典中获取
            if name in self._data:
                return self._data[name]
            raise AttributeError(f"配置项 '{name}' 不存在")

    def __setattr__(self, name: str, value: Any) -> None:
        """设置配置项并自动保存"""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            # 包装新值以确保嵌套字典也支持属性访问
            if isinstance(value, dict):
                value = self._wrap_dict(value, self._save_config)
            elif isinstance(value, list):
                value = [self._wrap_dict(item, self._save_config) if isinstance(item, dict) else item for item in value]
            self._data[name] = value
            self._save_config()

    def __getitem__(self, key: str) -> Any:
        """通过字典方式访问配置项"""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """通过字典方式设置配置项"""
        self.__setattr__(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """安全获取配置项"""
        try:
            return self.__getattr__(key)
        except (AttributeError, KeyError):
            return default

    def to_dict(self) -> Dict[str, Any]:
        """返回普通字典形式的配置"""
        return self._unwrap_dict(self._data)

    def __contains__(self, key: str) -> bool:
        """检查配置项是否存在"""
        return key in self._data

    def __str__(self) -> str:
        return f"GlobalConfig({len(self._data)} 个配置项)"


class DictWrapper:
    """字典包装器，支持属性式访问和字典式访问"""

    def __init__(self, data: Dict[str, Any], save_callback: callable):
        # 递归包装嵌套字典
        self._data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                self._data[key] = DictWrapper(value, save_callback)
            elif isinstance(value, list):
                self._data[key] = [DictWrapper(item, save_callback) if isinstance(item, dict) else item for item in
                                   value]
            else:
                self._data[key] = value
        self._save_callback = save_callback

    def __getattr__(self, name: str) -> Any:
        """属性式访问"""
        if name.startswith('_'):
            return super().__getattribute__(name)

        if name in self._data:
            return self._data[name]
        raise AttributeError(f"字典中不存在键 '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """属性式设置"""
        name = str(name)
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            # 如果值是字典，进行包装
            if isinstance(value, dict):
                value = DictWrapper(value, self._save_callback)
            elif isinstance(value, list):
                value = [DictWrapper(item, self._save_callback) if isinstance(item, dict) else item for item in value]

            self._data[name] = value
            self._save_callback()

    def __getitem__(self, key: str) -> Any:
        """字典式访问"""
        if key in self._data:
            return self._data[key]
        raise KeyError(f"键 '{key}' 不存在")

    def __setitem__(self, key: str, value: Any) -> None:
        """字典式设置"""
        self.__setattr__(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """安全获取"""
        return self._data.get(key, default)

    def setdefault(self, key: str, value: Any) -> None:
        """通过字典方式设置配置项"""
        self.__setattr__(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def update(self, other_dict: Dict[str, Any]) -> None:
        """更新多个键值对"""
        for key, value in other_dict.items():
            self[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def __str__(self) -> str:
        return str({k: v._data if isinstance(v, DictWrapper) else v for k, v in self._data.items()})

    def __repr__(self) -> str:
        return repr(self._data)
