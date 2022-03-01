import asyncio
from asyncio import AbstractEventLoop
import sys
import re
from typing import Dict, Any, Optional, Callable, Union, TypeVar, List, Type

from arclet.alconna.types import MessageChain
from arclet.alconna.builtin.actions import store_bool, store_const
from arclet.alconna.main import Alconna
from arclet.alconna.component import Option, Subcommand
from arclet.alconna.base import Args, TAValue
from arclet.alconna.util import split, split_once

PARSER_TYPE = Callable[[Callable, Dict[str, Any], Optional[Dict[str, Any]], Optional[AbstractEventLoop]], Any]


def default_parser(
        func: Callable,
        args: Dict[str, Any],
        local_arg: Optional[Dict[str, Any]],
        loop: Optional[AbstractEventLoop]
) -> Any:
    return func(**args, **local_arg)


class ALCCommand:
    """
    以 click-like 方法创建的 Alconna 结构体, 可以被视为一类 CommanderHandler
    """
    command: Alconna
    parser_func: PARSER_TYPE
    local_args: Dict[str, Any]
    exec_target: Callable = None
    loop: AbstractEventLoop

    def __init__(
            self,
            command: Alconna,
            target: Callable,
            loop: AbstractEventLoop,
    ):
        self.command = command
        self.exec_target = target
        self.loop = loop
        self.parser_func = default_parser
        self.local_args = {}

    def set_local_args(self, local_args: Optional[Dict[str, Any]] = None):
        """
        设置本地参数

        Args:
            local_args (Optional[Dict[str, Any]]): 本地参数
        """
        self.local_args = local_args

    def set_parser(self, parser_func: PARSER_TYPE):
        """
        设置解析器

        Args:
            parser_func (PARSER_TYPE): 解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.parser_func = parser_func
        return self

    def __call__(self, message: Union[str, MessageChain]) -> Any:
        if not self.exec_target:
            raise Exception("This must behind a @xxx.command()")
        result = self.command.parse(message)
        if result.matched:
            self.parser_func(self.exec_target, result.all_matched_args, self.local_args, self.loop)

    def from_commandline(self):
        """从命令行解析参数"""
        if not self.command:
            raise Exception("You must call @xxx.command() before @xxx.from_commandline()")
        args = sys.argv[1:]
        args.insert(0, self.command.command)
        self.__call__(" ".join(args))


F = TypeVar("F", bound=Callable[..., Any])
FC = TypeVar("FC", bound=Union[Callable[..., Any], ALCCommand])


# ----------------------------------------
# click-like
# ----------------------------------------


class AlconnaDecorate:
    """
    Alconna Click-like 构造方法的生成器

    Examples:
        >>> cli = AlconnaDecorate()
        >>> @cli.build_command()
        ... @cli.option("--name|-n", Args["name":str:"your name"])
        ... @cli.option("--age|-a", Args["age":int:"your age"])
        ... def hello(name: str, age: int):
        ...     print(f"Hello {name}, you are {age} years old.")
        ...
        >>> hello("hello --name Alice --age 18")

    Attributes:
        namespace (str): 命令的命名空间
        loop (AbstractEventLoop): 事件循环
    """
    namespace: str
    loop: AbstractEventLoop
    building: bool
    __storage: Dict[str, Any]
    default_parser: PARSER_TYPE

    def __init__(
            self,
            namespace: str = "Alconna",
            loop: Optional[AbstractEventLoop] = None,
    ):
        """
        初始化构造器

        Args:
            namespace (str): 命令的命名空间
            loop (AbstractEventLoop): 事件循环
        """
        self.namespace = namespace
        self.building = False
        self.__storage = {"options": []}
        self.loop = loop or asyncio.new_event_loop()
        self.default_parser = default_parser

    def build_command(self, name: Optional[str] = None) -> Callable[[F], ALCCommand]:
        """
        开始构建命令

        Args:
            name (Optional[str]): 命令名称
        """
        self.building = True

        def wrapper(func: Callable[..., Any]) -> ALCCommand:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            command_name = name or self.__storage.get('func').__name__
            help_string = self.__storage.get('func').__doc__
            command = Alconna(
                command=command_name,
                options=self.__storage.get("options"),
                namespace=self.namespace,
                main_args=self.__storage.get("main_args"),
                help_text=help_string or command_name
            )
            self.building = False
            return ALCCommand(command, self.__storage.get('func'), self.loop).set_parser(self.default_parser)

        return wrapper

    def option(
            self,
            name: str,
            args: Optional[Args] = None,
            alias: Optional[str] = None,
            help: Optional[str] = None,
            action: Optional[Callable] = None,
            sep: str = " "
    ) -> Callable[[FC], FC]:
        """
        添加命令选项

        Args:
            name (str): 选项名称
            args (Optional[Args]): 选项参数
            alias (Optional[str]): 选项别名
            help (Optional[str]): 选项帮助信息
            action (Optional[Callable]): 选项动作
            sep (str): 参数分隔符
        """
        if not self.building:
            raise Exception("This must behind a @xxx.command()")

        def wrapper(func: FC) -> FC:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            self.__storage['options'].append(
                Option(name, args=args, alias=alias, actions=action, separator=sep, help_text=help or name)
            )
            return func

        return wrapper

    def arguments(self, args: Args) -> Callable[[FC], FC]:
        """
        添加命令参数

        Args:
            args (Args): 参数
        """
        if not self.building:
            raise Exception("This must behind a @xxx.command()")

        def wrapper(func: FC) -> FC:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            self.__storage['main_args'] = args
            return func

        return wrapper

    def set_default_parser(self, parser_func: PARSER_TYPE):
        """
        设置默认的参数解析器

        Args:
            parser_func (PARSER_TYPE): 参数解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.default_parser = parser_func
        return self


# ----------------------------------------
# format
# ----------------------------------------


def _from_format(
        format_string: str,
        format_args: Dict[str, Union[TAValue, Args, Option, List[Option]]]
) -> "Alconna":
    """
    以格式化字符串的方式构造 Alconna

    Examples:

    >>> from arclet.alconna import Alconna
    >>> alc1 = AlconnaFormat(
    ...     "lp user {target} perm set {perm} {default}",
    ...     {"target": str, "perm": str, "default": Args["de":bool:True]},
    ... )
    >>> alc1.parse("lp user AAA perm set admin.all False")
    """
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
                options.append(Subcommand(_param, [value]))
            elif isinstance(value, List):
                options.append(Subcommand(_param, value))
            elif _key_ref > 1 and isinstance(options[-1], Option):
                if isinstance(value, Args):
                    options.append(Subcommand(_param, [options.pop(-1)], args=value))
                else:
                    options.append(Subcommand(_param, [options.pop(-1)], args=Args(**{key: value})))
            elif isinstance(value, Args):
                options.append(Option(_param, args=value))
            else:
                options.append(Option(_param, Args(**{key: value})))
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

    alc = Alconna(command=command, options=options, main_args=main_args)
    return alc


# ----------------------------------------
# koishi-like
# ----------------------------------------


def _from_string(
        command: str,
        *option: str,
        custom_types: Dict[str, Type] = None,
        sep: str = " "
) -> "Alconna":
    """
    以纯字符串的形式构造Alconna的简易方式

    Examples:

    >>> from arclet.alconna import Alconna
    >>> alc = AlconnaString(
    ... "test <message:str> #HELP_STRING",
    ... "--foo|-f <val:bool:True>", "--bar [134]"
    ... )
    >>> alc.parse("test abcd --foo True")
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
        custom_types = Alconna.custom_types
    else:
        custom_types.update(Alconna.custom_types)
    _args = Args.from_string_list(args, custom_types.copy())
    for opt in option:
        if opt.startswith("--"):
            opt_head, opt_others = split_once(opt, sep)
            try:
                opt_head, opt_alias = opt_head.split("|")
            except ValueError:
                opt_alias = opt_head
            opt_args = [re.split("[:|=]", p) for p in re.findall(r"<(.+?)>", opt_others)]
            _opt_args = Args.from_string_list(opt_args, custom_types.copy())
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
            _options[-1].help_text = opt_help_string[0]
            _options[-1].__generate_help__()
    return Alconna(headers=headers, main_args=_args, options=_options, help_text=help_string[0])


AlconnaFormat = _from_format
AlconnaString = _from_string
