"""Alconna 错误提示相关"""


class ParamsUnmatched(Exception):
    """一个 text 没有被任何参数匹配成功"""


class ArgumentMissing(Exception):
    """组件内的 Args 参数未能解析到任何内容"""


class InvalidParam(Exception):
    """构造 alconna 时某个传入的参数不正确"""


class NullMessage(Exception):
    """传入了无法解析的消息"""


class UnexpectedElement(Exception):
    """给出的消息含有不期望的元素"""


class DuplicateCommand(Exception):
    """命令重复"""


class ExceedMaxCount(Exception):
    """注册的命令数量超过最大长度"""


class BehaveCancelled(Exception):
    """行为执行被停止"""


class OutBoundsBehavior(Exception):
    """越界行为"""


class FuzzyMatchSuccess(Exception):
    """模糊匹配成功"""
