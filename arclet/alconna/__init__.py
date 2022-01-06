"""Alconna 主体"""

from typing import Dict, List, Optional, Union, Any, overload, Type
import re
from .util import split_once, split
from .component import Option, CommandInterface, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, TAValue, Args, AnyParam, AllParam
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam

_builtin_option = Option("-help")


class Alconna(CommandInterface):
    """
    亚尔康娜（Alconna），Cesloi的妹妹

    用于更加奇怪(大雾)精确的命令解析，支持String与MessageChain

    样例：Alconna(
        headers=[""],
        command="name",
        options=[
            Subcommand("sub_name",Option("sub_opt", args=sub_arg), args=sub_main_args),
            Option("opt", args=arg)
            ]
        main_args=main_args
        )

    其中
        - name: 命令名称
        - sub_name: 子命令名称
        - sub_opt: 子命令选项名称
        - sub_arg: 子命令选项参数
        - sub_main_args: 子命令主参数
        - opt: 命令选项名称
        - arg: 命令选项参数

    Args:
        headers: 呼叫该命令的命令头，一般是你的机器人的名字或者符号，与 command 至少有一个填写
        command: 命令名称，你的命令的名字，与 headers 至少有一个填写
        options: 命令选项，你的命令可选择的所有 option ，包括子命令与单独的选项
        main_args: 主参数，填入后当且仅当命令中含有该参数时才会成功解析
    """

    name = "Alconna"
    headers: List[str]
    command: str
    options: List[Union[Option, Subcommand]]
    result: Arpamar

    def __init__(
            self,
            headers: List[str] = None,
            command: Optional[str] = None,
            options: List[Union[Option, Subcommand]] = None,
            main_args: Optional[Args] = None,
            exception_in_time: bool = False,
            **kwargs
    ):
        # headers与command二者必须有其一
        if all((not headers, not command)):
            raise InvalidParam("headers与command二者必须有其一")
        self.headers = headers or [""]
        self.command = command or ""
        self.options = options or []
        self.args = main_args or Args(**kwargs)
        self.exception_in_time = exception_in_time
        self.options.append(_builtin_option)
        self._initialise_arguments()

    def help(self, help_string: str) -> "Alconna":
        """预处理 help 文档"""
        help_string += "\n" if help_string else ""
        command_string = f"{'|'.join(self._command_headers)}{self.separator}"
        option_string = "".join(list(map(lambda x: getattr(x, "help_doc", ""),
                                         filter(lambda x: isinstance(x, Option), self.options))))
        subcommand_string = "".join(list(map(lambda x: getattr(x, "help_doc", ""),
                                             filter(lambda x: isinstance(x, Subcommand), self.options))))
        option_help = "可用的选项有:\n" if option_string else ""
        subcommand_help = "可用的子命令有:\n" if subcommand_string else ""
        setattr(self, "help_doc", f"{command_string}{self.args.params(self.separator)}{help_string}\n"
                                  f"{subcommand_help}{subcommand_string}"
                                  f"{option_help}{option_string}")
        return self

    def get_help(self) -> str:
        """返回 help 文档"""
        return getattr(self, "help_doc", getattr(self.help(""), "help_doc"))

    @classmethod
    def simple(cls, *item: Union[str, tuple]):
        """构造Alconna的简易方式"""
        if isinstance(item[0], str):
            return cls(command=item[0]).__getitem__(item[1:]) if len(item) > 1 else cls(command=item[0])
        return cls

    @classmethod
    def from_string(cls, command: str, custom_types: Dict[str, Type] = None, sep: str = " "):
        """以纯字符串的形式构造Alconna的简易方式"""
        head, params = split_once(command, sep)
        headers = [head]
        if re.match(r"^\[(.+?)]$", head):
            headers = head.strip("[]").split("|")
        _args = Args()
        args = [p.split(":") for p in re.findall(r"<(.+?)>", params)]
        for arg in args:
            _le = len(arg)
            if _le == 0:
                raise NullTextMessage
            name = arg[0]
            value = arg[1].strip(" ") if _le > 1 else AnyParam
            default = arg[2].strip(" ") if _le > 2 else None
            if not isinstance(value, AnyParam.__class__):
                ns = {}
                exec(f"def ty():\n    return {value}", custom_types or {}, ns)
                try:
                    value = ns["ty"]()
                except NameError:
                    raise
            _args.__getitem__([(name, value, default)])
        return cls(headers=headers, main_args=_args)

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: List[Union[TAValue, Args, Option, List[Option]]],
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        ...

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: Dict[str, Union[TAValue, Args, Option, List[Option]]],
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        ...

    @classmethod
    def format(
            cls,
            format_string: str,
            format_args: ...,
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        """以格式化字符串的方式构造 Alconna"""
        _key_ref = 0
        strings = split(format_string)
        command = strings.pop(0)
        options = []
        main_args = None

        _string_stack: List[str] = []
        for i, string in enumerate(strings):
            if not (arg := re.findall(r"{(.+)}", string)):
                _string_stack.append(string)
                _key_ref = 0
                continue
            _key_ref += 1
            key = arg[0] if not reflect_map else (reflect_map[arg[0]] if reflect_map.get(arg[0]) else arg[0])

            if isinstance(format_args, List) and arg[0].isdigit():
                value = format_args[int(arg[0])]
            elif isinstance(format_args, Dict):
                value = format_args[arg[0]]
            else:
                raise InvalidParam("FormatMap 只能是 List 或者 Dict")
            try:
                _param = _string_stack.pop(-1)
                if isinstance(value, Option):
                    options.append(Subcommand(_param, value))
                elif isinstance(value, List):
                    options.append(Subcommand(_param, *value))
                elif _key_ref > 1 and isinstance(options[-1], Option):
                    if isinstance(value, Args):
                        options.append(Subcommand(_param, options.pop(-1), args=value))
                    else:
                        options.append(Subcommand(_param, options.pop(-1), **{key: value}))
                elif isinstance(value, Args):
                    options.append(Option(_param, args=value))
                else:
                    options.append(Option(_param, **{key: value}))
            except IndexError:
                if i == 0:
                    if isinstance(value, Args):
                        main_args = value
                    elif not isinstance(value, Option) and not isinstance(value, List):
                        main_args = Args(**{key: value})
                else:
                    if isinstance(value, Option):
                        options.append(value)
                    elif isinstance(value, List):
                        options[-1].options.extend(value)
                    elif isinstance(value, Args):
                        options[-1].args = value
                    else:
                        options[-1].args.argument.update({key: value})

        alc = cls(command=command, options=options, main_args=main_args)
        return alc

    def option(self, name: str, sep: str = " ", args: Optional[Args] = None, alias: Optional[str] = None, **kwargs):
        """链式注册一个 Option"""
        self.options.append(Option(name, args=args, alias=alias, **kwargs).separate(sep))
        self._initialise_arguments()
        return self

    def add_options(self, options: List[Option]):
        """将若干 Option 加入 Alconna 的解析列表"""
        self.options.extend(options)
        self._initialise_arguments()

    def _initialise_arguments(self):
        """初始化命令解析需要使用的参数"""
        # params是除开命令头的剩下部分
        self._params: Dict[str, Union[Args, Option, Subcommand]] = {"main_args": self.args}
        for opts in self.options:
            if isinstance(opts, Subcommand):
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
            self._params[opts.name] = opts

        self._command_headers: List[str] = []  # 依据headers与command生成一个列表，其中含有所有的命令头
        if self.headers != [""]:
            for i in self.headers:
                self._command_headers.append(i + self.command)
        elif self.command:
            self._command_headers.append(self.command)

    def _analyse_args(
            self,
            opt_args: Args,
            sep: str,
    ) -> Dict[str, Any]:
        """分析 Args 部分"""
        _option_dict: Dict[str, Any] = {}
        for key, value, default in opt_args:
            _may_arg = self.result.next_data(sep)
            if isinstance(value, str):
                if not (_arg_find := re.findall('^' + value + '$', _may_arg)):
                    if default is None:
                        raise ParamsUnmatched(f"param {_may_arg} is incorrect")
                    _arg_find = [default]
                if _may_arg == value:
                    _arg_find[0] = Ellipsis
                _option_dict[key] = _arg_find[0]
            elif value == AnyParam:
                _option_dict[key] = _may_arg
            elif value == AllParam:
                _rest_data = self.recover_raw_data()
                if not _rest_data:
                    _rest_data = [_may_arg]
                elif isinstance(_rest_data[0], str):
                    _rest_data[0] = _may_arg + sep + _rest_data[0]
                else:
                    _rest_data.insert(0, _may_arg)
                _option_dict[key] = _rest_data[0] if self.result.is_str else _rest_data
                return _option_dict
            else:
                if _may_arg.__class__ == value:
                    _option_dict[key] = _may_arg
                elif default is not None:
                    _option_dict[key] = default
                else:
                    raise ParamsUnmatched(f"param type {_may_arg.__class__} is incorrect")
        return _option_dict

    def _analyse_option(
            self,
            param: Option,
    ) -> Dict[str, Any]:
        """分析 Option 部分"""
        opt: str = param.name
        alias: str = param.alias
        args: Args = param.args
        sep: str = param.separator

        name = self.result.next_data(sep)
        if (not re.match('^' + opt + '$', name)) and (not re.match('^' + alias + '$', name)):  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {opt}")
        name = name.lstrip("-")
        if not args.argument:
            return {name: Ellipsis}
        return {name: self._analyse_args(args, sep)}

    def _analyse_subcommand(
            self,
            param: Subcommand
    ) -> Dict[str, Any]:
        """分析 Subcommand 部分"""
        command: str = param.name
        sep: str = param.separator
        sub_params: Dict = param.sub_params
        name = self.result.next_data(sep)
        if not re.match('^' + command + '$', name):
            raise ParamsUnmatched(f"{name} dose not matched with {command}")
        name = name.lstrip("-")
        if not param.args.argument and not param.options:
            return {name: Ellipsis}

        subcommand = {}
        _get_args = False
        for _ in range(len(sub_params)):
            try:
                _text = self.result.next_data(sep, pop=False)
                if not (sub_param := sub_params.get(_text)):
                    sub_param = sub_params['sub_args']
                    if isinstance(_text, str):
                        for sp in sub_params:
                            if _text.startswith(sp):
                                sub_param = sub_params.get(sp)
                                break
                if isinstance(sub_param, Option):
                    subcommand.update(self._analyse_option(sub_param))
                elif not _get_args:
                    if args := self._analyse_args(sub_param, sep):
                        _get_args = True
                        subcommand.update(args)
            except ParamsUnmatched:
                if self.exception_in_time:
                    raise
                break
        return {name: subcommand}

    def _analyse_header(self) -> str:
        """分析命令头部"""
        head_text = self.result.next_data(self.separator)
        if isinstance(head_text, str):
            for ch in self._command_headers:
                if not (_head_find := re.findall('^' + ch + '$', head_text)):
                    continue
                self.result.head_matched = True
                if _head_find[0] != ch:
                    return _head_find[0]
        if not self.result.head_matched:
            raise ParamsUnmatched(f"{head_text} does not matched")

    def recover_raw_data(self) -> List[Union[str, NonTextElement]]:
        """将处理过的命令数据大概还原"""
        _result = []
        for v in self.result.raw_data.values():
            if isinstance(v, list):
                _result.append(f'{self.separator}'.join(v))
            else:
                _result.append(v)
        self.result.raw_data.clear()
        return _result

    def analyse_message(self, message: Union[str, MessageChain]) -> Arpamar:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        if hasattr(self, "result"):
            del self.result
        self.result: Arpamar = Arpamar()

        if self.args.argument:
            self.result.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument

        if isinstance(message, str):
            self.result.is_str = True
            if not message.lstrip():
                if self.exception_in_time:
                    raise NullTextMessage
                return self.result
            self.result.raw_data.setdefault(0, split(message, self.separator))
        else:
            i, _tc = 0, 0
            for ele in message:
                if ele.__class__.__name__ in ("Source", "Quote", "File"):
                    continue
                if ele.__class__.__name__ in ("Plain", "Text"):
                    self.result.raw_data[i] = split(ele.text.lstrip(' '), self.separator)
                    _tc += 1
                else:
                    self.result.raw_data[i] = ele
                i += 1
            if _tc == 0:
                if self.exception_in_time:
                    raise NullTextMessage
                return self.result

        try:
            self.result.results['header'] = self._analyse_header()
        except ParamsUnmatched:
            self.result.results.clear()
            return self.result

        for i in range(len(self._params)):
            if not self.result.raw_data:
                break
            try:
                _text = self.result.next_data(self.separator, pop=False)
                _param = self._params.get(_text)
                if not _param:
                    _param = self._params['main_args']
                    if isinstance(_text, str):
                        for p, value in self._params.items():
                            if _text.startswith(p) or _text.startswith(getattr(value, 'alias', p)):
                                _param = value
                                break
                if isinstance(_param, Option):
                    self.result.results['options'].update(self._analyse_option(_param))
                elif isinstance(_param, Subcommand):
                    self.result.results['options'].update(self._analyse_subcommand(_param))
                elif not self.result.results.get("main_args"):
                    self.result.results['main_args'] = self._analyse_args(_param, self.separator)
            except ParamsUnmatched:
                if self.exception_in_time:
                    raise
                break

        if not self.result.raw_data and (not self.result.need_main_args or (
                self.result.need_main_args and not self.result.has('help') and self.result.results.get('main_args')
        )):
            self.result.matched = True
            self.result.encapsulate_result()
        else:
            if self.exception_in_time:
                raise ParamsUnmatched(", ".join([f"{v}" for v in self.result.raw_data.values()]))
            self.result.results.clear()
        return self.result
