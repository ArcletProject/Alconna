from __future__ import annotations

import re
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generic, Set
from contextvars import ContextVar

from nepattern import AllParam, AnyOne, AnyString, BasePattern, all_patterns
from nepattern.util import TPattern
from tarina import Empty, lang, split, split_once
from typing_extensions import Self, TypeAlias

from .base import STRING, Args, Option, Subcommand, HeadResult, OptionResult, SubcommandResult, ArgumentMissing, NullMessage, ParamsUnmatched, Arparma
from .typing import TDC


if TYPE_CHECKING:
    from .main import Alconna


def handle_bracket(name: str, mapping: dict):
    """处理字符串中的括号对并转为正则表达式"""
    pattern_map = all_patterns()
    if len(parts := re.split(r"(\{.*?})", name)) <= 1:
        return name, False
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            res = part[1:-1].split(":")
            if not res or (len(res) > 1 and not res[1] and not res[0]):
                parts[i] = ".+?"
            elif len(res) == 1 or not res[1]:
                parts[i] = f"(?P<{res[0]}>.+)"
            elif not res[0]:
                parts[
                    i
                ] = f"{pattern_map[res[1]].pattern if res[1] in pattern_map else res[1]}"
            elif res[1] in pattern_map:
                mapping[res[0]] = pattern_map[res[1]]
                parts[i] = f"(?P<{res[0]}>{pattern_map[res[1]].pattern})"
            else:
                parts[i] = f"(?P<{res[0]}>{res[1]})"
    return "".join(parts), True


class Header:
    """命令头部的匹配表达式"""
    __slots__ = ("origin", "content", "mapping", "compact", "compact_pattern")

    def __init__(
        self,
        origin: tuple[str, list[str]],
        content: set[str] | TPattern,
        mapping: dict[str, BasePattern] | None = None,
        compact: bool = False,
        compact_pattern: TPattern | None = None,
    ):
        self.origin = origin
        self.content = content
        self.mapping = mapping or {}
        self.compact = compact
        self.compact_pattern = compact_pattern

    @classmethod
    def generate(cls, command: str, prefixes: list[str], compact: bool):
        mapping = {}
        if command.startswith("re:"):
            _cmd = command[3:]
            to_regex = True
        else:
            _cmd, to_regex = handle_bracket(command, mapping)
        if not prefixes:
            cmd = re.compile(_cmd) if to_regex else {_cmd}
            return cls((command, prefixes), cmd, mapping, compact, re.compile(f"^{_cmd}"))
        prf = "|".join(re.escape(h) for h in prefixes)
        compp = re.compile(f"^(?:{prf}){_cmd}")
        if to_regex:
            return cls((command, prefixes), re.compile(f"(?:{prf}){_cmd}"), mapping, compact, compp)
        return cls((command, prefixes), {f"{h}{_cmd}" for h in prefixes}, mapping, compact, compp)


@dataclass(repr=True)
class Argv(Generic[TDC]):
    """命令行参数"""
    preprocessors: dict[type, Callable[..., Any]] = field(default_factory=dict)
    """命令元素的预处理器"""
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    """将命令元素转换为文本, 或者返回None以跳过该元素"""
    separators: tuple[str, ...] = field(default=(' ',))
    """命令分隔符"""
    filter_out: list[type] = field(default_factory=list)
    """需要过滤掉的命令元素"""
    checker: Callable[[Any], bool] | None = field(default=None)
    """检查传入命令"""
    converter: Callable[[str | list], TDC] = field(default=lambda x: x)
    """将字符串或列表转为目标命令类型"""
    filter_crlf: bool = field(default=True)
    """是否过滤掉换行符"""
    param_ids: set[str] = field(default_factory=set)
    """节点名集合"""

    current_index: int = field(init=False)
    """当前数据的索引"""
    ndata: int = field(init=False)
    """原始数据的长度"""
    bak_data: list[str | Any] = field(init=False)
    """备份的原始数据"""
    raw_data: list[str | Any] = field(init=False)
    """原始数据"""
    origin: TDC = field(init=False)
    """原始命令"""
    _sep: tuple[str, ...] | None = field(init=False)

    _cache: ClassVar[dict[type, dict[str, Any]]] = {}

    def __post_init__(self):
        self.reset()
        if __cache := self.__class__._cache.get(self.__class__, {}):
            self.preprocessors.update(__cache.get("preprocessors") or {})
            self.filter_out.extend(__cache.get("filter_out") or [])
            self.to_text = __cache.get("to_text") or self.to_text
            self.checker = __cache.get("checker") or self.checker
            self.converter = __cache.get("converter") or self.converter

    def reset(self):
        """重置命令行参数"""
        self.current_index = 0
        self.ndata = 0
        self.bak_data = []
        self.raw_data = []
        self.origin = "None"
        self._sep = None

    @property
    def done(self) -> bool:
        """命令是否解析完毕"""
        return self.current_index == self.ndata

    def build(self, data: TDC) -> Self:
        """命令分析功能, 传入字符串或消息链

        Args:
            data (TDC): 命令

        Returns:
            Self: 自身
        """
        self.reset()
        if self.checker and not self.checker(data):
            raise TypeError(data)
        self.origin = data
        if data.__class__ is str:
            data = [data]  # type: ignore
        i = 0
        raw_data = self.raw_data
        for unit in data:
            if (utype := unit.__class__) in self.filter_out:
                continue
            if (proc := self.preprocessors.get(utype)) and (res := proc(unit)):
                unit = res
            if (text := self.to_text(unit)) is None:
                raw_data.append(unit)
            elif not (res := text.strip()):
                continue
            else:
                raw_data.append(res)
            i += 1
        if i < 1:
            raise NullMessage(lang.require("argv", "null_message").format(target=data))
        self.ndata = i
        self.bak_data = raw_data.copy()
        return self

    def next(self, separate: tuple[str, ...] | None = None, move: bool = True) -> tuple[str | Any, bool]:
        """获取解析需要的下个数据

        Args:
            separate (tuple[str, ...] | None, optional): 分隔符.
            move (bool, optional): 是否移动指针.

        Returns:
            tuple[str | Any, bool]: 下个数据, 是否是字符串.
        """
        if self._sep:
            self._sep = None
        if self.current_index == self.ndata:
            return "", True
        separate = separate or self.separators
        _current_data = self.raw_data[self.current_index]
        if _current_data.__class__ is str:
            _text, _rest_text = split_once(_current_data, separate, self.filter_crlf)  # type: ignore
            if move:
                if _rest_text:
                    self._sep = separate
                    self.raw_data[self.current_index] = _rest_text
                else:
                    self.current_index += 1
            return _text, True
        if move:
            self.current_index += 1
        return _current_data, False

    def rollback(self, data: str | Any, replace: bool = False):
        """把获取的数据放回 (实际只是`指针`移动)

        Args:
            data (str | Any): 数据.
            replace (bool, optional): 是否替换.
        """
        if data == "" or data is None:
            return
        if self._sep:
            _current_data = self.raw_data[self.current_index]
            self.raw_data[self.current_index] = f"{data}{self._sep[0]}{_current_data}"
            return
        if self.current_index >= 1:
            self.current_index -= 1
        if replace:
            self.raw_data[self.current_index] = data

    def release(self, separate: tuple[str, ...] | None = None, recover: bool = False) -> list[str | Any]:
        """获取剩余的数据

        Args:
            separate (tuple[str, ...] | None, optional): 分隔符.
            recover (bool, optional): 是否从头开始获取.

        Returns:
            list[str | Any]: 剩余的数据.
        """
        _result = []
        data = self.bak_data if recover else self.raw_data[self.current_index:]
        for _data in data:
            if _data.__class__ is str:
                _result.extend(split(_data, separate or (' ',)))
            else:
                _result.append(_data)
        return _result

    def data_set(self):
        return self.raw_data.copy(), self.current_index

    def data_reset(self, data: list[str | Any], index: int):
        self.raw_data = data
        self.current_index = index


def default_compiler(analyser: SubAnalyser, pids: set[str]):
    """默认的编译方法

    Args:
        analyser (SubAnalyser): 任意子解析器
        pids (set[str]): 节点名集合
    """
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            if opts.compact or not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(opts)
            for alias in opts.aliases:
                if (li := analyser.compile_params.get(alias)) and isinstance(li, SubAnalyser):
                    continue
                analyser.compile_params[alias] = opts
            if opts.default:
                analyser.default_opt_result[opts.dest] = opts.default
            pids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts)
            analyser.compile_params[opts.name] = sub
            pids.add(opts.name)
            default_compiler(sub, pids)
            if not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(sub)
            if sub.command.default:
                analyser.default_sub_result[opts.dest] = sub.command.default


@dataclass
class SubAnalyser(Generic[TDC]):
    """子解析器, 用于子命令的解析"""

    command: Subcommand
    """子命令"""
    default_main_only: bool = field(default=False)
    """命令是否只有主参数"""
    need_main_args: bool = field(default=False)
    """是否需要主参数"""
    compile_params: dict[str, Option | SubAnalyser[TDC]] = field(default_factory=dict)
    """编译的节点"""
    compact_params: list[Option | SubAnalyser[TDC]] = field(default_factory=list)
    """可能紧凑的需要逐个解析的节点"""
    self_args: Args = field(init=False)
    """命令自身参数"""
    subcommands_result: dict[str, SubcommandResult] = field(init=False)
    """子命令的解析结果"""
    options_result: dict[str, OptionResult] = field(init=False)
    """选项的解析结果"""
    args_result: dict[str, Any] = field(init=False)
    """参数的解析结果"""
    header_result: HeadResult | None = field(init=False)
    """头部的解析结果"""
    value_result: Any = field(init=False)
    """值的解析结果"""
    default_opt_result: dict[str, OptionResult] = field(default_factory=dict)
    """默认选项的解析结果"""
    default_sub_result: dict[str, SubcommandResult] = field(default_factory=dict)
    """默认子命令的解析结果"""

    def _clr(self):
        """清除自身的解析结果"""
        self.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __post_init__(self):
        self.reset()
        self.self_args = self.command.args
        if self.command.nargs > 0 and self.command.nargs > self.self_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = sum(arg.field.default is not None for arg in self.self_args.argument)
        if _de_count and _de_count == self.command.nargs:
            self.default_main_only = True

    def result(self) -> SubcommandResult:
        """生成子命令解析结果

        Returns:
            SubcommandResult: 子命令解析结果
        """
        if self.default_opt_result:
            handle_opt_default(self.default_opt_result, self.options_result)
        if self.default_sub_result:
            for k, v in self.default_sub_result.items():
                if k not in self.subcommands_result:
                    self.subcommands_result[k] = v
        res = SubcommandResult(
            self.value_result, self.args_result, self.options_result, self.subcommands_result
        )
        self.reset()
        return res

    def reset(self):
        """重置解析器"""
        self.args_result = {}
        self.options_result = {}
        self.subcommands_result = {}
        self.value_result = None
        self.header_result = None

    def process(self, argv: Argv[TDC]) -> Self:
        """处理传入的参数集合

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Self: 自身

        Raises:
            ParamsUnmatched: 名称不匹配
            FuzzyMatchSuccess: 模糊匹配成功
        """
        sub = argv.context = self.command
        name, _ = argv.next(sub.separators)
        if name != sub.name:  # 先匹配节点名称
            raise ParamsUnmatched(lang.require("subcommand", "name_error").format(target=name, source=sub.name))
        return self.analyse(argv)

    def analyse(self, argv: Argv[TDC]) -> Self:
        """解析传入的参数集合

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Self: 自身

        Raises:
            ArgumentMissing: 参数缺失
        """
        while analyse_param(self, argv, self.command.separators):
            pass
        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)
        if not self.args_result and self.need_main_args:
            raise ArgumentMissing(lang.require("subcommand", "args_missing").format(name=self.command.dest))
        return self


class Analyser(SubAnalyser[TDC], Generic[TDC]):
    """命令解析器"""
    command: Alconna
    """命令实例"""
    command_header: Header
    """命令头部"""

    def __init__(self, alconna: Alconna[TDC]):
        """初始化解析器

        Args:
            alconna (Alconna[TDC]): 命令实例
        """
        super().__init__(alconna)
        self.command_header = Header.generate(alconna.command, alconna.prefixes, alconna.meta.compact)

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.name}>"

    def process(self, argv: Argv[TDC]) -> Arparma[TDC]:
        """主体解析函数, 应针对各种情况进行解析

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Arparma[TDC]: Arparma 解析结果

        Raises:
            ValueError: 快捷命令查找失败
            ParamsUnmatched: 参数不匹配
            ArgumentMissing: 参数缺失
        """
        try:
            self.header_result = analyse_header(self.command_header, argv)
        except ParamsUnmatched as e:
            if self.command.meta.raise_exception:
                raise
            return self.export(argv, True, e)
        except RuntimeError as e:
            exc = ParamsUnmatched(lang.require("header", "error").format(target=argv.release(recover=True)[0]))
            if self.command.meta.raise_exception:
                raise exc from e
            return self.export(argv, True, exc)

        if fail := self.analyse(argv):
            return fail

        if argv.done and (not self.need_main_args or self.args_result):
            return self.export(argv)

        rest = argv.release()
        if len(rest) > 0:
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=argv.next(move=False)[0]))
        else:
            exc = ArgumentMissing(lang.require("analyser", "param_missing"))
        if self.command.meta.raise_exception:
            raise exc
        return self.export(argv, True, exc)

    def analyse(self, argv: Argv[TDC]) -> Arparma[TDC] | None:
        try:
            while analyse_param(self, argv) and argv.current_index != argv.ndata:
                pass
        except (ParamsUnmatched, ArgumentMissing) as e1:
            if self.command.meta.raise_exception:
                raise
            return self.export(argv, True, e1)

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)

    def export(
        self, argv: Argv[TDC], fail: bool = False, exception: BaseException | None = None,
    ) -> Arparma[TDC]:
        """创建 `Arparma` 解析结果, 其一定是一次解析的最后部分

        Args:
            argv (Argv[TDC]): 命令行参数
            fail (bool, optional): 是否解析失败. Defaults to False.
            exception (BaseException | None, optional): 解析失败时的异常. Defaults to None.
        """
        result = Arparma(argv.origin, not fail, self.header_result)
        if fail:
            result.error_info = exception or repr(traceback.format_exc(limit=1))
            result.error_data = argv.release()
        else:
            if self.default_opt_result:
                handle_opt_default(self.default_opt_result, self.options_result)
            if self.default_sub_result:
                for k, v in self.default_sub_result.items():
                    if k not in self.subcommands_result:
                        self.subcommands_result[k] = v
            result.main_args = self.args_result
            result.options = self.options_result
            result.subcommands = self.subcommands_result
            result.unpack()
        self.reset()
        return result  # type: ignore


TCompile: TypeAlias = Callable[[SubAnalyser, Set[str]], None]


def analyse_args(argv: Argv, args: Args) -> dict[str, Any]:
    """
    分析 `Args` 部分

    Args:
        argv (Argv): 命令行参数
        args (Args): 目标 `Args`

    Returns:
        dict[str, Any]: 解析结果
    """
    result: dict[str, Any] = {}
    for arg in args.argument:
        key = arg.name
        value = arg.value
        default_val = arg.field.default
        may_arg, _str = argv.next(arg.separators)
        if not may_arg or (_str and may_arg in argv.param_ids):
            argv.rollback(may_arg)
            if default_val is not None:
                result[key] = None if default_val is Empty else default_val
            elif value.__class__ is MultiVar and value.flag == '*':  # type: ignore
                result[key] = ()
            elif not arg.optional:
                raise ArgumentMissing(lang.require("args", "missing").format(key=key))
            continue
        if value == AllParam:
            argv.rollback(may_arg)
            result[key] = argv.converter(argv.release(arg.separators))
            argv.current_index = argv.ndata
            return result
        elif value == AnyOne:
            result[key] = may_arg
        elif value == AnyString:
            result[key] = str(may_arg)
        elif value == STRING and _str:
            result[key] = may_arg
        else:
            res = (
                value.invalidate(may_arg, default_val)
                if value.anti
                else value.validate(may_arg, default_val)
            )
            if res.flag != 'valid':
                argv.rollback(may_arg)
            if res.flag == 'error':
                if arg.optional:
                    continue
                raise ParamsUnmatched(*res.error.args)
            if not arg.anonymous:
                result[key] = res._value  # type: ignore
    return result


def handle_option(argv: Argv, opt: Option) -> tuple[str, OptionResult]:
    """
    处理 `Option` 部分

    Args:
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
    """
    error = True
    name, _ = argv.next(opt.separators)
    if opt.compact:
        for al in opt.aliases:
            if mat := re.fullmatch(f"{al}(?P<rest>.*?)", name):
                argv.rollback(mat.groupdict()['rest'], replace=True)
                error = False
                break
    elif name in opt.aliases:
        error = False
    if error:
        raise ParamsUnmatched(lang.require("option", "name_error").format(source=opt.name, target=name))
    name = opt.dest
    return (
        (name, OptionResult(None, analyse_args(argv, opt.args)))
        if opt.nargs else (name, OptionResult())
    )


def analyse_option(analyser: SubAnalyser, argv: Argv, opt: Option):
    """
    分析 `Option` 部分

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
    """
    opt_n, opt_v = handle_option(argv, opt)
    analyser.options_result[opt_n] = opt_v


def analyse_compact_params(analyser: SubAnalyser, argv: Argv):
    """分析紧凑参数

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
    """
    for param in analyser.compact_params:
        _data, _index = argv.data_set()
        try:
            if param.__class__ is Option:
                analyse_option(analyser, argv, param)
            else:
                try:
                    param.process(argv)
                finally:
                    analyser.subcommands_result[param.command.dest] = param.result()
            _data.clear()
            return True
        except ParamsUnmatched as e:
            argv.data_reset(_data, _index)


def handle_opt_default(defaults: dict[str, OptionResult], data: dict[str, OptionResult]):
    for k, v in defaults.items():
        if k not in data:
            data[k] = v
        if not v.args:
            continue
        for key, value in v.args.items():
            data[k].args.setdefault(key, value)


def analyse_param(analyser: SubAnalyser, argv: Argv, seps: tuple[str, ...] | None = None):
    """处理参数

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        seps (tuple[str, ...], optional): 指定的分隔符.
    """
    _text, _str = argv.next(seps, move=False)
    if not _str or not _text:
        _param = None
    elif _text in analyser.compile_params:
        _param = analyser.compile_params[_text]
    elif analyser.compact_params and (res := analyse_compact_params(analyser, argv)):
        if res.__class__ is str:
            raise ParamsUnmatched(res)
        return True
    else:
        _param = None
    if not _param and analyser.command.nargs and not analyser.args_result:
        analyser.args_result = analyse_args(argv, analyser.self_args)
        if analyser.args_result:
            argv.context = None
            return True
    if _param.__class__ is Option:
        analyse_option(analyser, argv, _param)
    elif _param is not None:
        try:
            _param.process(argv)
        finally:
            analyser.subcommands_result[_param.command.dest] = _param.result()
    else:
        return False
    return True


def analyse_header(header: Header, argv: Argv) -> HeadResult:
    """分析头部

    Args:
        header (Header): 头部
        argv (Argv): 命令行参数

    Returns:
        HeadResult: 分析结果
    """
    content = header.content
    mapping = header.mapping
    head_text, _str = argv.next()
    if not _str:
        raise ParamsUnmatched(lang.require("header", "error").format(target=head_text), None)
    if content.__class__ is set and head_text in content:
        return HeadResult(head_text, head_text, True, fixes=mapping)
    elif content.__class__ is TPattern and (mat := content.fullmatch(head_text)):
        return HeadResult(head_text, head_text, True, mat.groupdict(), mapping)
    if header.compact and content.__class__ in (set, TPattern) and (mat := header.compact_pattern.match(head_text)):
        argv.rollback(head_text[len(mat[0]):], replace=True)
        return HeadResult(mat[0], mat[0], True, mat.groupdict(), mapping)
    raise ParamsUnmatched(lang.require("header", "error").format(target=head_text), head_text)


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
    converter: Callable[[str | list], TDC] | None = None
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
    Argv._cache.setdefault(
        target or __argv_type__.get(), {}
    ).update({k: v for k, v in locals().items() if v is not None})
