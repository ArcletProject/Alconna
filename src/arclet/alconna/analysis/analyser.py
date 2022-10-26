import re
import traceback
from weakref import finalize
from copy import copy
from typing import (
    Dict, Union, List, Optional, TYPE_CHECKING, Tuple, Any, Generic, TypeVar, Set, Callable
)
from nepattern import pattern_map, type_parser, BasePattern
from nepattern.util import TPattern

from ..exceptions import (
    NullMessage, ParamsUnmatched, ArgumentMissing, PauseTriggered
)
from ..args import Args
from ..base import Option, Subcommand, Sentence, StrMounter
from ..arpamar import Arpamar
from ..action import action_handler
from ..util import split_once, split
from ..typing import DataCollection, TDataCollection
from ..config import config
from ..output import output_manager
from .parts import analyse_args, analyse_option, analyse_subcommand, analyse_header, analyse_unmatch_params

if TYPE_CHECKING:
    from ..core import Alconna

T_Origin = TypeVar('T_Origin')


class Analyser(Generic[T_Origin]):
    """ Alconna使用的分析器基类, 实现了一些通用的方法 """
    preprocessors: Dict[str, Callable[..., Any]] = {}
    text_sign: str = 'text'

    def __init__(self, alconna: "Alconna"):
        if not hasattr(self, 'filter_out'):
            self.filter_out = []
        self.reset()
        self.used_tokens = set()
        self.origin_data = None
        self.alconna = alconna
        self.self_args = alconna.args
        self.separators = alconna.separators
        self.raise_exception = alconna.meta.raise_exception
        self.need_main_args = False
        self.default_main_only = False
        self.default_separate = True
        self.message_cache = alconna.namespace_config.enable_message_cache
        self.param_ids = set()
        self.command_params = {}
        self.__handle_main_args__(alconna.args, alconna.nargs)
        self.__init_header__(alconna.command, alconna.headers)
        self.__init_actions__()

        def _clr(a: 'Analyser'):
            a.reset()
            a.used_tokens.clear()
            del a.origin_data
            del a.alconna

        finalize(self, _clr, self)

    def __handle_main_args__(self, main_args: Args, nargs: Optional[int] = None):
        nargs = nargs or len(main_args)
        if nargs > 0 and nargs > main_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = sum(a['field'] is not None for k, a in main_args.argument.items())
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
                        f"(?P<{_parts[0]}>"
                        f"{pattern_map[_parts[1]].pattern if _parts[1] in pattern_map else _parts[1]})"
                    )
        return "".join(parts)

    def __init_header__(
            self,
            command_name: Union[str, type, BasePattern],
            headers: Union[List[Union[str, Any]], List[Tuple[Any, str]]]
    ):
        if isinstance(command_name, str):
            command_name = self.__handle_bracket__(command_name)

        _command_name, _command_str = (
            (re.compile(command_name), command_name) if isinstance(command_name, str) else
            (copy(type_parser(command_name)), str(command_name))
        )
        if not headers:
            self.command_header = _command_name  # type: ignore
        elif isinstance(headers[0], tuple):
            mixins = [(h[0], re.compile(re.escape(h[1]) + _command_str)) for h in headers]  # type: ignore
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
                if isinstance(_command_name, TPattern):
                    self.command_header = re.compile(f"(?:{ch_text[:-1]}){_command_str}")  # noqa
                else:
                    _command_name.pattern = f"(?:{ch_text[:-1]}){_command_name.pattern}"  # type: ignore
                    _command_name.regex_pattern = re.compile(_command_name.pattern)  # type: ignore
                    self.command_header = _command_name  # type: ignore
            elif not ch_text:
                self.command_header = (elements, _command_name)  # type: ignore
            else:
                self.command_header = (
                                      elements, re.compile(f"(?:{ch_text[:-1]})")), _command_name  # type: ignore # noqa

    def __init_actions__(self):
        actions = self.alconna.action_list
        actions['main'] = self.alconna.action
        for opt in self.alconna.options:
            if isinstance(opt, Option) and opt.action:
                actions['options'][opt.dest] = opt.action
            if isinstance(opt, Subcommand):
                if opt.action:
                    actions['subcommands'][opt.dest] = opt.action
                for option in opt.options:
                    if option.action:
                        actions['subcommands'][f"{opt.dest}.{option.dest}"] = option.action

    @staticmethod
    def _compile_opts(option: Option, data: Dict[str, Union[Sentence, List[Option]]]):
        for alias in option.aliases:
            if (li := data.get(alias)) and isinstance(li, list):
                li.append(option)  # type: ignore
                li.sort(key=lambda x: x.priority, reverse=True)
            else:
                data[alias] = [option]

    @staticmethod
    def default_params_parser(analyser: "Analyser"):
        require_len = 0
        for opts in analyser.alconna.options:
            if isinstance(opts, Option):
                analyser._compile_opts(opts, analyser.command_params)  # type: ignore
                analyser.param_ids.update(opts.aliases)
            elif isinstance(opts, Subcommand):
                sub_require_len = 0
                analyser.command_params[opts.name] = opts
                analyser.param_ids.add(opts.name)
                for sub_opts in opts.options:
                    analyser._compile_opts(sub_opts, opts.sub_params)
                    if sub_opts.requires:
                        sub_require_len = max(len(sub_opts.requires), sub_require_len)
                        for k in sub_opts.requires:
                            opts.sub_params.setdefault(k, Sentence(name=k))
                    analyser.param_ids.update(sub_opts.aliases)
                opts.sub_part_len = range(len(opts.options) + (1 if opts.nargs else 0) + sub_require_len)
            if not analyser.separators.issuperset(opts.separators):
                analyser.default_separate &= False
            if opts.requires:
                analyser.param_ids.update(opts.requires)
                require_len = max(len(opts.requires), require_len)
                for k in opts.requires:
                    analyser.command_params.setdefault(k, Sentence(name=k))
            analyser.part_len = range(
                len(analyser.alconna.options) + (1 if analyser.need_main_args else 0) + require_len
            )

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.alconna.path}>"

    def reset(self):
        """重置分析器"""
        self.current_index, self.content_index, self.ndata, self.temp_token = 0, 0, 0, 0
        self.is_str, self.head_matched = False, False
        self.temporary_data, self.main_args, self.options, self.subcommands = {}, {}, {}, {}
        self.raw_data, self.sentences = [], []
        self.origin_data, self.header, self.context = None, None, None
        self.head_pos = (0, 0)

    def push(self, *data: Union[str, Any]):
        for d in data:
            if not d:
                continue
            if isinstance(d, str) and isinstance(self.raw_data[-1], StrMounter):
                if self.current_index == self.ndata:
                    self.current_index -= 1
                    self.content_index = len(self.raw_data[-1]) - 1
                self.raw_data[-1].append(d)
            else:
                self.raw_data.append(StrMounter([d]) if isinstance(d, str) else d)
                self.ndata += 1
        return self

    def popitem(self, separate: Optional[Set[str]] = None, move: bool = True) -> Tuple[Union[str, Any], bool]:
        """获取解析需要的下个数据"""
        if self.current_index == self.ndata:
            return "", True
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, StrMounter):
            _rest_text: str = ""
            _text = _current_data[self.content_index]
            if separate and not self.separators.issuperset(separate):
                _text, _rest_text = split_once(_text, tuple(separate))
            if move:
                self.content_index += 1
                if _rest_text:
                    _current_data[self.content_index - 1] = _text
                    _current_data.insert(self.content_index, _rest_text)
            if len(_current_data) == self.content_index:
                self.current_index += 1
                self.content_index = 0
            return _text, True
        if move:
            self.current_index += 1
        return _current_data, False

    def pushback(self, data: Union[str, Any], replace=False):
        """把 pop的数据放回 (实际只是‘指针’移动)"""
        if not data:
            return
        if self.current_index >= 1:
            self.current_index -= 1
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, StrMounter):
            if self.content_index == 0:
                self.content_index = len(_current_data) - 1
            else:
                self.content_index -= 1
        if replace:
            if isinstance(data, str):
                _current_data[self.content_index] = data
            else:
                self.raw_data[self.current_index] = data

    def release(self, separate: Optional[Set[str]] = None, recover: bool = False) -> List[Union[str, Any]]:
        _result = []
        is_cur = False
        for _data in self.raw_data[0 if recover else self.current_index:]:
            if isinstance(_data, StrMounter):
                for s in _data[0 if is_cur or recover else self.content_index:]:
                    if separate and not self.separators.issuperset(separate):
                        _result.extend(split(s, tuple(separate)))
                    else:
                        _result.append(s)
                    is_cur = True
            else:
                _result.append(_data)
        return _result

    def process(self, data: DataCollection[Union[str, Any]]) -> 'Analyser':
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.origin_data = data
        if isinstance(data, str):
            self.is_str = True
            data = [data]
        i, exc = 0, None
        keep_crlf = not self.alconna.meta.keep_crlf
        raw_data = self.raw_data
        for unit in data:
            if (uname := unit.__class__.__name__) in self.filter_out:
                continue
            if (proc := self.preprocessors.get(uname)) and (res := proc(unit)):
                unit = res
            if text := getattr(unit, self.text_sign, unit if isinstance(unit, str) else None):
                if not (res := split(text.strip(), tuple(self.separators), keep_crlf)):
                    continue
                raw_data.append(StrMounter(res))
            else:
                raw_data.append(unit)
            i += 1
        if i < 1:
            exp = NullMessage(config.lang.analyser_handle_null_message.format(target=data))
            if self.raise_exception:
                raise exp
            self.temporary_data["fail"] = exp
        else:
            self.ndata = 1
        return self

    def analyse(
            self,
            message: Union[DataCollection[Union[str, Any]], None] = None,
            interrupt: bool = False
    ) -> Arpamar:
        """主体解析函数, 应针对各种情况进行解析"""
        if self.ndata == 0 and not self.temporary_data.get('fail'):
            if not message:
                raise ValueError(config.lang.analyser_handle_null_message.format(target=message))
            self.process(message)
        if self.temporary_data.get('fail'):
            return self.export(fail=True, exception=self.temporary_data.get('exception'))
        try:
            self.header = analyse_header(self)
            self.head_pos = self.current_index, self.content_index
        except ParamsUnmatched as e:
            self.current_index = 0
            self.content_index = 0
            if self.raise_exception:
                raise e
            return self.export(fail=True, exception=e)

        for _ in self.part_len:
            try:
                _text, _str = self.popitem(move=False)
                _param = _param if (_param := (self.command_params.get(_text) if _str and _text else Ellipsis)) else (
                    None if self.default_separate else analyse_unmatch_params(
                        self.command_params.values(), _text
                    )
                )
                if (not _param or _param is Ellipsis) and not self.main_args:
                    self.main_args = analyse_args(self, self.self_args)
                elif isinstance(_param, list):
                    for opt in _param:
                        if opt.name == "--help":
                            self.current_index, self.content_index = self.head_pos
                            _help_param = [str(i) for i in self.release() if i not in {"-h", "--help"}]

                            def _get_help():
                                formatter = self.alconna.formatter_type(self.alconna)
                                return formatter.format_node(_help_param)

                            output_manager.get(self.alconna.name, _get_help).handle(
                                is_raise_exception=self.raise_exception)
                            return self.export(fail=True)
                        _current_index, _content_index = self.current_index, self.content_index
                        try:
                            opt_n, opt_v = analyse_option(self, opt)
                            self.options[opt_n] = opt_v
                            break
                        except Exception as e:
                            exc = e
                            self.current_index, self.content_index = _current_index, _content_index
                            continue
                    else:
                        raise exc  # type: ignore  # noqa
                elif isinstance(_param, Subcommand):
                    self.subcommands.setdefault(*analyse_subcommand(self, _param))
                elif isinstance(_param, Sentence):
                    self.sentences.append(self.popitem()[0])
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if rest := self.release():
                    if rest[-1] in ("--help", "-h"):
                        self.current_index, self.content_index = self.head_pos
                        _help_param = [str(i) for i in self.release() if i not in {"-h", "--help"}]

                        def _get_help():
                            formatter = self.alconna.formatter_type(self.alconna)
                            return formatter.format_node(_help_param)

                        output_manager.get(self.alconna.name, _get_help).handle(
                            is_raise_exception=self.raise_exception)
                        return self.export(fail=True)
                if interrupt and isinstance(e1, ArgumentMissing):
                    raise PauseTriggered from e1
                if self.raise_exception:
                    raise
                return self.export(fail=True, exception=e1)
            if self.current_index == self.ndata:
                break

        # 防止主参数的默认值被忽略
        if self.default_main_only and not self.main_args:
            self.main_args = analyse_args(self, self.self_args)

        if self.current_index == self.ndata and (not self.need_main_args or self.main_args):
            return self.export()

        rest = self.release()
        if len(rest) > 0:
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if interrupt and isinstance(exc, ArgumentMissing):
            raise PauseTriggered
        if self.raise_exception:
            raise exc
        return self.export(fail=True, exception=exc)

    @staticmethod
    def converter(command: str) -> T_Origin:
        return command  # type: ignore

    def export(self, exception: Optional[BaseException] = None, fail: bool = False) -> Arpamar[T_Origin]:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arpamar(self.alconna)
        result.head_matched = self.head_matched
        result.matched = not fail
        if fail:
            result.error_info = repr(exception or traceback.format_exc(limit=1))
            result.error_data = self.release()
        else:
            result.encapsulate_result(self.header, self.main_args, self.options, self.subcommands)
            action_handler(result)
        self.reset()
        return result


TAnalyser = TypeVar("TAnalyser", bound=Analyser)


def compile(alconna: "Alconna") -> Analyser:
    _analyser = alconna.analyser_type(alconna)
    Analyser.default_params_parser(_analyser)
    return _analyser


def analyse(alconna: "Alconna", command: TDataCollection) -> "Arpamar[TDataCollection]":
    return compile(alconna).process(command).analyse().execute()
