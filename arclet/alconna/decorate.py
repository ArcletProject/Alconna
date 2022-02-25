import asyncio
from asyncio import AbstractEventLoop
import sys
from typing import Dict, Any, Optional, Callable, Union, TypeVar
from .main import Alconna
from .base import Args
from .component import Option
from .types import MessageChain


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
        result = self.command.analyse_message(message)
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
            ).help(help_string or command_name)
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
            sep: str = " ",
            **kwargs
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
                Option(name, args=args, alias=alias, actions=action, **kwargs).separate(sep).help(help or name)
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
