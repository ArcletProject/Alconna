import re
from abc import ABCMeta, abstractmethod
from typing import Dict, Union, List, Optional, TYPE_CHECKING, Tuple, Any, Type, Callable
from ..base import Args
from ..exceptions import NullTextMessage, UnexpectedElement
from ..component import Option, Subcommand, Arpamar
from ..util import split_once, split, chain_texts, elements_whitelist, raw_type, elements_blacklist
from ..types import NonTextElement, ArgPattern, MessageChain, Gettable

if TYPE_CHECKING:
    from ..main import Alconna


class Analyser(metaclass=ABCMeta):
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
    raw_data: Dict[int, Union[List[str], NonTextElement]]  # 原始数据
    ndata: int  # 原始数据的长度
    params: Dict[str, Union[Option, Subcommand, Args]]  # 参数
    command_header: Union[ArgPattern, Tuple[List[NonTextElement], ArgPattern]]  # 命令头部
    separator: str  # 分隔符
    is_raise_exception: bool  # 是否抛出异常
    options: Dict[str, Any]  # 存放解析到的所有选项
    subcommands: Dict[str, Any]  # 存放解析到的所有子命令
    main_args: Dict[str, Any]  # 主参数
    header: Optional[str]  # 命令头部
    need_main_args: bool  # 是否需要主参数
    head_matched: bool  # 是否匹配了命令头部
    part_len: range  # 分段长度
    default_main_only: bool  # 默认只有主参数
    self_args: Args  # 自身参数
    ARGHANDLER_TYPE = Callable[["Analyser", Union[str, NonTextElement], str, Type, Any, int, str, Dict[str, Any]], Any]
    arg_handlers: Dict[Type, ARGHANDLER_TYPE]

    def __init_subclass__(cls, **kwargs):
        cls.arg_handlers = {}
        for base in reversed(cls.__bases__):
            if issubclass(base, Analyser):
                cls.arg_handlers.update(getattr(base, "arg_handlers", {}))

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
        self.alconna = alconna
        self.self_args = alconna.args
        self.separator = alconna.separator
        self.is_raise_exception = alconna.is_raise_exception
        self.need_main_args = False
        self.default_main_only = False
        self.__handle_main_args(alconna.args, alconna.nargs)
        self.__init_header__(alconna.command, alconna.headers)

    def __handle_main_args(self, main_args: Args, nargs: int = None):
        nargs = nargs or len(main_args)
        if nargs > 0:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = 0
        for k, a in main_args.argument.items():
            if a['default'] is not None:
                _de_count += 1
        if _de_count and _de_count == nargs:
            self.default_main_only = True

    def __init_header__(self, command_name: str, headers: List[Union[str, NonTextElement]]):
        if headers != [""]:
            elements = []
            ch_text = ""
            for h in headers:
                if isinstance(h, str):
                    ch_text += re.escape(h) + "|"
                else:
                    elements.append(h)
            pattern = "(?:{})".format(ch_text[:-1]) + command_name
            self.command_header = (elements, ArgPattern(pattern)) if elements else ArgPattern(pattern)
        else:
            self.command_header = ArgPattern(command_name)

    @staticmethod
    def default_params_generator(analyser: "Analyser"):
        analyser.params = {}  # "main_args": analyser.alconna.args
        for opts in analyser.alconna.options:
            if isinstance(opts, Subcommand):
                opts.sub_params.setdefault('sub_args', opts.args)
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
                opts.sub_part_len = range(len(opts.options) + opts.nargs)
            analyser.params[opts.name] = opts
        analyser.part_len = range(len(analyser.params) + 1)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def reset(self):
        """重置分析器"""
        self.current_index = 0
        self.content_index = 0
        self.is_str = False
        self.options = {}
        self.main_args = {}
        self.subcommands = {}
        self.header = None
        self.raw_data = {}
        self.head_matched = False
        self.ndata = 0

    def next_data(self, separate: Optional[str] = None, pop: bool = True) -> Union[str, NonTextElement]:
        """获取解析需要的下个数据"""
        _text: str = ""  # 重置
        _rest_text: str = ""

        if self.current_index == self.ndata:
            return ""
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, list):
            _text = _current_data[self.content_index]
            if separate and separate != self.separator:
                _text, _rest_text = split_once(_text, separate)
            if pop:
                if _rest_text:  # 这里实际上还是pop了
                    self.raw_data[self.current_index][self.content_index] = _rest_text
                else:
                    self.content_index += 1
            if len(_current_data) == self.content_index:
                self.current_index += 1
                self.content_index = 0
            return _text
        if pop:
            self.current_index += 1
        return _current_data

    def rest_count(self, separate: Optional[str] = None) -> int:
        """获取剩余的数据个数"""
        _result = 0
        for i in self.raw_data:
            if i < self.current_index:
                continue
            if isinstance(self.raw_data[i], list):
                for s in self.raw_data[i][self.content_index:]:
                    if separate and self.separator != separate:
                        _result += len(split(s, separate))
                    _result += 1
            else:
                _result += 1
        return _result

    def reduce_data(self, data: Union[str, NonTextElement]):
        """把pop的数据放回 (实际只是‘指针’移动)"""
        if data:
            if self.current_index == self.ndata:
                self.current_index -= 1
                if isinstance(data, str):
                    self.content_index = len(self.raw_data[self.current_index]) - 1
            else:
                _current_data = self.raw_data[self.current_index]
                if isinstance(_current_data, list) and isinstance(data, str):
                    self.content_index -= 1
                else:
                    self.current_index -= 1

    def recover_raw_data(self) -> List[Union[str, NonTextElement]]:
        """将处理过的命令数据大概还原"""
        _result = []
        for i in self.raw_data:
            if i < self.current_index:
                continue
            if isinstance(self.raw_data[i], list):
                _result.append(f'{self.separator}'.join(self.raw_data[i][self.content_index:]))
            else:
                _result.append(self.raw_data[i])
        self.current_index = self.ndata
        self.content_index = 0
        return _result

    def handle_message(self, data: Union[str, MessageChain]) -> Optional[Arpamar]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        if isinstance(data, str):
            self.is_str = True
            if not data.lstrip():
                if self.is_raise_exception:
                    raise NullTextMessage("传入了空的字符串")
                return self.create_arpamar(fail=True, exception=NullTextMessage("传入了空的字符串"))
            self.raw_data[0] = split(data, self.separator)
            self.ndata = 1
        else:
            separate = self.separator
            is_raise_exception = self.is_raise_exception
            i, _tc = 0, 0
            exc = None
            raw_data: Dict[int, Any] = {}
            for ele in data:
                e_type = ele.__class__.__name__
                if e_type in chain_texts and (res := split(ele.text.lstrip(' '), separate)):
                    raw_data[i] = res
                    _tc += 1
                elif e_type in elements_whitelist:
                    raw_data[i] = ele
                elif e_type in raw_type:
                    if isinstance(ele, Gettable):
                        if ele.get('type') in chain_texts and (res := split(ele.get('text').lstrip(' '), separate)):
                            raw_data[i] = res
                            _tc += 1
                        elif ele.get('type') in elements_whitelist or ele.get('type') not in elements_blacklist:
                            raw_data[i] = ele
                        else:
                            exc = UnexpectedElement(f"{e_type}({ele})")
                            continue
                    elif e_type == "str" and (res := split(ele.lstrip(' '), separate)):
                        raw_data[i] = res
                        _tc += 1
                    else:
                        exc = UnexpectedElement(f"{e_type}({ele})")
                        continue
                elif e_type not in elements_blacklist:
                    raw_data[i] = ele
                else:
                    exc = UnexpectedElement(f"{e_type}({ele})")
                    continue
                i += 1
            if _tc == 0:
                if is_raise_exception:
                    raise NullTextMessage("传入了一个无法获取文本的消息链")
                return self.create_arpamar(fail=True, exception=NullTextMessage("传入了一个无法获取文本的消息链"))
            if exc:
                if is_raise_exception:
                    raise exc
                return self.create_arpamar(fail=True, exception=exc)
            self.raw_data = raw_data
            self.ndata = i

    @abstractmethod
    def analyse(self, message: Union[str, MessageChain] = None):
        """主体解析函数, 应针对各种情况进行解析"""
        pass

    @abstractmethod
    def create_arpamar(self, exception: Optional[BaseException] = None, fail: bool = False):
        """创建arpamar, 其一定是一次解析的最后部分"""
        pass

    @abstractmethod
    def add_param(self, opt):
        """临时增加解析用参数"""
        pass
