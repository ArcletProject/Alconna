"""Alconna 核心"""
import re
from typing import Dict, Any, Union, List, Optional, TYPE_CHECKING

from .actions import ArgAction
from .base import Args
from .component import Option, Subcommand, Arpamar
from .util import split_once
from .types import NonTextElement, ArgPattern, AllParam, AnyParam
from .exceptions import ParamsUnmatched
if TYPE_CHECKING:
    from .main import Alconna


class CommandAnalyser:
    """Alconna使用的分析器"""
    current_index: int  # 记录解析时当前数据的index
    is_str: bool  # 是否解析的是string
    options: Dict[str, Any]
    main_args: Dict[str, Any]
    header: Optional[str]
    raw_data: Dict[int, Union[List[str], NonTextElement]]
    need_main_args: bool
    head_matched: bool
    separator: str
    is_raise_exception: bool
    params: Dict[str, Union[Args, Option, Subcommand]]
    command_headers: List[Union[str, List[Union[NonTextElement, str]]]]

    def __init__(
            self,
            alconna: "Alconna"
    ):
        """初始化命令解析需要使用的参数"""
        self.current_index = 0
        self.is_str = False
        self.raw_data = {}
        self.options = {}
        self.main_args = {"data": {}}
        self.need_main_args = False
        self.head_matched = False

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
                    self.command_headers.append(i + alconna.command)
                else:
                    self.command_headers.append([i, alconna.command])
        elif alconna.command:
            self.command_headers.append(alconna.command)

    def reset(self):
        """重置分析器"""
        self.current_index = 0
        self.is_str = False
        self.options = {}
        self.main_args = {"data": {}}
        self.header = None
        self.raw_data.clear()
        self.head_matched = False

    def add_param(self, tc: Union[Option, Subcommand]):
        """临时增加解析用参数"""
        if isinstance(tc, Subcommand):
            for sub_opts in tc.options:
                tc.sub_params.setdefault(sub_opts.name, sub_opts)
        self.params[tc.name] = tc

    def recover_raw_data(self) -> List[Union[str, NonTextElement]]:
        """将处理过的命令数据大概还原"""
        _result = []
        for v in self.raw_data.values():
            if isinstance(v, list):
                _result.append(f'{self.separator}'.join(v))
            else:
                _result.append(v)
        self.raw_data.clear()
        return _result

    def analyse_args(
            self,
            opt_args: Args,
            sep: str,
            action: Optional[ArgAction] = None
    ) -> Dict[str, Any]:
        """分析 Args 部分"""
        option_dict: Dict[str, Any] = {}
        for key, value, default in opt_args:
            may_arg = self.next_data(sep)
            if isinstance(value, ArgPattern):
                if not (arg_find := re.findall("^" + value.pattern + "$", may_arg)):
                    if default is None:
                        raise ParamsUnmatched(f"param {may_arg} is incorrect")
                    arg_find = [default]
                    self.reduce_data(may_arg)
                if may_arg == value.pattern:
                    arg_find[0] = Ellipsis
                if value.transform and isinstance(arg_find[0], str):
                    arg_find[0] = eval(arg_find[0], {"true": True, "false": False})
                option_dict[key] = arg_find[0]
            elif value == AnyParam:
                option_dict[key] = may_arg
            elif value == AllParam:
                rest_data = self.recover_raw_data()
                if not rest_data:
                    rest_data = [may_arg]
                elif isinstance(rest_data[0], str):
                    rest_data[0] = may_arg + sep + rest_data[0]
                else:
                    rest_data.insert(0, may_arg)
                option_dict[key] = rest_data[0] if self.is_str else rest_data
                return option_dict
            else:
                if may_arg.__class__ == value:
                    option_dict[key] = may_arg
                elif default is not None:
                    option_dict[key] = default
                    self.reduce_data(may_arg)
                else:
                    raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
        if action:
            option_dict = action(option_dict, self.is_raise_exception)
        return option_dict

    def analyse_option(
            self,
            param: Option,
    ) -> Dict[str, Any]:
        """分析 Option 部分"""
        opt: str = param.name
        alias: str = param.alias
        args: Args = param.args
        sep: str = param.separator

        name = self.next_data(sep)
        if name not in (opt, alias):  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {opt}")
        name = name.lstrip("-")
        if not args.argument:
            if param.action:
                return {name: param.action({}, self.is_raise_exception)}
            return {name: Ellipsis}

        return {name: self.analyse_args(args, sep, param.action)}

    def analyse_subcommand(
            self,
            param: Subcommand
    ) -> Dict[str, Any]:
        """分析 Subcommand 部分"""
        command: str = param.name
        sep: str = param.separator
        sub_params: Dict = param.sub_params
        name = self.next_data(sep)
        if command != name:
            raise ParamsUnmatched(f"{name} dose not matched with {command}")
        name = name.lstrip("-")
        if not param.args.argument and not param.options:
            if param.action:
                return {name: param.action({}, self.is_raise_exception)}
            return {name: Ellipsis}

        subcommand = {}
        get_args = False
        for _ in range(len(sub_params)):
            try:
                text = self.next_data(sep, pop=False)
                if not (sub_param := sub_params.get(text)):
                    sub_param = sub_params['sub_args']
                    if isinstance(text, str):
                        for sp in sub_params:
                            if text.startswith(sp):
                                sub_param = sub_params.get(sp)
                                break
                if isinstance(sub_param, Option):
                    subcommand.update(self.analyse_option(sub_param))
                elif not get_args:
                    if args := self.analyse_args(sub_param, sep, param.action):
                        get_args = True
                        subcommand.update(args)
            except ParamsUnmatched:
                if self.is_raise_exception:
                    raise
                break
        return {name: subcommand}

    def analyse_header(self) -> str:
        """分析命令头部"""
        head_text = self.next_data(self.separator)
        if isinstance(head_text, str):
            for ch in self.command_headers:
                if not (_head_find := re.findall('^' + ch + '$', head_text)):
                    continue
                self.head_matched = True
                if _head_find[0] != ch:
                    return _head_find[0]
        else:
            may_command = self.next_data(self.separator)
            for ch in self.command_headers:
                if isinstance(ch, List):
                    if not (_head_find := re.findall('^' + ch[1] + '$', may_command)):
                        continue
                    if head_text == ch[0]:
                        self.head_matched = True
                        if _head_find[0] != ch[1]:
                            return _head_find[0]
        if not self.head_matched:
            raise ParamsUnmatched(f"{head_text} does not matched")

    def analyse(self, action: ArgAction):
        """分析整个命令"""
        try:
            self.header = self.analyse_header()
        except ParamsUnmatched:
            return self.create_arpamar(fail=True)

        for i in range(len(self.params)):
            if not self.raw_data:
                break
            try:
                _text = self.next_data(self.separator, pop=False)
                _param = self.params.get(_text)
                if not _param:
                    _param = self.params['main_args']
                    if isinstance(_text, str):
                        for p, value in self.params.items():
                            if _text.startswith(p) or _text.startswith(getattr(value, 'alias', p)):
                                _param = value
                                break
                if isinstance(_param, Option):
                    self.options.update(self.analyse_option(_param))
                elif isinstance(_param, Subcommand):
                    self.options.update(self.analyse_subcommand(_param))
                elif not self.main_args.get('data'):
                    self.main_args['data'] = self.analyse_args(_param, self.separator, action)
            except ParamsUnmatched:
                if self.is_raise_exception:
                    raise
                break

        if not self.raw_data and (not self.need_main_args or (
                self.need_main_args and not self.options.get('help') and self.main_args.get('data')
        )):
            return self.create_arpamar()
        if self.is_raise_exception:
            raise ParamsUnmatched(", ".join([f"{v}" for v in self.raw_data.values()]))
        return self.create_arpamar(fail=True)

    def next_data(self, separate: Optional[str] = None, pop: bool = True) -> Union[str, NonTextElement]:
        """获取解析需要的下个数据"""
        _text: str = ""  # 重置
        _rest_text: str = ""

        try:
            if not self.raw_data[self.current_index]:
                self.raw_data.pop(self.current_index)
                self.current_index += 1

            _current_data = self.raw_data[self.current_index]
        except KeyError:
            return ""

        if isinstance(_current_data, list):
            _text, _rest_text = split_once(_current_data[0], separate)
            if not _rest_text and not pop:
                return _current_data[0]
            if not _rest_text and pop:
                return _current_data.pop(0)
            if _rest_text and pop:
                self.raw_data[self.current_index][0] = _rest_text
            return _text

        if pop:
            self.raw_data.pop(self.current_index)
            self.current_index += 1
        return _current_data

    def reduce_data(self, data: Union[str, NonTextElement]):
        """把数据放回"""
        try:
            if isinstance(data, str) and isinstance(self.raw_data[self.current_index], list):
                self.raw_data[self.current_index].insert(0, data)
            else:
                self.current_index -= 1
                self.raw_data[self.current_index] = [data]
        except KeyError:
            pass

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
        self.reset()
        return result
