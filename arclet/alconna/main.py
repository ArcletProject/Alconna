"""Alconna 主体"""


from typing import Dict, List, Optional, Union, overload, Type, Callable
import re
from .analyser import CommandAnalyser
from .actions import ArgAction
from .util import split_once, split
from .base import TemplateCommand, TAValue, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, AnyParam
from .exceptions import NullTextMessage, InvalidParam, UnexpectedElement

_builtin_option = Option("-help")
default_chain_texts = ["Plain", "Text"]
default_black_elements = ["Source", "File", "Quote"]
default_white_elements = []


def set_chain_texts(*text: Union[str, Type[NonTextElement]]):
    """设置文本类元素的集合"""
    global default_chain_texts
    default_chain_texts = [t if isinstance(t, str) else t.__name__ for t in text]


def set_black_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的黑名单"""
    global default_black_elements
    default_black_elements = [ele if isinstance(ele, str) else ele.__name__ for ele in element]


def set_white_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的白名单"""
    global default_white_elements
    default_white_elements = [ele if isinstance(ele, str) else ele.__name__ for ele in element]


class Alconna(TemplateCommand):
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

    headers: List[Union[str, NonTextElement]]
    command: str
    options: List[Union[Option, Subcommand]]
    analyser: CommandAnalyser

    def __init__(
            self,
            headers: List[Union[str, NonTextElement]] = None,
            command: Optional[str] = None,
            options: List[Union[Option, Subcommand]] = None,
            main_args: Optional[Args] = None,
            exception_in_time: bool = False,
            actions: Optional[Callable] = None,
            **kwargs
    ):
        # headers与command二者必须有其一
        if all((not headers, not command)):
            raise InvalidParam("headers与command二者必须有其一")
        super().__init__("Alconna", main_args, actions, **kwargs)
        self.headers = headers or [""]
        self.command = command or ""
        self.options = options or []
        self.exception_in_time = exception_in_time
        self.options.append(_builtin_option)
        self.analyser = CommandAnalyser(self)

    def help(self, help_string: str) -> "Alconna":
        """预处理 help 文档"""
        help_string += "\n" if help_string else ""
        command_string = f"{'|'.join(self.analyser.command_headers)}{self.separator}"
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
            value = arg[1].strip(" ()") if _le > 1 else AnyParam
            default = arg[2].strip(" ") if _le > 2 else None

            if not isinstance(value, AnyParam.__class__):
                if custom_types and custom_types.get(value) and not isinstance(custom_types[value], type):
                    raise InvalidParam(f"自定义参数类型传入的不是类型而是 {custom_types[value]}, 这是有意而为之的吗?")
                try:
                    setattr(cls, "custom_types", custom_types)
                    value = eval(value, custom_types)
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
        opt = Option(name, args=args, alias=alias, **kwargs).separate(sep)
        self.options.append(opt)
        self.analyser.add_param(opt)
        return self

    def set_action(self, action: Union[Callable, str, ArgAction], custom_types: Dict[str, Type] = None):
        """设置针对main_args的action"""
        if isinstance(action, str):
            ns = {}
            exec(action, getattr(self, "custom_types", custom_types), ns)
            action = ns.popitem()[1]
        self.__check_action__(action)
        return self

    def chain_filter(
            self,
            message: MessageChain,
            texts: List[str],
            black_elements: List[str],
            white_elements: Optional[List[str]] = None
    ):
        """消息链过滤方法, 优先度 texts > white_elements > black_elements"""
        i, _tc = 0, 0
        for ele in message:
            if ele.__class__.__name__ in texts:
                self.analyser.raw_data[i] = split(ele.text.lstrip(' '), self.separator)
                _tc += 1
            elif white_elements:
                if ele.__class__.__name__ not in white_elements:
                    if self.exception_in_time:
                        raise UnexpectedElement(f"{ele.__class__.__name__}({ele})")
                    continue
                self.analyser.raw_data[i] = ele
            else:
                if ele.__class__.__name__ in black_elements:
                    if self.exception_in_time:
                        raise UnexpectedElement(f"{ele.__class__.__name__}({ele})")
                    continue
                self.analyser.raw_data[i] = ele
            i += 1
        if _tc == 0:
            if self.exception_in_time:
                raise NullTextMessage
            return self.analyser.create_arpamar(fail=True)

    def analyse_message(self, message: Union[str, MessageChain]) -> Arpamar:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        if isinstance(message, str):
            self.analyser.is_str = True
            if not message.lstrip():
                if self.exception_in_time:
                    raise NullTextMessage
                return self.analyser.create_arpamar(fail=True)
            self.analyser.raw_data.setdefault(0, split(message, self.separator))
        else:
            self.chain_filter(message, default_chain_texts, default_black_elements, default_white_elements)

        return self.analyser.analyse(self.action)
