from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Union, List, Type
from inspect import isclass

if TYPE_CHECKING:
    from ..arpamar import Arpamar


class ArpamarBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """

    requires: List[Union[Type['ArpamarBehavior'], 'ArpamarBehavior']]

    @abstractmethod
    def operate(self, interface: "Arpamar"):
        """
        该方法可以是 `staticmethod`, `classmethod` 亦或是普通的方法/函数.
        """
        ...


T_ABehavior = Union[Type['ArpamarBehavior'], 'ArpamarBehavior']


@lru_cache(None)
def requirement_handler(behavior: T_ABehavior) -> "List[T_ABehavior]":
    unbound_mixin = getattr(behavior, "requires", [])
    result: "List[behavior]" = []

    for i in unbound_mixin:
        if isclass(i) and issubclass(i, ArpamarBehavior):
            result.extend(requirement_handler(i))
        else:
            result.append(i)
    result.append(behavior)
    return result
