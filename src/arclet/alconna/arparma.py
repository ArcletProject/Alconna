from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from tarina import get_signature

from .model import HeadResult, OptionResult, SubcommandResult
from .typing import TDC

T = TypeVar('T')


class Arparma(Generic[TDC]):
    """承载解析结果与操作数据的接口类

    Attributes:
        origin (TDC): 原始数据
        matched (bool): 是否匹配
        header_match (HeadResult): 命令头匹配结果
        error_info (type[BaseException] | BaseException | str): 错误信息
        error_data (list[str | Any]): 错误数据
        main_args (dict[str, Any]): 主参数匹配结果
        other_args (dict[str, Any]): 其他参数匹配结果
        options (dict[str, OptionResult]): 选项匹配结果
        subcommands (dict[str, SubcommandResult]): 子命令匹配结果
    """
    header_match: HeadResult
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]

    def __init__(
        self,
        source: str,
        origin: TDC,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[BaseException] | BaseException | str = '',
        error_data: list[str | Any] | None = None,
        main_args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
        subcommands: dict[str, SubcommandResult] | None = None,
    ):
        """初始化 `Arparma`
        Args:
            source (str): 命令源
            origin (TDC): 原始数据
            matched (bool, optional): 是否匹配
            header_match (HeadResult | None, optional): 命令头匹配结果
            error_info (type[BaseException] | BaseException | str, optional): 错误信息
            error_data (list[str | Any] | None, optional): 错误数据
            main_args (dict[str, Any] | None, optional): 主参数匹配结果
            options (dict[str, OptionResult] | None, optional): 选项匹配结果
            subcommands (dict[str, SubcommandResult] | None, optional): 子命令匹配结果
        """
        self._source = source
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.main_args = main_args or {}
        self.other_args = {}
        self.options = options or {}
        self.subcommands = subcommands or {}

    def _clr(self):
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def source(self):
        """返回命令源"""
        from .manager import command_manager
        return command_manager.get_command(self._source)

    @property
    def head_matched(self):
        """返回命令头是否匹配"""
        return self.header_match.matched

    @property
    def non_component(self) -> bool:
        """返回是否没有解析到任何组件"""
        return not self.subcommands and not self.options

    @property
    def components(self) -> dict[str, OptionResult | SubcommandResult]:
        """返回解析到的组件"""
        return {**self.options, **self.subcommands}

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    def _unpack_opts(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}

    def _unpack_subs(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}
            if _v.options:
                self._unpack_opts(_v.options)
            if _v.subcommands:
                self._unpack_subs(_v.subcommands)

    def unpack(self) -> None:
        """处理 `Arparma` 中的数据"""
        self._unpack_opts(self.options)
        self._unpack_subs(self.subcommands)

    def call(self, target: Callable[..., T], **additional) -> T:
        """依据 `Arparma` 中的数据调用函数

        Args:
            target (Callable[..., T]): 要调用的函数
            **additional (Any): 附加参数
        Returns:
            T: 函数返回值
        Raises:
            RuntimeError: 如果 Arparma 未匹配, 则抛出 RuntimeError
        """
        if self.matched:
            names = {p.name for p in get_signature(target)}
            return target(**{k: v for k, v in {**self.all_matched_args, **additional}.items() if k in names})
        raise RuntimeError

    def fail(self, exc: type[BaseException] | BaseException | str):
        """生成一个失败的 `Arparma`"""
        return Arparma(self._source, self.origin, False, self.header_match, error_info=exc)

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs if v is not None])
        else:
            attrs = {
                "matched": self.matched, "header_match": self.header_match,
                "options": self.options, "subcommands": self.subcommands,
                "main_args": self.main_args, "other_args": self.other_args
            }
            return ", ".join([f"{a}={v}" for a, v in attrs.items() if v])
