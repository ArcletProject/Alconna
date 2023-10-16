from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ActType(IntEnum):
    """节点触发的动作类型"""

    STORE = 0
    """无 Args 时, 仅存储一个值, 默认为 Ellipsis; 有 Args 时, 后续的解析结果会覆盖之前的值"""
    APPEND = 1
    """无 Args 时, 将多个值存为列表, 默认为 Ellipsis; 有 Args 时, 每个解析结果会追加到列表中
    
    当存在默认值并且不为列表时, 会自动将默认值变成列表, 以保证追加的正确性
    """
    COUNT = 2
    """无 Args 时, 计数器加一; 有 Args 时, 表现与 STORE 相同
    
    当存在默认值并且不为数字时, 会自动将默认值变成 1, 以保证计数器的正确性
    """


@dataclass(eq=True, frozen=True)
class Action:
    """节点触发的动作"""

    type: ActType
    value: Any


store = Action(ActType.STORE, Ellipsis)
"""默认的存储动作"""
store_true = Action(ActType.STORE, True)
"""存储 True"""
store_false = Action(ActType.STORE, False)
"""存储 False"""

append = Action(ActType.APPEND, [Ellipsis])
"""默认的追加动作"""

count = Action(ActType.COUNT, 1)
"""默认的计数动作"""


def store_value(value: Any):
    """存储一个值

    Args:
        value (Any): 待存储的值
    """
    return Action(ActType.STORE, value)


def append_value(value: Any):
    """追加值

    Args:
        value (Any): 待存储的值
    """
    return Action(ActType.APPEND, [value])
