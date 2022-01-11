"""Alconna Action相关"""

from typing import Callable, Any, Union, List, Tuple, Optional, TYPE_CHECKING


class ArgAction:
    """负责封装action的类"""
    action: Callable[[Any], Union[List, Tuple]]

    def __init__(self, action: Callable = None):
        self.action = action

    @classmethod
    def set_action(cls, action: Callable):
        """修饰一个action"""
        def _act(*items: Any):
            result = action(*items)
            if result is None:
                return items
            if not isinstance(result, tuple):
                result = [result]
            return result

        return cls(_act)

    def __call__(self, option_dict, exception_in_time):
        try:
            additional_values = self.action(*option_dict.values())
            for i, k in enumerate(option_dict.keys()):
                option_dict[k] = additional_values[i]
        except Exception as e:
            if exception_in_time:
                raise e
        return option_dict


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda x: x)
        self.value = value

    def __call__(self, option_dict, exception_in_time):
        return self.value


def store_bool(value: bool):
    """存储一个布尔值"""
    return _StoreValue(value)


def store_const(value: int):
    """存储一个整数"""
    return _StoreValue(value)


if TYPE_CHECKING:
    from . import alconna_version


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)
