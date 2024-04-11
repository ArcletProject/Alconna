"""Alconna 错误提示相关"""


class AlconnaException(Exception):
    """Alconna 异常基类"""


class ParamsUnmatched(AlconnaException):
    """一个传入参数没有被选项或Args匹配"""


class InvalidParam(AlconnaException):
    """传入参数验证失败"""


class ArgumentMissing(AlconnaException):
    """组件内的 Args 参数未能解析到任何内容"""


class InvalidArgs(AlconnaException):
    """构造 alconna 时某个传入的参数不正确"""


class NullMessage(AlconnaException):
    """传入了无法解析的消息"""


class UnexpectedElement(AlconnaException):
    """给出的消息含有不期望的元素"""


class ExecuteFailed(AlconnaException):
    """执行失败"""


class ExceedMaxCount(AlconnaException):
    """注册的命令数量超过最大长度"""


class BehaveCancelled(AlconnaException):
    """行为执行被停止"""


class OutBoundsBehave(AlconnaException):
    """越界行为"""


class FuzzyMatchSuccess(AlconnaException):
    """模糊匹配成功"""


class PauseTriggered(AlconnaException):
    """解析状态保存触发"""


class SpecialOptionTriggered(AlconnaException):
    """内置选项解析触发"""
