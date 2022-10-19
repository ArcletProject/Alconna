from typing import TYPE_CHECKING, Optional, Any

from .action import ArgAction

__all__ = ["store_value", "version", "store_true", "store_false"]


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs=None, kwargs=None, raise_exception=False):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


store_true = store_value(True)
store_false = store_value(False)


if TYPE_CHECKING:
    from arclet.alconna import alconna_version


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        return _StoreValue(value) if value else _StoreValue(alconna_version)
