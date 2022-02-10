"""Alconna 错误提示相关"""


class ParamsUnmatched(Exception):
    """一个 text 没有被任何参数匹配成功"""


class InvalidParam(Exception):
    """构造alconna时某个传入的参数不正确"""


class NullTextMessage(Exception):
    """传入了不含有text的消息"""


class UnexpectedElement(Exception):
    """给出的消息含有不期望的元素"""


class DuplicateCommand(Exception):
    """命令重复"""


class ExceedMaxCount(Exception):
    """注册的命令数量超过最大长度"""
