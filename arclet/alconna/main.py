"""Alconna 主体"""
from typing import Dict, List, Optional, Union, Type, Callable
import re
from .analyser import CommandAnalyser, DisorderCommandAnalyser, OrderCommandAnalyser
from .actions import ArgAction
from .util import split_once, split, chain_filter
from .base import TemplateCommand, TAValue, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain
from .exceptions import NullTextMessage, InvalidParam
from .actions import store_bool, store_const, help_send
from .manager import command_manager


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
        exception_in_time: 当解析失败时是否抛出异常，默认为 False
        actions: 命令解析后针对主参数的回调函数
        order_parse: 是否按照命令顺序解析，默认为 False
        namespace: 命令命名空间，默认为 'Alconna'
    """

    headers: List[Union[str, NonTextElement]]
    command: str
    options: List[Union[Option, Subcommand]]
    analyser: CommandAnalyser
    custom_types: Dict[str, Type] = {}
    namespace: str
    __cls_name__: str = "Alconna"

    def __init__(
            self,
            headers: List[Union[str, NonTextElement]] = None,
            command: Optional[str] = None,
            options: List[Union[Option, Subcommand]] = None,
            main_args: Optional[Args] = None,
            exception_in_time: bool = False,
            actions: Optional[Callable] = None,
            order_parse: bool = False,
            namespace: Optional[str] = None,
            **kwargs
    ):
        # headers与command二者必须有其一
        if all((not headers, not command)):
            raise InvalidParam("headers与command二者必须有其一")
        super().__init__(f"ALCONNA::{command or headers[0]}", main_args, actions, **kwargs)
        self.headers = headers or [""]
        self.command = command or ""
        self.options = options or []
        self.exception_in_time = exception_in_time
        self.namespace = namespace or self.__cls_name__
        self.options.append(Option("--help", alias="-h", actions=help_send(self.get_help)))
        self.analyser = OrderCommandAnalyser(self) if order_parse else DisorderCommandAnalyser(self)
        command_manager.register(self)
        self.__class__.__cls_name__ = "Alconna"

    def __class_getitem__(cls, item):
        if isinstance(item, str):
            cls.__cls_name__ = item
        return cls

    def set_namespace(self, namespace: str):
        """重新设置命名空间"""
        command_manager.delete(self)
        self.namespace = namespace
        command_manager.register(self)
        return self

    def help(self, help_string: str) -> "Alconna":
        """预处理 help 文档"""
        self.help_text = help_string
        help_string = ("\n" + help_string) if help_string else ""
        headers = [f"{ch}" for ch in self.analyser.command_headers]
        command_string = f"{'|'.join(headers)}{self.separator}"
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
        try:
            return getattr(self, "help_doc")
        except AttributeError:
            return getattr(self.help(""), "help_doc")

    @classmethod
    def simple(cls, *item: Union[str, tuple]):
        """构造Alconna的简易方式"""
        if isinstance(item[0], str):

            return cls(command=item[0], main_args=Args.__class_getitem__(item[1:])) if len(item) > 1 else cls(
                command=item[0]
            )
        return cls

    @classmethod
    def set_custom_types(cls, **types: Type):
        """设置自定义类型"""
        cls.custom_types = types

    @classmethod
    def from_string(
            cls,
            command: str,
            *option: str,
            custom_types: Dict[str, Type] = None,
            sep: str = " "
    ):
        """
        以纯字符串的形式构造Alconna的简易方式
        from_string("test <message:str> #HELP_STRING", ["--foo|-f <val:bool:True>", "--bar [134]"])
        """
        _options = []
        head, others = split_once(command, sep)
        headers = [head]
        if re.match(r"^\[(.+?)]$", head):
            headers = head.strip("[]").split("|")
        args = [re.split("[:|=]", p) for p in re.findall(r"<(.+?)>", others)]
        if not (help_string := re.findall(r"#(.+)", others)):
            help_string = headers
        if not custom_types:
            custom_types = cls.custom_types
        _args = Args.from_string_list(args, custom_types)
        for opt in option:
            if opt.startswith("--"):
                opt_head, opt_others = split_once(opt, sep)
                try:
                    opt_head, opt_alias = opt_head.split("|")
                except ValueError:
                    opt_alias = opt_head
                opt_args = [re.split("[:|=]", p) for p in re.findall(r"<(.+?)>", opt_others)]
                _opt_args = Args.from_string_list(opt_args, custom_types)
                opt_action_value = re.findall(r"\[(.+?)]$", opt_others)
                if not (opt_help_string := re.findall(r"#(.+)", opt_others)):
                    opt_help_string = [opt_head]
                if opt_action_value:
                    val = eval(opt_action_value[0], {"true": True, "false": False})
                    if isinstance(val, bool):
                        _options.append(Option(opt_head, alias=opt_alias, args=_opt_args, actions=store_bool(val)))
                    else:
                        _options.append(Option(opt_head, alias=opt_alias, args=_opt_args, actions=store_const(val)))
                else:
                    _options.append(Option(opt_head, alias=opt_alias, args=_opt_args))
                _options[-1].help(opt_help_string[0])
        return cls(headers=headers, main_args=_args, options=_options).help(help_string[0])

    @classmethod
    def format(
            cls,
            format_string: str,
            format_args: Dict[str, Union[TAValue, Args, Option, List[Option]]]
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
            key = arg[0]
            value = format_args[key]
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

    def analyse_message(self, message: Union[str, MessageChain]) -> Arpamar:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        if command_manager.is_disable(self):
            return self.analyser.create_arpamar(fail=True)
        if isinstance(message, str):
            self.analyser.is_str = True
            if not message.lstrip():
                if self.exception_in_time:
                    raise NullTextMessage
                return self.analyser.create_arpamar(fail=True)
            self.analyser.raw_data[0] = split(message, self.separator)
            self.analyser.ndata = 1
        else:
            result = chain_filter(message, self.separator, self.exception_in_time)
            if not result:
                return self.analyser.create_arpamar(fail=True)
            self.analyser.raw_data = result
            self.analyser.ndata = len(result)

        return self.analyser.analyse(self.action)
