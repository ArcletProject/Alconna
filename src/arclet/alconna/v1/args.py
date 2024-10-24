from __future__ import annotations

import warnings
from enum import Enum
from typing import Any, Final, Iterable

from tarina import Empty
from typing_extensions import Self

from arclet.alconna.args import ArgsBuilder, Arg
from arclet.alconna.typing import TAValue

from .typing import KeyWordVar, MultiVar, _StrMulti, UnpackVar


class ArgFlag(str, Enum):
    """标识参数单元的特殊属性"""

    OPTIONAL = "?"
    HIDDEN = "/"
    ANTI = "!"


class _CompatArgsBuilder(ArgsBuilder):
    def __getitem__(self, item):
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            self._args.extend(data)
        else:
            self._args.append(Arg(*data))
        return self

    def build(self):
        for arg in self._args:
            value = arg.type_
            if isinstance(value, MultiVar):
                if isinstance(value, _StrMulti):
                    arg.field.multiple = "str"
                else:
                    arg.field.multiple = value.flag if value.length < 1 else value.length
                arg.type_ = value.base
                if isinstance(value.base, KeyWordVar):
                    arg.type_ = value.base.base
                    arg.field.kw_only = True
                    arg.field.kw_sep = value.base.sep
            elif isinstance(value, KeyWordVar):
                arg.field.kw_only = True
                arg.field.kw_sep = value.sep
                arg.type_ = value.base
            elif isinstance(value, UnpackVar):
                arg.type_ = value.of(value.origin)
        return super().build()

    def __truediv__(self, other) -> Self:
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def separate(self, *separator: str) -> Self:
        """设置参数的分隔符

        Args:
            *separator (str): 分隔符

        Returns:
            Self: 参数集合自身
        """
        for arg in self._args:
            arg.field.seps = "".join(separator)
        return self

    def add(self, name: str, *, value: TAValue[Any], default: Any = Empty, flags: list[ArgFlag] | None = None) -> Self:
        """添加一个参数

        Args:
            name (str): 参数名称
            value (TAValue): 参数值
            default (Any, optional): 参数默认值.
            flags (list[ArgFlag] | None, optional): 参数标记.

        Returns:
            Self: 参数集合自身
        """
        if next(filter(lambda x: x.name == name, self._args), False):
            return self
        self._args.append(Arg(name, value, default))
        return self


class __CompatArgsBuilderInstance:
    __slots__ = ()

    def __getattr__(self, item: str):
        return _CompatArgsBuilder().__getattr__(item)

    def __getitem__(self, item):
        warnings.warn("Args[...] is deprecated, use Args.xxx(...) instead", DeprecationWarning, stacklevel=2)
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            return _CompatArgsBuilder(*data)
        else:
            return _CompatArgsBuilder(Arg(*data))

    def __call__(self, *args: Arg[Any], separators: str | Iterable[str] | None = None):
        """
        构造一个 `Args`

        Args:
            *args (Arg): 参数单元
            separators (str | Iterable[str] | None, optional): 可选的为所有参数单元指定分隔符
        """
        if separators is not None:
            seps = "".join(separators) if isinstance(separators, Iterable) else separators
            for arg in args:
                arg.field.seps = seps
        return _CompatArgsBuilder(*args)


Args: Final = __CompatArgsBuilderInstance()
