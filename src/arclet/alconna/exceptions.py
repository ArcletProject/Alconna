"""Alconna 错误提示相关"""


class AlconnaException(Exception):
    """Alconna 异常基类"""


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


class NullMessage(AlconnaException):
    """传入了无法解析的消息"""


class UnexpectedElement(AlconnaException):
    """给出的消息含有不期望的元素"""


class AnalyseException(AlconnaException):
    """Alconna Analyse 异常基类"""

    def __init__(self, msg, context_node=None):
        super().__init__(msg)
        self.context_node = context_node


class ParamsUnmatched(AnalyseException):
    """一个传入参数没有被选项或Args匹配"""


class InvalidParam(AnalyseException):
    """传入参数验证失败"""


class InvalidHeader(AnalyseException):
    """传入的消息头部无效"""


class ArgumentMissing(AnalyseException):
    """组件内的 Args 参数未能解析到任何内容"""


class InvalidArgs(AnalyseException):
    """构造 alconna 时某个传入的参数不正确"""


class PauseTriggered(AnalyseException):
    """解析状态保存触发"""

    def __init__(self, msg, context_node, argv):
        super().__init__(msg, context_node)
        self.argv = argv
