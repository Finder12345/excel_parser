import logging
import os
import traceback
import ujson
import stat
import platform

from .dbc_parser_tool import DbcParser
from .global_cfg import global_config


def save_dbc_info():


    def set_readonly_safe(file_path, data):
        """安全的跨平台只读设置"""
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


    try:
        # 解析DBC文件
        dbc_obj = DbcParser()
        msg_info = dbc_obj.parse_dbcs(global_config.file_type_info['dbc_info'])

        output_dir = global_config.current_work_space['project_directory']
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        # 获取json输出路径
        dbc_requirement_metadata_file = os.path.join(
            output_dir,
            str(global_config.current_work_space['project_name']),
            "dbc_requirement_metadata_file.json"
        )
        global_config.previous_data['dbc_requirement_metadata_file'] = dbc_requirement_metadata_file
        # 写入json文件

        set_readonly_safe(dbc_requirement_metadata_file, msg_info)
        return msg_info["AUTOSAR"]["RequirementsData"]["CommunicationStack"]["Can"], dbc_requirement_metadata_file, 1
    except Exception as e:
        msg = f"解析arxml失败: {e}\r\n traceback: {traceback.format_exc()}"
        logging.error(msg)
        return {}, msg, 0
