from __future__ import annotations

from typing import Any, Callable

from .typing import TDC
from ._internal._argv import Argv

__argv_type__ = Argv


def set_default_argv_type(argv_type: type[Argv]):
    """设置默认的命令行参数类型"""
    global __argv_type__
    __argv_type__ = argv_type


def argv_config(
    preprocessors: dict[str, Callable[..., Any]] | None = None,
    to_text: Callable[[Any], str | None] | None = None,
    filter_out: list[str] | None = None,
    checker: Callable[[Any], bool] | None = None,
    converter: Callable[[str | list], TDC] | None = None
):
    """配置命令行参数

    Args:
        preprocessors (dict[str, Callable[..., Any]] | None, optional): 命令元素的预处理器.
        to_text (Callable[[Any], str | None] | None, optional): 将命令元素转换为文本, 或者返回None以跳过该元素.
        filter_out (list[str] | None, optional): 需要过滤掉的命令元素.
        checker (Callable[[Any], bool] | None, optional): 检查传入命令.
        converter (Callable[[str | list], TDC] | None, optional): 将字符串或列表转为目标命令类型.
    """
    Argv._cache.setdefault(__argv_type__, {}).update(locals())
