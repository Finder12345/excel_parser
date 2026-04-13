# -*- coding: utf-8 -*-
"""
@File    : query.py
@Date    : 2025--08-19 11:49
@Desc    : Description of the file
@Author  : lei
"""

query_ineraction_excel = """
你应该能看懂一部分，但格式是自定义的，你的理解应该有偏差，希望通过提问并给出正确答案的方式帮助你纠正偏差，
1、问：表格整体结构是怎样的？
   正确答案：前5行是表头，后面所有行是表内容，表内容中每一行代表一条路由信息，包括信号名、pdu名、通道名等。
2、问：表头含义是什么？
   正确答案：第一行：只有Gateway Routing Chart，是整个表格的名称。
          第二行："Source/Destination Matrix"是路由矩阵的名称，下面对应第四行是矩阵中可能出现的所有通道名（channel name），再下面各行中用字母标识某行路由信息的源和目标通道名。第二行中其余内容不重要。
          第三行：通信协议标识。例如，"CAN/ETHERNET/LIN"代表第四行相应内容与这三种协议都有关，"ETH"则代表只和这一种协议有关。
          第四行：路由相关信号所有属性，以第二行中"Source/Destination Matrix"为界，左侧是路由源相关属性，右侧是路由目的相关属性。
          第五行：信号的单位，不重要。
"""
# 例如，B4 / AI4都是"Signal name"，但B4是路由源信号，AI4是路由目标信号。

query_ineraction_autosar_1 = """
提示1：
需求json格式如下：
[
    {
        "源信号名称": "ACU_3_CrashOutputSts",
        "源pdu名称": "ACU_3",
        "目标信号名称": "CrashOutputSts",
        "目标pdu名称": "ABM_1",
        "目标通道名称": "CAN_FLZCU_BD",
        "源通道名称": "CANFD_FLZCU_CH"
    },
]
每条路由对应一个字典，其中包含路由源信息（例如，源信号名称、源通道名称等）和路由目标信息（例如，目标信号名称、目标通道名称等），
若存在多条路由的源信息全部一致，而路由目标信息不一致，说明是从一个源路由到多个目标，
这种情况下，结构需求中ComGwMapping应该只生成一个字典，其中ComGwSource有一个，ComGwDestination有多个，且要与需求json的数据对应。
提示2：
ComGwSource/ComGwSignal/ComGwSignalRef值的形式为："源通道名称/源pdu名称/源信号名称";
ComGwDestination/ComGwSignal/ComGwSignalRef值的形式为："目标通道名称/目标pdu名称/目标信号名称"
"""

query_ineraction_autosar = """
提示1：
需求json格式如下：
{
    "源信号名称": "",
    "源pdu名称": "",
    "目标信号名称": "AI4",
    "目标pdu名称": "AJ4"
}
注意：需要理解键的含义，忽视值。
提示2：
ComGwSource/ComGwSignal/ComGwSignalRef值为："源通道名称/源pdu名称/源信号名称"；
ComGwDestination/ComGwSignal/ComGwSignalRef值为："目标通道名称/目标pdu名称/目标信号名称"
"""

query_ineraction_autosar_tmp = """
提示1：输入是两份json文件。
提示2：
ComGwSource/ComGwSignal/ComGwSignalRef值为："源通道名称/源pdu名称/源信号名称"；
ComGwDestination/ComGwSignal/ComGwSignalRef值为："目标通道名称/目标pdu名称/目标信号名称"
"""

