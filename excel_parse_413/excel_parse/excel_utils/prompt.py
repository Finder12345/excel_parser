# -*- coding: utf-8 -*-
"""
@File    : prompt.py.py
@Author  : zhenp
@Date    : 2025-07-29 14:13
@Desc    : Description of the file
"""
import os
import yaml
from . import python_project_root
import inspect
from . import excel_prompts

markdown_parse_prompt = """
  # role
  你是 autosar 领域的专家，熟悉 autosar 的需求配置，尤其是了解通信矩阵的Signal和Message相关的配置内容

  # task
  用户会输入一段markdown文档的文字给你，文本内容主要是用作通信矩陈的需求变更的补充内容，包括Signal或Message的增/删/改操作，你需要从文本中提取出关键数据信息，并以结构化json形式返回

  # 输入要求：
    Message的操作：
        同一通道(channel)下，报文名是唯一的，
        1.所以对于增删改操作，输入必须要包含通道信息、报文名(msg_name)；
        2.另外对于新增和更新操作，还需要提供报文的相关属性信息，其中字段有：
            msg_id：报文ID
            cycle_time:报文周期
            msg_length:报文长度
            send_type：报文发送类型
            direction：报文方向（发送或者接收）
        对于新增操作，以上所有属性信息都需要提取；对于更新操作，则至少需要一项属性信息。
    signal的操作：
        signal隶属于报文，一个报文(Message)可能有多个signal，信号名可以代表其在同一报文下的唯一性
        1.所以对于增删改操作，输入必须要包含通道信息、报文名、信号名(signal_name)；
        2.另外对于新增和更新操作，还需要提供signal的相关属性信息，其中字段有：
            BitPosition：起始位位置（单位：bit，通常从0开始计数），指明信号在帧/PDU中的起始比特位置
            BitSize为：起始位位置（单位：bit，通常从0开始计数），指明信号在帧/PDU中的起始比特位置
            SignalInitValue：默认/缺省原始值，用于初始化、无数据或超时策略时采用的值
            factor：缩放因子，用于原始值到物理值的线性缩放
            offset：偏移量，用于原始值到物理值的线性平移
        对于新增操作，以上所有属性信息都需要提取；对于更新操作，则至少需要一项属性信息。

  # example
    Message：
    CZR_CANFD通道下，报文名为CCU_EPB_2，将ID修改为0x25B，周期修改为10ms:
    CZR_CANFD通道下，增加报文名为CCU_EPB_1，ID为0x27B，周期为20ms，报文长度为32Byte，发送类型是Periodic，方向是发送；
    CZR_CANFD通道下，删除名为CCU_EPB_1的报文；
    CZR_CANFD通道下，增加报文名为CCU_EPB_1，周期为20ms，报文长度为32Byte，发送类型是Periodic，方向是接收;
    signal：
    CZR_CANFD通道下，报文CCU_EPB_2中的信号EPB_MotorCurrent_L，将起始位修改为1，长度修改为2;
    CZR_CANFD通道下，在报文CCU_EPB_1下增加信号EPB_RWUAvl L，startbit为1，bitsize为2，defaultvalue为O，offset为0，factor为1；
    CZR_CANFD通道下，在CCU_EPB_1的报文下删除信号EPB_RWUAvl_L；
    CCU_EPB_1的报文下删除信号EPB_RWUAvl_L；

  # 输出：需求变更的内容列表
  输出要求：
  1. 以json格式返回，必须去掉markdown格式相关的内容。
  2. 报文方向的发送或者接收，对应输出分别是'TX'和'RX'；scope只有两种："Message"和"Signal"；action只有三种："modify"、"add"和"delete"
  3. 对于不满足输入要求的文字块，将其放入invalid_data列表中；对于满足输入要求的文字块，将解析后数据放入valid_data列表中。
  4. 严格按照以下格式返回，key千万不要改动
  RESPONSE JSON FORMAT:
  {
    invalid_data: [
        {
            'text_block': "CZR_CANFD通道下，增加报文名为CCU_EPB_1，周期为20ms，报文长度为32Byte，发送类型是Periodic，方向是接收;"
            'reason': "没有MsgId参数"
        },
        {
            'text_block': "CCU_EPB_1的报文下删除信号EPB_RWUAvl_L；"
            'reason': "没有channel信息"
        }
    ],
    valid_data: [
        {
          "scope": "Message",
          "action": "modify",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_2",
          "details": {
            "msg_id": "0x25B",
            "cycle_time": 10
          }
        },
        {
          "scope": "Message",
          "action": "add",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_1",
          "details": {
            "msg_id": "0x27B",
            "cycle_time": 20,
            "msg_length": 32,
            "send_type": 'Periodic',
            "direction: 'TX',
          }
        },
        {
          "scope": "Message",
          "action": "delete",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_1"
        },
        {
          "scope": "Signal",
          "action": "modify",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_2",
          "signal_name": "EPB_MotorCurrent_L",
          "details": {
            "BitPosition": 1,
            "BitSize": 2
          }
        },
        {
          "scope": "Signal",
          "action": "add",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_1",
          "signal_name": "EPB_RWUAvl_L",
          "details": {
            "BitPosition": 1,
            "BitSize": 2,
            "SignalInitValue": 0,
            "offset": 0,
            "factor": 1
          }
        },
        {
          "scope": "Signal",
          "action": "delete",
          "channel": "CZR_CANFD",
          "msg_name": "CCU_EPB_1",
          "signal_name": "EPB_RWUAvl_L"
        }
    ]
  }
"""

json_parse_prompt = """
  # role
  你是 AUTOSAR 领域的资深专家，具备以下专业能力：
  - 精通 AUTOSAR 架构和需求配置规范
  - 深度理解 CDD (Customer Designed Device) 配置原理
  - 熟悉 AVTP (Audio Video Transport Protocol) 协议配置细节
  - 具备丰富的车载通信矩阵设计经验

  # task
  用户会输入一个 JSON 格式的 CDD 补充需求描述，你的任务是从中提取关键数据信息：
  - 提取通道名 (Channel) 和报文名 (MessageName)
  - 将解析结果转换为标准的结构化 JSON 格式返回

  # example
  # input format:
    {
      "description": "用于描述CDD的补充需求的统一JSON格式",
      "modules": [
        {
          "name": "CDD_AVTP",
          "description": "AVTP CDD的补充定义",
          "entities": [
            {
              "type": "Message",
              "name": "AVTP_Message",
              "members": [
                {
                  "name": "MessageName1",
                  "Channel": "Channel1"
                },
                {
                  "name": "MessageName2",
                  "Channel": "Channel2"
                }
              ]
            }
          ]
        }
      ]
    }

  输出要求：
  1. 以json格式返回，必须去掉markdown格式相关的内容。
  2. 你需要获取CDD相关的AVTP报文，并获取每个报文数据对应的通道名(赋值给'Channel')，报文名(赋值给'MessageName')，并且放入MessageList列表中；对于其他不相关的数据不要提取
  3. 严格按照以下格式返回，key千万不要改动
  RESPONSE JSON FORMAT:
    {
      "type": "CDD_AVTP",
      "MessageList": [
        {
          "Channel": "Channel1",
          "MessageName": "MessageName1"
        },
        {
          "Channel": "Channel2",
          "MessageName": "MessageName2"
        }
      ]
    }
"""

experience_prompt = """
    # role
    你是一名autosar专家，熟悉autosar各业务模块的配置，你需要把用户提供的信息转成json形式，有三种json格式，根据用户输入的内容有不同的json格式。

    # 背景：
    我已经从EXCEL需求文件中提取了很多autosar模块的数据，它们有各业务模块对应的表格名（sheet_name_key_words）、表格描述（sheet_description），也有提取的字段和EXCEL表格表头的映射信息（mapping_name就是可能的表格内的名字），以及字段的定义描述（description）。例如：
      {{  
          "can_routing": {{
              "sheet_name_key_words": ["GWRoutingChart", 'Routing'],
              "sheet_description": ["CAN路由表，一般包含'网关'、'路由'、'Routing'、'Gateway'关键词，大小写不敏感"],
              "fields": {{
                "sourceSignalName": {{
                    "mapping_name": ["Signal Name", "SigName"],
                    "description": ["源信号名称"]
                }},
                "destinationPduName": {{
                  "mapping_name": ["Dest Message/PDU name"],
                  "description": ["目标PDU名称"]
                }}
             }}
          }}
      }}
    以上can_routing就是代码CAN模块的路由表数据，"GWRoutingChart"就是can_routing对应的sheet表的name, sourceSignalName就是表内的一个属性字段，"Signal Name"就是sourceSignalName对应表格内的一个表头字段，"源信号名称"就是sourceSignalName定义描述
    但用户提出了我有数据提取失败，他提供了正确的信息。

    # task
    如果用户输入是对属性字段与表格内字段的映射关系信息，则使用第一种json格式：
        例如用户输入："路由表的destinationPduName应该对应Name列"，就需要抽取出属性字段为"destinationPduName"，表头字段为"Name"，将其放入description字段
        注意如果映射的表头字段包含"列"位置相关信息，不要提取出来，比如上述的"Name列", 应该只提取"Name"
        输出格式为JSON:
        {{  
            "sheet_type": "can_routing",
            "fields": {{
                "destinationPduName": {{
                    "mapping_name": ["Name"]
                }}
            }}
        }}

    如果用户输入只是对属性字段的描述信息，则使用第二种json格式，
        例如用户输入："路由表的destinationPduName通常和sourceSignalName一致"。没有属性字段与表头的映射关系，则将完整描述放入description字段
        输出格式为JSON:
        {{  
            "sheet_type": "can_routing",
            "fields": {{
                "destinationPduName": {{
                    "description": ["路由表的destinationPduName通常和sourceSignalName一致"]
                }}
            }}
        }}

    如果用户输入的是业务模块与表格名的映射关系信息，则使用第三种json格式：
        例如用户输入："LIN调度表应该对应的sheet_name是LIN1调度表"。需要将lin_schedule业务模块对应的sheet_name放入sheet_name_key_words字段
        输出格式为JSON:
        {{
            "sheet_type": "lin_schedule",
            "sheet_name_key_words": ["LIN1调度表"]
        }}

    如果用户输入的是业务模块的表名相关描述信息，则使用第四种json格式：
        例如用户输入："LIN信号表，一般包含'LIN'关键词，但不包含'LIN Legend'、'调度'、'schedule'关键词"。需要将LIN信号表对应的描述放入sheet_description字段
        输出格式为JSON:
        {{
            "sheet_type": "lin_signal",
            "sheet_description": ["LIN信号表，一般包含'LIN'关键词，但不包含'LIN Legend'、'调度'、'schedule'关键词"]
        }}


    如果不能匹配到以上所有json格式，则直接返回空字符串。
        输出格式为：""


    # 输出要求：
    输出前四种数据格式一定要有sheet_type字段，如果不能匹配到语义一致或近似的业务模块，则直接返回空字符串。{insert_msg}

"""


def get_prompts_dict():
    """收集并返回路由表/Excel 解析相关的提示词字典。

    主要来源：
        - 本文件内定义的 markdown_parse_prompt/json_parse_prompt/experience_prompt；
        - routingtable.excel_prompts 模块中定义的所有“公共字符串常量”（非 _ 前缀）。

    返回:
        prompts_data: Dict[str, str]

    说明:
        对 excel_prompts 中的字符串做了 strip('\n')/strip(' ') 以减少无意义空白。
    """
    prompts_data = {'markdown_parse_prompt': markdown_parse_prompt,
                    'json_parse_prompt': json_parse_prompt,
                    'experience_prompt': experience_prompt}
    # 遍历模块的所有成员
    for name, value in inspect.getmembers(excel_prompts):
        # 过滤出字符串类型的公共属性
        if not name.startswith('_') and isinstance(value, str):
            prompts_data[name] = value.strip('\n').strip(' ')
    return prompts_data


prompts_data = get_prompts_dict()


def get_params_trim_prompts():
    """加载参数裁剪（params trim）相关的提示词配置。

    读取资源文件:
        resources/params_trim_prompts.yaml

    返回:
        prompt_data: 从 YAML 解析得到的 dict（yaml.safe_load）。

    用途:
        通常用于将大对象/长列表按规则裁剪后再喂给 LLM，避免 token 过大。
    """
    params_trim_prompts_path = os.path.join(python_project_root, "resources", "params_trim_prompts.yaml")
    with open(params_trim_prompts_path, "r", encoding="utf-8") as f:
        prompt_data = yaml.safe_load(f.read())
    return prompt_data

# params_trim_prompts =get_params_trim_prompts()