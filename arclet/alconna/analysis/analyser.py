import re
import traceback
from abc import ABCMeta, abstractmethod
from typing import Dict, Union, List, Optional, TYPE_CHECKING, Tuple, Any, Type, Callable, Pattern, Generic, TypeVar, \
    Set

from ..manager import command_manager
from ..exceptions import NullTextMessage
from ..base import Args, Option, Subcommand
from ..arpamar import Arpamar
from ..util import split_once, split
from ..types import DataUnit, DataCollection, pattern_map
from ..lang import lang_config

if TYPE_CHECKING:
    from ..main import Alconna

T_Origin = TypeVar('T_Origin')


class Analyser(Generic[T_Origin], metaclass=ABCMeta):
    """
    Alconna使用的分析器基类, 实现了一些通用的方法

    Attributes:
        current_index(int): 记录解析时当前数据的index
        content_index(int): 记录内部index
        head_matched: 是否匹配了命令头部
    """
    alconna: 'Alconna'  # Alconna实例
    current_index: int  # 当前数据的index
    content_index: int  # 内部index
    is_str: bool  # 是否是字符串
    # raw_data: Dict[int, Union[List[str], Any]]  # 原始数据
    raw_data: List[Union[Any, List[str]]]  # 原始数据
    ndata: int  # 原始数据的长度
    command_params: Dict[str, Union[Option, Subcommand]]  # 参数
    param_ids: List[str]
    # 命令头部
    command_header: Union[
        Pattern,
        Tuple[Union[Tuple[List[Any], Pattern], List[Any]], Pattern],
        List[Tuple[Any, Pattern]]
    ]
    separator: str  # 分隔符
    is_raise_exception: bool  # 是否抛出异常
    options: Dict[str, Any]  # 存放解析到的所有选项
    subcommands: Dict[str, Any]  # 存放解析到的所有子命令
    main_args: Dict[str, Any]  # 主参数
    header: Optional[Union[Dict[str, Any], bool]]  # 命令头部
    need_main_args: bool  # 是否需要主参数
    head_matched: bool  # 是否匹配了命令头部
    part_len: range  # 分段长度
    default_main_only: bool  # 默认只有主参数
    self_args: Args  # 自身参数
    ARGHANDLER_TYPE = Callable[["Analyser", Union[str, DataUnit], str, Type, Any, int, str, Dict[str, Any], bool], Any]
    arg_handlers: Dict[Type, ARGHANDLER_TYPE]
    filter_out: List[str]  # 元素黑名单
    temporary_data: Dict[str, Any]  # 临时数据
    origin_data: T_Origin  # 原始数据
    temp_token: int  # 临时token
    used_tokens: Set[int]  # 已使用的token

    def __init_subclass__(cls, **kwargs):
        cls.arg_handlers = {}
        for base in reversed(cls.__bases__):
            if issubclass(base, Analyser):
                cls.arg_handlers.update(getattr(base, "arg_handlers", {}))
        if not hasattr(cls, "filter_out"):
            raise TypeError(lang_config.analyser_filter_missing)

    @staticmethod
    def generate_token(data: List[Union[Any, List[str]]], hs=hash) -> int:
        return hs(str(data))

    @classmethod
    def add_arg_handler(cls, arg_type: Type, handler: Optional[ARGHANDLER_TYPE] = None):
        if handler:
            cls.arg_handlers[arg_type] = handler
            return handler

        def __wrapper(func):
            cls.arg_handlers[arg_type] = func
            return func

        return __wrapper

    def __init__(self, alconna: "Alconna"):
        self.reset()
        self.used_tokens = set()
        self.original_data = None
        self.alconna = alconna
        self.self_args = alconna.args
        self.separator = alconna.separator
        self.is_raise_exception = alconna.is_raise_exception
        self.need_main_args = False
        self.default_main_only = False
        self.__handle_main_args__(alconna.args, alconna.nargs)
        self.__init_header__(alconna.command, alconna.headers)

    def __handle_main_args__(self, main_args: Args, nargs: Optional[int] = None):
        nargs = nargs or len(main_args)
        if nargs > 0 and nargs > main_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = 0
        for k, a in main_args.argument.items():
            if a['default'] is not None:
                _de_count += 1
        if _de_count and _de_count == nargs:
            self.default_main_only = True

    def __init_header__(
            self,
            command_name: str,
            headers: Union[List[Union[str, DataUnit]], List[Tuple[DataUnit, str]]]
    ):
        if len(parts := re.split("({.*?})", command_name)) > 1:
            for i, part in enumerate(parts):
                if not part:
                    continue
                if res := re.match("{(.*?)}", part):
                    _res = res.group(1)
                    if not _res:
                        parts[i] = ".+?"
                        continue
                    _parts = _res.split(":")
                    if len(_parts) == 1:
                        parts[i] = f"(?P<{_parts[0]}>.+?)"
                    elif not _parts[0] and not _parts[1]:
                        parts[i] = ".+?"
                    elif not _parts[0] and _parts[1]:
                        parts[i] = f"{pattern_map.get(_parts[1], _parts[1])}".replace("(", "").replace(")", "")
                    elif _parts[0] and not _parts[1]:
                        parts[i] = f"(?P<{_parts[0]}>.+?)"
                    else:
                        parts[i] = f"(?P<{_parts[0]}>{pattern_map.get(_parts[1], _parts[1])})"
            command_name = "".join(parts)

        if headers != [""]:
            if isinstance(headers[0], tuple):
                mixins = []
                for h in headers:
                    mixins.append((h[0], re.compile(re.escape(h[1]) + command_name)))  # type: ignore
                self.command_header = mixins
            else:
                elements = []
                ch_text = ""
                for h in headers:
                    if isinstance(h, str):
                        ch_text += re.escape(h) + "|"
                    else:
                        elements.append(h)
                if not elements:
                    self.command_header = re.compile("(?:{})".format(ch_text[:-1]) + command_name)  # noqa
                elif not ch_text:
                    self.command_header = (elements, re.compile(command_name))
                else:
                    self.command_header = (
                        (elements, re.compile("(?:{})".format(ch_text[:-1]))), re.compile(command_name)  # noqa
                    )
        else:
            self.command_header = re.compile(command_name)

    @staticmethod
    def default_params_generator(analyser: "Analyser"):
        analyser.param_ids = []
        analyser.command_params = {}
        for opts in analyser.alconna.options:
            if isinstance(opts, Subcommand):
                analyser.param_ids.append(opts.name)
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
                    analyser.param_ids.extend(sub_opts.aliases)
                opts.sub_part_len = range(len(opts.options) + 1)
            else:
                analyser.param_ids.extend(opts.aliases)
            analyser.command_params[opts.name] = opts
        analyser.part_len = range(len(analyser.command_params) + 1)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def __del__(self):
        self.reset()

    def reset(self):
        """重置分析器"""
        self.current_index = 0
        self.content_index = 0
        self.is_str = False
        self.options = {}
        self.main_args = {}
        self.subcommands = {}
        self.temporary_data = {}
        self.header = None
        self.raw_data = []
        self.head_matched = False
        self.ndata = 0
        self.original_data = None
        self.temp_token = 0

    def next_data(self, separate: Optional[str] = None, pop: bool = True) -> Tuple[Union[str, Any], bool]:
        """获取解析需要的下个数据"""
        if "separator" in self.temporary_data:
            self.temporary_data.pop("separator", None)
        if self.current_index == self.ndata:
            return "", True
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, list):
            _rest_text: str = ""
            _text = _current_data[self.content_index]
            if separate and separate != self.separator:
                _text, _rest_text = split_once(_text, separate)
            if pop:
                if _rest_text:  # 这里实际上还是pop了
                    self.temporary_data["separator"] = separate
                    _current_data[self.content_index] = _rest_text  # self.raw_data[self.current_index]
                else:
                    self.content_index += 1
            if len(_current_data) == self.content_index:
                self.current_index += 1
                self.content_index = 0
            return _text, True
        if pop:
            self.current_index += 1
        return _current_data, False

    def rest_count(self, separate: Optional[str] = None) -> int:
        """获取剩余的数据个数"""
        _result = 0
        for _data in self.raw_data[self.current_index:]:
            if isinstance(_data, list):
                for s in _data[self.content_index:]:
                    if separate and separate != self.separator:
                        _result += len(split(s, separate))
                    else:
                        _result += 1
            else:
                _result += 1
        return _result

    def reduce_data(self, data: Union[str, Any], replace=False):
        """把pop的数据放回 (实际只是‘指针’移动)"""
        if not data:
            return
        if self.current_index == self.ndata:
            self.current_index -= 1
            if isinstance(data, str):
                self.content_index = len(self.raw_data[self.current_index]) - 1
            if replace:
                if isinstance(data, str):
                    self.raw_data[self.current_index][self.content_index] = data
                else:
                    self.raw_data[self.current_index] = data
        else:
            _current_data = self.raw_data[self.current_index]
            if isinstance(_current_data, list) and isinstance(data, str):
                if sep := self.temporary_data.get("separator", None):
                    _current_data[self.content_index] = f"{data}{sep}{_current_data[self.content_index]}"
                else:
                    self.content_index -= 1
                    if replace:
                        _current_data[self.content_index] = data
            else:
                self.current_index -= 1
                if replace:
                    self.raw_data[self.current_index] = data

    def recover_raw_data(self) -> List[Union[str, Any]]:
        """将处理过的命令数据大概还原"""
        _result = []
        for _data in self.raw_data[self.current_index:]:
            if isinstance(_data, list):
                _result.append(f'{self.separator}'.join(_data[self.content_index:]))
            else:
                _result.append(_data)
        self.current_index = self.ndata
        self.content_index = 0
        return _result

    def process_message(self, data: Union[str, DataCollection]) -> 'Analyser':
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.original_data = data
        if isinstance(data, str):
            self.is_str = True
            if not (res := split(data.lstrip(), self.separator)):
                exp = NullTextMessage(lang_config.analyser_handle_null_message.format(target=data))
                if self.is_raise_exception:
                    raise exp
                self.temporary_data["fail"] = exp
            else:
                self.raw_data = [res]
                self.ndata = 1
                self.temp_token = self.generate_token(self.raw_data)
        else:
            separate = self.separator
            i, __t, exc = 0, False, None
            raw_data = []
            for unit in data:  # type: ignore
                if text := getattr(unit, 'text', None):
                    if not (res := split(text.lstrip(), separate)):
                        continue
                    raw_data.append(res)
                    __t = True
                elif isinstance(unit, str):
                    if not (res := split(unit.lstrip(), separate)):
                        continue
                    raw_data.append(res)
                    __t = True
                elif unit.__class__.__name__ not in self.filter_out:
                    raw_data.append(unit)
                else:
                    continue
                i += 1
            if __t is False:
                exp = NullTextMessage(lang_config.analyser_handle_null_message.format(target=data))
                if self.is_raise_exception:
                    raise exp
                self.temporary_data["fail"] = exp
            else:
                self.raw_data = raw_data
                self.ndata = i
                self.temp_token = self.generate_token(raw_data)
        return self

    @abstractmethod
    def analyse(self, message: Union[str, DataCollection, None] = None) -> Arpamar:
        """主体解析函数, 应针对各种情况进行解析"""
        pass

    @abstractmethod
    def add_param(self, opt):
        """临时增加解析用参数"""
        pass

    def create_arpamar(self, exception: Optional[BaseException] = None, fail: bool = False) -> Arpamar:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arpamar()
        result.head_matched = self.head_matched
        if fail:
            tb = traceback.format_exc(limit=1)
            result.error_info = repr(exception) or repr(tb)
            result.error_data = self.recover_raw_data()
            result.matched = False
        else:
            result.matched = True
            result.encapsulate_result(self.header, self.main_args, self.options, self.subcommands)
            command_manager.record(self.temp_token, self.original_data, self.alconna.path, result)
            self.used_tokens.add(self.temp_token)
        self.reset()
        return result
