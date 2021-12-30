"""Alconna 错误提示相关"""


class ParamsUnmatched(Exception):
    """一个 text 没有被任何参数匹配成功"""


class InvalidName(Exception):
    """option或subcommand的名字中填入了非法的字符"""


class InvalidFormatMap(Exception):
    """错误的格式化参数串"""


class NullTextMessage(Exception):
    """传入了不含有text的消息"""
