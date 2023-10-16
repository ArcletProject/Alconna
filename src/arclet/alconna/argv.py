from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

from ._internal._argv import Argv as Argv
from .typing import TDC

__argv_type__: ContextVar[type[Argv]] = ContextVar("argv_type", default=Argv)


def set_default_argv_type(argv_type: type[Argv]):
    """设置默认的命令行参数类型"""
    __argv_type__.set(argv_type)


def argv_config(
    target: type[Argv] | None = None,
    preprocessors: dict[type, Callable[..., Any]] | None = None,
    to_text: Callable[[Any], str | None] | None = None,
    filter_out: list[type] | None = None,
    checker: Callable[[Any], bool] | None = None,
    converter: Callable[[str | list], TDC] | None = None,
):
    """配置命令行参数

    Args:
        target (type[Argv] | None, optional): 目标命令类型.
        preprocessors (dict[type, Callable[..., Any]] | None, optional): 命令元素的预处理器.
        to_text (Callable[[Any], str | None] | None, optional): 将命令元素转换为文本, 或者返回None以跳过该元素.
        filter_out (list[type] | None, optional): 需要过滤掉的命令元素.
        checker (Callable[[Any], bool] | None, optional): 检查传入命令.
        converter (Callable[[str | list], TDC] | None, optional): 将字符串或列表转为目标命令类型.
    """
    Argv._cache.setdefault(target or __argv_type__.get(), {}).update(
        {k: v for k, v in locals().items() if v is not None}
    )
