"""Alconna 核心"""
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Dict, Any, Union, List, Optional, TYPE_CHECKING
from .actions import ArgAction
from .base import Args
from .component import Option, Subcommand, Arpamar
from .util import split_once
from .types import NonTextElement, ArgPattern, AllParam, AnyParam, PatternToken
from .exceptions import ParamsUnmatched

if TYPE_CHECKING:
    from .main import Alconna


class CommandAnalyser(metaclass=ABCMeta):
    """Alconna使用的分析器"""
    current_index: int  # 记录解析时当前数据的index
    content_index: int  # 记录内部index
    is_str: bool  # 是否解析的是string
    raw_data: Dict[int, Union[List[str], NonTextElement]]
    ndata: int
    separator: str
    is_raise_exception: bool
    params: Dict[str, Union[Args, Option, Subcommand]]
    command_headers: List[Union[ArgPattern, List[Union[NonTextElement, ArgPattern]]]]

    def next_data(self, separate: Optional[str] = None, pop: bool = True) -> Union[str, NonTextElement]:
        """获取解析需要的下个数据"""
        _text: str = ""  # 重置
        _rest_text: str = ""

        if self.current_index == self.ndata:
            return ""
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, list):
            _text = _current_data[self.content_index]
            if separate != self.separator:
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

    def reduce_data(self, data: Union[str, NonTextElement]):
        """把pop的数据放回(实际只是指针移动)"""
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

    @abstractmethod
    def analyse(self, action: ArgAction):
        pass

    @abstractmethod
    def create_arpamar(self, fail: bool = False):
        pass

    @abstractmethod
    def add_param(self, opt):
        pass


def analyse_args(
        analyser: CommandAnalyser,
        opt_args: Args,
        sep: str,
        action: Optional[ArgAction] = None
) -> Dict[str, Any]:
    """分析 Args 部分"""
    option_dict: Dict[str, Any] = {}
    for key in opt_args.argument:
        value = opt_args.argument[key]['value']
        default = opt_args.argument[key]['default']
        may_arg = analyser.next_data(sep)
        if value.__class__ is ArgPattern:
            arg_find = value.find(may_arg)
            if not arg_find:
                analyser.reduce_data(may_arg)
                if default is None:
                    raise ParamsUnmatched(f"param {may_arg} is incorrect")
                arg_find = default
            if may_arg == value.pattern:
                arg_find = Ellipsis
            if value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
                arg_find = value.transform_action(arg_find)
            option_dict[key] = arg_find
        elif value is AnyParam:
            option_dict[key] = may_arg
        elif value is AllParam:
            rest_data = analyser.recover_raw_data()
            if not rest_data:
                rest_data = [may_arg]
            elif isinstance(rest_data[0], str):
                rest_data[0] = may_arg + sep + rest_data[0]
            else:
                rest_data.insert(0, may_arg)
            option_dict[key] = rest_data
            return option_dict
        else:
            if may_arg.__class__ is value:
                option_dict[key] = may_arg
            elif default is not None:
                option_dict[key] = default
                analyser.reduce_data(may_arg)
            else:
                analyser.reduce_data(may_arg)
                raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
    if action:
        option_dict = action(option_dict, analyser.is_raise_exception)
    return option_dict


def analyse_option(
        analyser: CommandAnalyser,
        param: Option,
) -> List[Any]:
    """分析 Option 部分"""

    name = analyser.next_data(param.separator)
    if name not in (param.name, param.alias):  # 先匹配选项名称
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.name.lstrip("-")
    if param.nargs == 0:
        return [name, param.action({}, analyser.is_raise_exception)] if param.action else [name, Ellipsis]
    return [name, analyse_args(analyser, param.args, param.separator, param.action)]


def analyse_subcommand(
        analyser: CommandAnalyser,
        param: Subcommand
) -> List[Union[str, Any]]:
    """分析 Subcommand 部分"""
    name = analyser.next_data(param.separator)
    if param.name != name:
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = name.lstrip("-")
    if param.sub_part_len.stop == 0:
        return [name, param.action({}, analyser.is_raise_exception)] if param.action else [name, Ellipsis]

    subcommand = {}
    args = None
    for _ in param.sub_part_len:
        text = analyser.next_data(param.separator, pop=False)
        if not (sub_param := param.sub_params.get(text)) and isinstance(text, str):
            for sp in param.sub_params:
                if text.startswith(getattr(param.sub_params[sp], 'alias', sp)):
                    sub_param = param.sub_params[sp]
                    break
        try:
            if isinstance(sub_param, Option):
                opt_n, opt_v = analyse_option(analyser, sub_param)
                if not subcommand.get(opt_n):
                    subcommand[opt_n] = opt_v
                elif isinstance(subcommand[opt_n], Dict):
                    subcommand[opt_n] = [subcommand[opt_n], opt_v]
                else:
                    subcommand[opt_n].append(opt_v)
            elif not args and (args := analyse_args(analyser, param.args, param.separator, param.action)):
                subcommand.update(args)
        except ParamsUnmatched:
            if analyser.is_raise_exception:
                raise
            break
    return [name, subcommand]


def analyse_header(
        analyser: CommandAnalyser,
        commands: List[Union[ArgPattern, List[Union[NonTextElement, ArgPattern]]]],
        separator: str
) -> str:
    """分析命令头部"""
    head_text = analyser.next_data(separator)
    if isinstance(head_text, str):
        for ch in commands:
            if isinstance(ch, ArgPattern):
                if not (_head_find := ch.find(head_text)):
                    continue
                analyser.head_matched = True
                return _head_find if _head_find != ch.pattern else None
    else:
        may_command = analyser.next_data(separator)
        for ch in commands:
            if isinstance(ch, List):
                if not (_head_find := ch[1].find(may_command)):
                    continue
                if head_text == ch[0]:
                    analyser.head_matched = True
                    return _head_find if _head_find != ch[1].pattern else None
    if not analyser.head_matched:
        raise ParamsUnmatched(f"{head_text} does not matched")


class DisorderCommandAnalyser(CommandAnalyser):
    """无序的分析器"""
    options: Dict[str, Any]
    main_args: Dict[str, Any]
    header: Optional[str]
    need_main_args: bool
    head_matched: bool
    part_len: range

    def __init__(
            self,
            alconna: "Alconna"
    ):
        """初始化命令解析需要使用的参数"""
        self.reset()
        self.need_main_args = False
        self.default_main_only = False
        if alconna.nargs > 0:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = 0
        for k, a in alconna.args.argument.items():
            if a['default'] is not None:
                _de_count += 1
        if _de_count and _de_count == alconna.nargs:
            self.default_main_only = True
        self.is_raise_exception = alconna.exception_in_time
        self.separator = alconna.separator

        # params是除开命令头的剩下部分
        self.params = {"main_args": alconna.args}
        for opts in alconna.options:
            if isinstance(opts, Subcommand):
                opts.sub_params.setdefault('sub_args', opts.args)
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
                opts.sub_part_len = range(len(opts.options) + opts.nargs)
            self.params[opts.name] = opts
        self.part_len = range(len(self.params))
        # 依据headers与command生成一个列表，其中含有所有的命令头
        self.command_headers = []
        if alconna.headers != [""]:
            for i in alconna.headers:
                if isinstance(i, str):
                    self.command_headers.append(ArgPattern(i + alconna.command))
                else:
                    self.command_headers.append([i, ArgPattern(alconna.command)])
        elif alconna.command:
            self.command_headers.append(ArgPattern(alconna.command))

    def reset(self):
        """重置分析器"""
        self.current_index = 0
        self.content_index = 0
        self.is_str = False
        self.options = {}
        self.main_args = {}
        self.header = None
        self.raw_data = {}
        self.head_matched = False

    def add_param(self, tc: Union[Option, Subcommand]):
        """临时增加解析用参数"""
        if isinstance(tc, Subcommand):
            for sub_opts in tc.options:
                tc.sub_params.setdefault(sub_opts.name, sub_opts)
        self.params[tc.name] = tc

    def analyse(self, action: ArgAction):
        """分析整个命令"""
        try:
            self.header = analyse_header(self, self.command_headers, self.separator)
        except ParamsUnmatched:
            return self.create_arpamar(fail=True)

        for _ in self.part_len:
            _text = self.next_data(self.separator, pop=False)
            try:
                _param = self.params.get(_text)
            except TypeError:
                _param = None
            if not _param and _text != "" and isinstance(_text, str):
                for p in self.params:
                    if _text.startswith(getattr(self.params[p], 'alias', p)):
                        _param = self.params[p]
                        break
            try:
                if isinstance(_param, Option):
                    if _param.name == "--help":
                        analyse_option(self, _param)
                        return self.create_arpamar(fail=True)
                    opt_n, opt_v = analyse_option(self, _param)
                    if not self.options.get(opt_n):
                        self.options[opt_n] = opt_v
                    elif isinstance(self.options[opt_n], Dict):
                        self.options[opt_n] = [self.options[opt_n], opt_v]
                    else:
                        self.options[opt_n].append(opt_v)

                elif isinstance(_param, Subcommand):
                    sub_n, sub_v = analyse_subcommand(self, _param)
                    self.options[sub_n] = sub_v
                elif not self.main_args:
                    self.main_args = analyse_args(self, self.params['main_args'], self.separator, action)
            except ParamsUnmatched:
                if self.is_raise_exception:
                    raise
                break
            if self.current_index == self.ndata:
                break

        # 防止主参数的默认值被忽略
        if self.default_main_only:
            self.main_args = analyse_args(self, self.params['main_args'], self.separator, action)

        if self.current_index == self.ndata and (not self.need_main_args or (self.need_main_args and self.main_args)):
            return self.create_arpamar()
        if self.is_raise_exception:
            raise ParamsUnmatched(", ".join([f"{v}" for v in self.recover_raw_data()]))
        return self.create_arpamar(fail=True)

    def create_arpamar(self, fail: bool = False):
        """生成 Arpamar 结果"""
        result = Arpamar()
        result.head_matched = self.head_matched
        if fail:
            result.error_data = self.recover_raw_data()
            result.matched = False
        else:
            result.matched = True
            result.encapsulate_result(self.header, self.main_args, self.options)
        self.reset()
        return result


class DataNode:
    name: str
    index: int
    content_index: int

    def __init__(self, name, index, content_index=0):
        self.name = name
        self.index = index
        self.content_index = content_index

    def catch(self, data: Dict[int, Union[List[str], NonTextElement]]):
        try:
            result = data[self.index]
            if isinstance(result, list):
                result = result[self.content_index]
            return {self.name: result}
        except (KeyError, IndexError):
            return

    def __repr__(self):
        return f"Node<{self.name}> in {self.index}/{self.content_index}"


class AlconnaCache:
    prime_data: Dict[int, Union[List[str], NonTextElement]]
    nodes: List[DataNode]

    def __init__(self):
        self.nodes = []

    def record(self, result: Dict[str, Any]):
        for name in result:
            for i in self.prime_data:
                value = result[name]
                data = self.prime_data[i]
                if isinstance(data, list):
                    for ci, d in enumerate(data):
                        if isinstance(value, (int, bool, float, str)) and str(value) in d:
                            self.nodes.append(DataNode(name, i, ci))
                        elif value == d:
                            self.nodes.append(DataNode(name, i, ci))

                elif not isinstance(value, (int, bool, float, str)) and data == value:
                    self.nodes.append(DataNode(name, i))
                    # break


cache_list: Dict[str, AlconnaCache] = {}


class OrderCommandAnalyser(CommandAnalyser):
    """有序的分析器"""
    options: Dict[str, Any]
    main_args: Dict[str, Any]
    header: Optional[str]
    need_main_args: bool
    head_matched: bool

    def __init__(
            self,
            alconna: "Alconna"
    ):
        """初始化命令解析需要使用的参数"""
        self.alconna = alconna
        self.reset()
        self.need_main_args = False

        if not cache_list.get(alconna.name):
            self.cache = AlconnaCache()
        else:
            self.cache = cache_list[alconna.name]
        if alconna.args.argument:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        self.is_raise_exception = alconna.exception_in_time
        self.separator = alconna.separator

        # params是除开命令头的剩下部分
        self.params = {"main_args": alconna.args}
        for opts in alconna.options:
            if isinstance(opts, Subcommand):
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
            self.params[opts.name] = opts

        # 依据headers与command生成一个列表，其中含有所有的命令头
        self.command_headers = []
        if alconna.headers != [""]:
            for i in alconna.headers:
                if isinstance(i, str):
                    self.command_headers.append(ArgPattern(i + alconna.command))
                else:
                    self.command_headers.append([i, ArgPattern(alconna.command)])
        elif alconna.command:
            self.command_headers.append(ArgPattern(alconna.command))

    def reset(self):
        """重置分析器"""
        self.current_index = 0
        self.is_str = False
        self.options = {}
        self.main_args = {}
        self.header = None
        self.raw_data = {}
        self.head_matched = False

    def add_param(self, tc: Union[Option, Subcommand]):
        """临时增加解析用参数"""
        if isinstance(tc, Subcommand):
            for sub_opts in tc.options:
                tc.sub_params.setdefault(sub_opts.name, sub_opts)
        self.params[tc.name] = tc

    def analyse(self, action: ArgAction):
        if not self.cache.nodes:
            self.cache.prime_data = deepcopy(self.raw_data)
        else:
            _result = {}
            for n in self.cache.nodes:
                if r := n.catch(self.raw_data):
                    _result = {**_result, **r}
            result = Arpamar()
            result.matched = True
            result._other_args = _result
            return result
        try:
            self.header = analyse_header(self, self.command_headers, self.separator)
        except ParamsUnmatched:
            return self.create_arpamar(fail=True)

        for param in self.params.values():
            if self.ndata == self.current_index:
                break
            try:
                if isinstance(param, Option):
                    if param.name == "--help":
                        analyse_option(self, param)
                        return self.create_arpamar(fail=True)
                    opt = analyse_option(self, param)
                    if not self.options.get(opt[0]):
                        self.options[opt[0]] = opt[1]
                    elif isinstance(self.options[opt[0]], Dict):
                        self.options[opt[0]] = [self.options[opt[0]], opt[1]]
                    else:
                        self.options[opt[0]].append(opt[1])
                elif isinstance(param, Subcommand):
                    self.options.update(analyse_subcommand(self, param))
                elif not self.main_args.get:
                    self.main_args = analyse_args(self, self.params['main_args'], self.separator, action)
            except ParamsUnmatched:
                if self.is_raise_exception:
                    raise
                break

        if self.ndata == self.current_index and (not self.need_main_args or (self.need_main_args and self.main_args)):
            return self.create_arpamar()
        if self.is_raise_exception:
            raise ParamsUnmatched(", ".join([f"{v}" for v in self.raw_data.values()]))
        return self.create_arpamar(fail=True)

    def create_arpamar(self, fail: bool = False):
        """生成 Arpamar 结果"""
        result = Arpamar()
        result.head_matched = self.head_matched
        if fail:
            if self.raw_data:
                result.error_data = self.recover_raw_data()
            result.matched = False
            self.reset()
            return result
        result.matched = True
        result.encapsulate_result(self.header, self.main_args, self.options)
        if not self.cache.nodes:
            self.cache.record(result.all_matched_args)
        if not cache_list.get(self.alconna.name):
            cache_list[self.alconna.name] = self.cache
        self.reset()
        return result
