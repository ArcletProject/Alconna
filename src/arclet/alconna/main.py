"""Alconna 主体"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Generic, Sequence, TypeVar

from .analysis import Analyser, default_compiler, TCompile, __argv_type__
from .base import Option, Arg, NullMessage, Arparma
from .typing import TDC, CommandMeta, DataCollection

TCallable = TypeVar("TCallable")
TDC1 = TypeVar("TDC1", bound=DataCollection[Any])


def handle_argv():
    path = Path(sys.argv[0])
    head = path.stem
    if head == "__main__":
        head = path.parent.stem
    return head


class Alconna(Generic[TDC]):
    """更加精确的命令解析"""

    prefixes: list[str]
    """命令前缀"""
    command: str | Any
    """命令名"""
    options: list[Option]
    "命令包含的选项"
    namespace: str
    """命名空间"""
    meta: CommandMeta
    """命令元数据"""

    def compile(self, compiler: TCompile | None = None):
        """编译 `Alconna` 为对应的解析器"""
        compiler = compiler or default_compiler
        compiler(self.analyser, self.argv.param_ids)

    def __init__(
        self,
        *args: Option | str | list[str] | Arg,
        meta: CommandMeta | None = None,
        separators: str | set[str] | Sequence[str] | None = None,
    ):
        """
        以标准形式构造 `Alconna`

        Args:
            *args (Option | str | list[str] | Arg): 命令选项、主参数、命令名称或命令头
            action (ArgAction | Callable | None, optional): 命令解析后针对主参数的回调函数
            meta (CommandMeta | None, optional): 命令元信息
            separators (str | set[str] | Sequence[str] | None, optional): 命令参数分隔符, 默认为 `' '`
        """
        self.prefixes = next(filter(lambda x: isinstance(x, list), args), [])  # type: ignore
        try:
            self.command = next(filter(lambda x: isinstance(x, str), args))
        except StopIteration:
            self.command = "" if self.prefixes else handle_argv()
        self.meta = meta or CommandMeta()
        self.options = [i for i in args if isinstance(i, Option)]
        self.args = [i for i in args if isinstance(i, Arg)]
        self.nargs = len(self.args)
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.argv = __argv_type__.get()(
            separators=self.separators,  # type: ignore
            filter_crlf=not self.meta.keep_crlf,  # type: ignore
        )
        self.analyser = Analyser(self)
        self.compile()
        self._executors: list[Callable] = []

    def __repr__(self):
        return f"{self.command or self.prefixes[0]}(args={self.args}, options={self.options})"

    def parse(self, message: TDC) -> Arparma[TDC]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类
        
        Args:
            message (TDC): 命令消息
        Returns:
            Arparma[TDC
        Raises:
            NullMessage: 传入的消息为空时抛出
        """
        try:
            self.argv.build(message)
            arp = self.analyser.process(self.argv)
        except NullMessage as e:
            if self.meta.raise_exception:
                raise e
            return Arparma(message, False, error_info=e)
        if arp.matched and self._executors:
            for ext in self._executors:
                arp.call(ext)
        return arp

    def bind(self, target: TCallable) -> TCallable:
        """绑定命令回调函数"""
        self._executors.append(target)
        return target

    def _calc_hash(self):
        return hash((self.command + str(self.prefixes), self.meta, *self.options, *self.args))

    def __call__(self, *args, **kwargs):
        if args:
            return self.parse(list(args))  # type: ignore
        head = handle_argv()
        if head != self.command:
            return self.parse(sys.argv[1:])  # type: ignore
        return self.parse([head, *sys.argv[1:]])  # type: ignore

    @property
    def headers(self):
        return self.prefixes


__all__ = ["Alconna"]
