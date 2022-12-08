from __future__ import annotations

import re
import traceback
from copy import copy
from typing import (
    TYPE_CHECKING, Any, Generic, TypeVar, Callable, ClassVar
)
from nepattern import pattern_map, type_parser, BasePattern
from nepattern.util import TPattern

from ..manager import command_manager
from ..exceptions import (
    NullMessage, ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess, CompletionTriggered, PauseTriggered
)
from ..args import Args, Arg
from ..base import Option, Subcommand, Sentence
from ..arparma import Arparma
from ..util import split_once, split
from ..typing import DataCollection, TDataCollection
from ..config import config
from ..components.output import output_manager
from .parts import analyse_args, analyse_option, analyse_subcommand, analyse_header, analyse_unmatch_params
from .special import handle_help, handle_shortcut, handle_completion

if TYPE_CHECKING:
    from ..core import Alconna


class Analyser(Generic[TDataCollection]):
    """ Alconna使用的分析器基类, 实现了一些通用的方法 """
    preprocessors: dict[str, Callable[..., Any]] = {}
    text_sign: str = 'text'
    alconna: Alconna  # Alconna实例
    context: Arg | Subcommand | Option | None
    current_index: int  # 当前数据的index
    bak_data: list[str | Any]
    raw_data: list[str | Any]
    ndata: int  # 原始数据的长度
    command_params: dict[str, Sentence | list[Option] | Subcommand]
    param_ids: set[str]
    # 命令头部
    command_header: (
        TPattern | BasePattern | list[tuple[Any, TPattern]] |
        tuple[tuple[list[Any], TPattern] | list[Any], TPattern | BasePattern]
    )
    separators: tuple[str, ...]  # 分隔符
    raise_exception: bool  # 是否抛出异常
    options: dict[str, Any]  # 存放解析到的所有选项
    subcommands: dict[str, Any]  # 存放解析到的所有子命令
    main_args: dict[str, Any]  # 主参数
    header: dict[str, Any] | bool | None  # 命令头部
    need_main_args: bool  # 是否需要主参数
    head_matched: bool  # 是否匹配了命令头部
    part_len: range  # 分段长度
    default_main_only: bool  # 默认只有主参数
    self_args: Args  # 自身参数
    filter_out: ClassVar[list[str]]  # 元素黑名单
    temporary_data: dict[str, Any]  # 临时数据
    temp_token: int  # 临时token
    used_tokens: set[int]  # 已使用的token
    sentences: list[str]  # 存放解析到的所有句子
    default_separate: bool
    message_cache: bool
    fuzzy_match: bool

    @staticmethod
    def generate_token(data: list[Any | list[str]]) -> int:
        return hash(str(data))

    def _clr(self):
        self.reset()
        self.used_tokens.clear()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __init__(self, alconna: Alconna):
        if not hasattr(self, 'filter_out'):
            self.filter_out = []  # type: ignore
        self.reset()
        self.used_tokens = set()
        self.alconna = alconna
        self.self_args = alconna.args
        self.separators = alconna.separators
        self.raise_exception = alconna.meta.raise_exception
        self.need_main_args = False
        self.default_main_only = False
        self.default_separate = True
        self.filter_crlf = not self.alconna.meta.keep_crlf
        self.fuzzy_match = alconna.meta.fuzzy_match
        self.message_cache = alconna.namespace_config.enable_message_cache
        self.param_ids = set()
        self.command_params = {}
        self.special = {}
        self.special.update(
            [(i, handle_help) for i in alconna.namespace_config.builtin_option_name['help']] +
            [(i, handle_completion) for i in alconna.namespace_config.builtin_option_name['completion']] +
            [(i, handle_shortcut) for i in alconna.namespace_config.builtin_option_name['shortcut']]
        )
        self.__handle_main_args__(alconna.args, alconna.nargs)
        self.__init_header__(alconna.command, alconna.headers)

    def __handle_main_args__(self, main_args: Args, nargs: int | None = None):
        nargs = nargs or len(main_args)
        if nargs > 0 and nargs > main_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = sum(arg.field.default_gen is not None for arg in main_args.argument)
        if _de_count and _de_count == nargs:
            self.default_main_only = True

    @staticmethod
    def __handle_bracket__(name: str):
        if len(parts := re.split(r"(\{.*?})", name)) <= 1:
            return name
        for i, part in enumerate(parts):
            if not part:
                continue
            if res := re.match(r"\{(.*?)}", part):
                if not res[1]:
                    parts[i] = ".+?"
                    continue
                if len(_parts := res[1].split(":")) == 1:
                    parts[i] = f"(?P<{_parts[0]}>.+?)"
                elif not _parts[0] and not _parts[1]:
                    parts[i] = ".+?"
                elif not _parts[0]:
                    parts[i] = f"{pattern_map[_parts[1]].pattern if _parts[1] in pattern_map else _parts[1]}"
                elif not _parts[1]:
                    parts[i] = f"(?P<{_parts[0]}>.+?)"
                else:
                    parts[i] = (
                        f"(?P<{_parts[0]}>{pattern_map[_parts[1]].pattern if _parts[1] in pattern_map else _parts[1]})"
                    )
        return "".join(parts)

    def __init_header__(
        self, command_name: str | type | BasePattern, headers: list[str | Any] | list[tuple[Any, str]]
    ):
        if isinstance(command_name, str):
            command_name = self.__handle_bracket__(command_name)

        _cmd_name, _cmd_str = (
            (re.compile(command_name), command_name) if isinstance(command_name, str) else
            (copy(type_parser(command_name)), str(command_name))
        )
        if not headers:
            self.command_header = _cmd_name  # type: ignore
        elif isinstance(headers[0], tuple):
            mixins = [(h[0], re.compile(re.escape(h[1]) + _cmd_str)) for h in headers]  # type: ignore
            self.command_header = mixins
        else:
            elements = []
            ch_text = ""
            for h in headers:
                if isinstance(h, str):
                    ch_text += f"{re.escape(h)}|"
                else:
                    elements.append(h)
            if not elements:
                if isinstance(_cmd_name, TPattern):
                    self.command_header = re.compile(f"(?:{ch_text[:-1]}){_cmd_str}")  # noqa
                else:
                    _cmd_name.pattern = f"(?:{ch_text[:-1]}){_cmd_name.pattern}"  # type: ignore
                    _cmd_name.regex_pattern = re.compile(_cmd_name.pattern)  # type: ignore
                    self.command_header = _cmd_name  # type: ignore
            elif not ch_text:
                self.command_header = (elements, _cmd_name)  # type: ignore
            else:
                self.command_header = (elements, re.compile(f"(?:{ch_text[:-1]})")), _cmd_name  # type: ignore # noqa

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.alconna.path}>"

    def reset(self):
        """重置分析器"""
        # self.current_index, self.content_index, self.ndata, self.temp_token = 0, 0, 0, 0
        self.current_index, self.ndata, self.temp_token = 0, 0, 0
        self.head_matched = False
        self.temporary_data, self.main_args, self.options, self.subcommands = {}, {}, {}, {}
        self.raw_data, self.bak_data, self.sentences = [], [], []
        self.header, self.context = None, None
        # self.head_pos = (0, 0)

    def push(self, *data: str | Any):
        for d in data:
            if not d:
                continue
            if isinstance(d, str) and isinstance(self.raw_data[-1], str):
                if self.current_index >= self.ndata:
                    self.current_index -= 1
                self.raw_data[-1] += f"{self.separators[0]}{d}"
            else:
                self.raw_data.append(d)
                self.ndata += 1
        self.bak_data = self.raw_data.copy()
        return self

    def popitem(self, separate: tuple[str, ...] | None = None, move: bool = True) -> tuple[str | Any, bool]:
        """获取解析需要的下个数据"""
        if self.temporary_data.get('sep'):
            del self.temporary_data['sep']
        if self.current_index == self.ndata:
            return "", True
        separate = separate or self.separators
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, str):
            _text, _rest_text = split_once(_current_data, separate, self.filter_crlf)
            if move:
                if _rest_text:
                    self.temporary_data['sep'] = separate
                    self.raw_data[self.current_index] = _rest_text
                else:
                    self.current_index += 1
            return _text, True
        if move:
            self.current_index += 1
        return _current_data, False

    def pushback(self, data: str | Any, replace: bool = False):
        """把 pop的数据放回 (实际只是‘指针’移动)"""
        if data in ("", None):
            return
        if sep := self.temporary_data.get('sep'):
            _current_data = self.raw_data[self.current_index]
            self.raw_data[self.current_index] = f"{data}{sep[0]}{_current_data}"
            return
        if self.current_index >= 1:
            self.current_index -= 1
        if replace:
            self.raw_data[self.current_index] = data

    def release(
        self, separate: tuple[str, ...] | None = None, recover: bool = False, move_head: bool = True
    ) -> list[str | Any]:
        _result = []
        if recover:
            data = self.bak_data
            if move_head:
                _d, self.raw_data = self.raw_data.copy(), data.copy()
                analyse_header(self)
                data, self.raw_data = self.raw_data, _d
        else:
            data = self.raw_data[self.current_index:]
        for _data in data:
            if isinstance(_data, str):
                _result.extend(split(_data, separate))
            else:
                _result.append(_data)
        return _result

    def process(self, data: DataCollection[str | Any]) -> Analyser:
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.temporary_data["origin"] = data
        if isinstance(data, str):
            data = [data]
        i, exc, raw_data = 0, None, self.raw_data
        for unit in data:
            if (uname := unit.__class__.__name__) in self.filter_out:
                continue
            if (proc := self.preprocessors.get(uname)) and (res := proc(unit)):
                unit = res
            if text := getattr(unit, self.text_sign, unit if isinstance(unit, str) else None):
                if not (res := text.strip()):
                    continue
                raw_data.append(res)
            else:
                raw_data.append(unit)
            i += 1
        if i < 1:
            exp = NullMessage(config.lang.analyser_handle_null_message.format(target=data))
            if self.raise_exception:
                raise exp
            self.temporary_data["fail"] = exp
        else:
            self.ndata = i
            self.bak_data = raw_data.copy()
            if self.message_cache:
                self.temp_token = self.generate_token(raw_data)
        return self

    def analyse(self, message: DataCollection[str | Any] | None = None, interrupt: bool = False) -> Arparma:
        """主体解析函数, 应针对各种情况进行解析"""
        if command_manager.is_disable(self.alconna):
            return self.export(fail=True)

        if self.ndata == 0 and not self.temporary_data.get('fail'):
            if not message:
                raise ValueError(config.lang.analyser_handle_null_message.format(target=message))
            self.process(message)
        if self.temporary_data.get('fail'):
            return self.export(fail=True, exception=self.temporary_data.get('exception'))
        if (res := command_manager.get_record(self.temp_token)) and self.temp_token in self.used_tokens:
            self.reset()
            return res
        try:
            self.header = analyse_header(self)
            # self.head_pos = self.current_index
        except ParamsUnmatched as e:
            self.current_index = 0
            try:
                _res = command_manager.find_shortcut(self.popitem(move=False)[0], self.alconna)
                self.reset()
                return _res if isinstance(_res, Arparma) else self.process(_res).analyse()
            except ValueError as exc:
                if self.raise_exception:
                    raise e from exc
                return self.export(fail=True, exception=e)
        except FuzzyMatchSuccess as Fuzzy:
            output_manager.get(self.alconna.name, lambda: str(Fuzzy)).handle(raise_exception=self.raise_exception)
            return self.export(fail=True)

        for _ in self.part_len:
            try:
                _text, _str = self.popitem(move=False)
                _param = _param if (_param := (self.command_params.get(_text) if _str and _text else Ellipsis)) else (
                    None if self.default_separate else analyse_unmatch_params(
                        self.command_params.values(), _text, self.fuzzy_match
                    )
                )
                if (not _param or _param is Ellipsis) and not self.main_args:
                    self.main_args = analyse_args(self, self.self_args, self.alconna.nargs)
                elif isinstance(_param, list):
                    for opt in _param:
                        if handler := self.special.get(opt.name):
                            return handler(self)
                        _data = self.raw_data.copy()
                        _index = self.current_index
                        try:
                            opt_n, opt_v = analyse_option(self, opt)
                            self.options[opt_n] = opt_v
                            _data.clear()
                            break
                        except Exception as e:
                            exc = e
                            self.raw_data = _data
                            self.current_index = _index
                            continue
                    else:
                        raise exc  # type: ignore  # noqa
                elif isinstance(_param, Subcommand):
                    self.subcommands.setdefault(*analyse_subcommand(self, _param))
                elif isinstance(_param, Sentence):
                    self.sentences.append(self.popitem()[0])
            except FuzzyMatchSuccess as e:
                output_manager.get(self.alconna.name, lambda: str(e)).handle(raise_exception=self.raise_exception)
                return self.export(fail=True)
            except CompletionTriggered as comp:
                return handle_completion(self, comp.args[0])
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if rest := self.release():
                    if rest[-1] in self.alconna.namespace_config.builtin_option_name['completion']:
                        return handle_completion(self, self.context)  # type: ignore
                    if handler := self.special.get(rest[-1]):
                        return handler(self)
                if interrupt and isinstance(e1, ArgumentMissing):
                    raise PauseTriggered from e1
                if self.raise_exception:
                    raise
                return self.export(fail=True, exception=e1)
            if self.current_index == self.ndata:
                break

        # 防止主参数的默认值被忽略
        if self.default_main_only and not self.main_args:
            self.main_args = analyse_args(self, self.self_args, self.alconna.nargs)

        if self.current_index == self.ndata and (not self.need_main_args or self.main_args):
            return self.export()

        rest = self.release()
        if len(rest) > 0:
            if rest[-1] in self.alconna.namespace_config.builtin_option_name['completion']:
                return handle_completion(self, rest[-2])
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if interrupt and isinstance(exc, ArgumentMissing):
            raise PauseTriggered
        if self.raise_exception:
            raise exc
        return self.export(fail=True, exception=exc)

    @staticmethod
    def converter(command: str) -> TDataCollection:
        return command  # type: ignore

    def export(self, exception: BaseException | None = None, fail: bool = False) -> Arparma[TDataCollection]:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arparma(self.alconna.path, self.temporary_data.pop("origin", "None"))
        result.head_matched = self.head_matched
        result.matched = not fail
        if fail:
            result.error_info = repr(exception or traceback.format_exc(limit=1))
            result.error_data = self.release()
        else:
            result.encapsulate_result(self.header, self.main_args, self.options, self.subcommands)
            if self.message_cache:
                command_manager.record(self.temp_token, result)  
                self.used_tokens.add(self.temp_token)
        self.reset()
        return result  # type: ignore


TAnalyser = TypeVar("TAnalyser", bound=Analyser)
