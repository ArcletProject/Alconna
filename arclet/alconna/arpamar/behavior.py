from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Optional, Any, Literal, List

from ..exceptions import BehaveCancelled

if TYPE_CHECKING:
    from . import Arpamar


class ArpamarBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """
    @abstractmethod
    def operate(self, interface: "ArpamarBehaviorInterface"):
        ...


class ArpamarBehaviorInterface:
    __target: 'Arpamar'

    __const__ = ("matched", "head_matched", "error_data", "error_info", "header")
    __changeable__ = ("main_args", "options", "subcommands", "other_args")

    def __init__(self, target: 'Arpamar'):
        self.__target = target

    @property
    def target(self) -> "Arpamar":
        return self.__target

    def require(self, path: str) -> Optional[Any]:
        """如果能够返回, 除开基本信息, 一定返回该path所在的dict"""
        parts = path.split(".")
        part = parts[0]
        if len(parts) == 1:
            if part in self.__const__:
                return getattr(self.target, part)
            elif part in self.__changeable__:
                return getattr(self.target, part)
            elif part in self.target.main_args:
                return self.target.main_args
        else:
            _cache = {}
            for part in parts:
                if part in self.__changeable__:
                    _cache = getattr(self.target, part)
                    continue
                if all([part in self.__target.options, part in self.__target.subcommands]):
                    return
                if part in self.__target.options:
                    _cache = self.__target.options[part]
                    if not isinstance(_cache, dict):
                        return _cache
                    continue
                if part in self.__target.subcommands:
                    _cache = self.__target.subcommands[part]
                    if not isinstance(_cache, dict):
                        return _cache
                    continue
                if part in _cache:
                    if not isinstance(_cache, dict):
                        break
                    _cache = _cache[part]
                    continue
                else:
                    return
            return _cache

    def change_const(self, key: Literal["matched", "head_matched", "error_data", "error_info", "header"], value: Any):
        setattr(self.target, key, value)

    def execute(self, behaviors: List[ArpamarBehavior]):
        for behavior in behaviors:
            try:
                behavior.operate(self)
            except BehaveCancelled:
                continue
