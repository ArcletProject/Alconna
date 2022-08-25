"""Alconna ArgAction相关"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING, Literal
from arclet.alconna.components.action import ArgAction
from arclet.alconna.components.behavior import ArpamarBehavior
from arclet.alconna.exceptions import BehaveCancelled, OutBoundsBehave
from arclet.alconna.config import config


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs=None, kwargs=None, raise_exception=False):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


if TYPE_CHECKING:
    from arclet.alconna import alconna_version
    from arclet.alconna.arpamar import Arpamar


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        return _StoreValue(value) if value else _StoreValue(alconna_version)


def set_default(value: Any, option: Optional[str] = None, subcommand: Optional[str] = None):
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当option与subcommand同时传入时, 则会被设置为该subcommand内option的默认值

    Args:
        value: 默认值
        option: 选项名
        subcommand: 子命令名
    """

    class _SetDefault(ArpamarBehavior):
        def operate(self, interface: "Arpamar"):
            if not option and not subcommand:
                raise BehaveCancelled
            if option and subcommand is None and not interface.query(f"options.{option}"):
                interface.update(f"options.{option}", {"value": value, "args": {}})
            if subcommand and option is None and not interface.query(f"subcommands.{subcommand}"):
                interface.update(f"subcommands.{subcommand}", {"value": value, "args": {}, "options": {}})
            if option and subcommand and not interface.query(f"{subcommand}.options.{option}"):
                interface.update(f"{subcommand}.options.{option}", {"value": value, "args": {}})

    return _SetDefault()


def exclusion(target_path: str, other_path: str):
    """
    当设置的两个路径同时存在时, 抛出异常

    Args:
        target_path: 目标路径
        other_path: 其他路径
    """

    class _EXCLUSION(ArpamarBehavior):
        def operate(self, interface: "Arpamar"):
            if interface.query(target_path) and interface.query(other_path):
                raise OutBoundsBehave(
                    config.lang.behavior_exclude_matched.format(target=target_path, other=other_path)
                )

    return _EXCLUSION()


def cool_down(seconds: float):
    """
    当设置的时间间隔内被调用时, 抛出异常

    Args:
        seconds: 时间间隔
    """

    class _CoolDown(ArpamarBehavior):
        def __init__(self):
            self.last_time = datetime.now()

        def operate(self, interface: "Arpamar"):
            current_time = datetime.now()
            if (current_time - self.last_time).total_seconds() < seconds:
                raise OutBoundsBehave(config.lang.behavior_cooldown_matched)
            else:
                self.last_time = current_time

    return _CoolDown()


def inclusion(*targets: str, flag: Literal["any", "all"] = "any"):
    """
    当设置的路径不存在时, 抛出异常

    Args:
        targets: 路径列表
        flag: 匹配方式, 可选值为"any"或"all", 默认为"any"
    """

    class _Inclusion(ArpamarBehavior):
        def operate(self, interface: "Arpamar"):
            if flag == "all":
                for target in targets:
                    if not interface.query(target):
                        raise OutBoundsBehave(config.lang.behavior_inclusion_matched)
            else:
                all_count = len(targets) - sum(1 for target in targets if interface.query(target))
                if all_count > 0:
                    raise OutBoundsBehave(config.lang.behavior_inclusion_matched)
    return _Inclusion()
