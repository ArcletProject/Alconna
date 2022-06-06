"""Alconna 主体"""
import sys
from typing import Dict, List, Optional, Union, Type, Callable, Tuple, TypeVar, overload, TYPE_CHECKING, TypedDict, \
    Iterable

from .lang import lang_config
from .analysis.base import compile
from .base import CommandNode, Args, ArgAction, Option, Subcommand, HelpOption, ShortcutOption
from .typing import DataCollection
from .manager import command_manager
from .arpamar import Arpamar
from .components.action import ActionHandler
from .components.output import AbstractTextFormatter
from .components.behavior import ArpamarBehavior, T_ABehavior
from .components.duplication import AlconnaDuplication
from .builtin.formatter import DefaultTextFormatter
from .builtin.analyser import DefaultCommandAnalyser

if TYPE_CHECKING:
    from .analysis.analyser import Analyser

T_Duplication = TypeVar('T_Duplication', bound=AlconnaDuplication)


class _Actions(TypedDict):
    main: Optional[ArgAction]
    options: Dict[str, ArgAction]
    subcommands: Dict[str, ArgAction]


class AlconnaGroup(CommandNode):
    _group = True

    def __init__(
            self,
            name: str,
            *commands: "Alconna",
            namespace: Optional[str] = None,

    ):
        self.commands = list(commands)
        self.namespace = namespace
        name = command_manager.sign + name
        super().__init__(name, )
        self.name.replace(command_manager.sign, '')
        self.__handler_help_text__()

    def __handler_help_text__(self):
        self.help_text = "\n"
        for command in self.commands:
            self.help_text += (
                f" * {command.name} : "
                f"{command.help_text.replace('Usage', ';').replace('Example', ';').split(';')[0]}\n"
            )
        return self

    @property
    def path(self) -> str:
        return f"{self.namespace}.{self.name.replace(command_manager.sign, '')}"

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.commands[0].formatter_type(self).format_node()

    def append(self, *commands: "Alconna"):
        self.commands += list(commands)
        self.__handler_help_text__()
        return self

    def __union__(self, other: Union["AlconnaGroup", "Alconna"]):
        if isinstance(other, AlconnaGroup):
            self.commands += other.commands
            self.__handler_help_text__()
        else:
            self.commands.append(other)
        return self

    def __iter__(self):
        yield from self.commands

    def __getitem__(self, item: str):
        try:
            return next(filter(lambda x: x.name == item, self.commands))
        except StopIteration:
            raise KeyError(item)

    def parse(self, message: Union[str, DataCollection]):
        res = None
        for command in self.commands:
            if (res := command.parse(message)).matched:
                return res
        else:
            return res


class Alconna(CommandNode):
    """
    亚尔康娜 (Alconna), Cesloi 的妹妹

    用于更加精确的命令解析，支持 String 与 MessageChain

    Examples:

        >>> from arclet.alconna import Alconna
        >>> alc = Alconna(
        ...     headers=["h1", "h2"],
        ...     command="name",
        ...     options=[
        ...         Option("opt", Args["opt_arg", "opt_arg"]),
        ...         Subcommand(
        ...             "sub_name",
        ...             [Option("sub_opt", Args["sub_arg", "sub_arg"])],
        ...             args=Args["sub_main_args", "sub_main_args"]
        ...         )
        ...     ],
        ...     main_args=Args["main_args", "main_args"],
        ...  )
        >>> alc.parse("name opt opt_arg")


    其中
        - name: 命令名称
        - sub_name: 子命令名称
        - sub_opt: 子命令选项名称
        - sub_arg: 子命令选项参数
        - sub_main_args: 子命令主参数
        - opt: 命令选项名称
        - opt_arg: 命令选项参数
        - main_args: 命令主参数
    """
    _group = False
    headers: Union[List[Union[str, object]], List[Tuple[object, str]]]
    command: str
    options: List[Union[Option, Subcommand]]
    analyser_type: Type["Analyser"]
    formatter_type: Type[AbstractTextFormatter]
    namespace: str
    behaviors: List[Union[ArpamarBehavior, Type[ArpamarBehavior]]]
    action_list: _Actions
    local_args = {}
    custom_types = {}

    global_headers: Union[List[Union[str, object]], List[Tuple[object, str]]] = [""]
    global_behaviors: List[Union[ArpamarBehavior, Type[ArpamarBehavior]]] = []
    global_analyser_type: Type["Analyser"] = DefaultCommandAnalyser  # type: ignore
    global_formatter_type: Type[AbstractTextFormatter] = DefaultTextFormatter  # type: ignore
    global_separators = {" "}
    global_fuzzy_match: bool = False
    global_raise_exception: bool = False

    @classmethod
    def config(
        cls,
        *,
        headers: Optional[Union[List[Union[str, object]], List[Tuple[object, str]]]] = None,
        behaviors: Optional[List[Union[ArpamarBehavior, Type[ArpamarBehavior]]]] = None,
        analyser_type: Optional[Type["Analyser"]] = None,
        formatter_type: Optional[Type[AbstractTextFormatter]] = None,
        separator: Optional[str] = None,
        fuzzy_match: bool = False,
        raise_exception: bool = False,
    ):
        """
        配置 Alconna 的默认属性
        """
        if headers is not None:
            cls.global_headers = headers
        if behaviors is not None:
            cls.global_behaviors.extend(behaviors)
        if analyser_type is not None:
            cls.global_analyser_type = analyser_type
        if formatter_type is not None:
            cls.global_formatter_type = formatter_type
        if separator is not None:
            cls.global_separators = {separator}
        cls.global_fuzzy_match = fuzzy_match
        cls.global_raise_exception = raise_exception
        return cls

    def __init__(
            self,
            command: Optional[str] = None,
            main_args: Union[Args, str, None] = None,
            headers: Optional[Union[List[Union[str, object]], List[Tuple[object, str]]]] = None,
            options: Optional[List[Union[Option, Subcommand]]] = None,
            is_raise_exception: bool = False,
            action: Optional[Union[ArgAction, Callable]] = None,
            namespace: Optional[str] = None,
            separators: Optional[Union[str, Iterable[str]]] = None,
            help_text: Optional[str] = None,
            analyser_type: Optional[Type["Analyser"]] = None,
            behaviors: Optional[List[T_ABehavior]] = None,
            formatter_type: Optional[Type[AbstractTextFormatter]] = None,
            is_fuzzy_match: bool = False,
    ):
        """
        以标准形式构造 Alconna

        Args:
            headers: 呼叫该命令的命令头, 一般是你的机器人的名字或者符号, 与 command 至少有一个填写
            command: 命令名称, 你的命令的名字, 与 headers 至少有一个填写
            options: 命令选项, 你的命令可选择的所有 option, 包括子命令与单独的选项
            main_args: 主参数, 填入后当且仅当命令中含有该参数时才会成功解析
            is_raise_exception: 当解析失败时是否抛出异常, 默认为 False
            action: 命令解析后针对主参数的回调函数
            namespace: 命令命名空间, 默认为 'Alconna'
            separators: 命令参数分隔符, 默认为空格
            help_text: 帮助文档, 默认为 'Unknown Information'
            analyser_type: 命令解析器类型, 默认为 DisorderCommandAnalyser
            behaviors: 命令解析行为，默认为 None
            formatter_type: 命令帮助文本格式器类型, 默认为 DefaultHelpTextFormatter
            is_fuzzy_match: 是否开启模糊匹配, 默认为 False
        """
        if all((not headers, not command)):
            command = sys.modules["__main__"].__file__.split("/")[-1].split(".")[0]  # type: ignore
        self.headers = headers or self.__class__.global_headers
        self.command = command or ""
        self.options = options or []
        super().__init__(
            f"{command_manager.sign}{command or self.headers[0]}",
            main_args,
            action=action,
            separators=separators or self.__class__.global_separators.copy(),  # type: ignore
            help_text=help_text or "Unknown Information"
        )
        self.action_list = {"options": {}, "subcommands": {}, "main": None}
        self.namespace = namespace or command_manager.default_namespace
        self.options.extend([HelpOption, ShortcutOption])
        self.analyser_type = analyser_type or self.__class__.global_analyser_type
        self.behaviors = behaviors or self.__class__.global_behaviors.copy()
        self.behaviors.insert(0, ActionHandler())
        self.formatter_type = formatter_type or self.__class__.global_formatter_type
        self.is_fuzzy_match = is_fuzzy_match or self.__class__.global_fuzzy_match
        self.is_raise_exception = is_raise_exception or self.__class__.global_raise_exception

        command_manager.register(compile(self))
        self.name = self.name.replace(command_manager.sign, "")

    def __union__(self, other: Union["Alconna", AlconnaGroup]) -> AlconnaGroup:
        """
        合并两个 重名的Alconna 实例
        """
        if self.path != other.path:
            raise ValueError("两个命令的命令名称不一致")
        if isinstance(other, Alconna):
            return AlconnaGroup(self.name, self, other, namespace=self.namespace)
        return other.append(self)

    @property
    def path(self) -> str:
        return f"{self.namespace}.{self.name.replace(command_manager.sign, '')}"

    def reset_namespace(self, namespace: str):
        """重新设置命名空间"""
        command_manager.delete(self)
        self.namespace = namespace
        command_manager.register(compile(self))
        return self

    def reset_behaviors(self, behaviors: List[T_ABehavior]):
        """重新设置解析行为器"""
        self.behaviors = behaviors
        self.behaviors.insert(0, ActionHandler())
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter_type(self).format_node()

    @classmethod
    def set_custom_types(cls, **types: Type):
        """设置Alconna内的自定义类型"""
        cls.custom_types = types

    def shortcut(
            self,
            short_key: str,
            command: Optional[str] = None,
            delete: bool = False,
            expiration: int = 0
    ):
        """添加快捷命令"""
        try:
            if delete:
                command_manager.delete_shortcut(short_key, self)
                return lang_config.shortcut_delete_success.format(
                    shortcut=short_key, target=self.path.split(".")[-1])
            if command:
                command_manager.add_shortcut(self, short_key, command, expiration)
                return lang_config.shortcut_add_success.format(
                    shortcut=short_key, target=self.path.split(".")[-1])
            elif cmd := command_manager.recent_message:
                alc = command_manager.last_using
                if alc and alc == self:
                    command_manager.add_shortcut(self, short_key, cmd, expiration)
                    return lang_config.shortcut_add_success.format(
                        shortcut=short_key, target=self.path.split(".")[-1])
                raise ValueError(
                    lang_config.shortcut_recent_command_error.format(
                        target=self.path, source=getattr(alc, "path", "Unknown Source"))
                )
            else:
                raise ValueError(lang_config.shortcut_no_recent_command)
        except Exception as e:
            if self.is_raise_exception:
                raise e
            return str(e)

    def __repr__(self):
        return f"<{self.namespace}::{self.name} with {len(self.options)} options; args={self.args}>"

    def add_option(
            self,
            name: str,
            *alias: str,
            args: Optional[Args] = None,
            sep: str = " ",
            help_text: Optional[str] = None,
    ):
        """链式注册一个 Option"""
        command_manager.delete(self)
        names = name.split(sep)
        name, requires = names[-1], names[:-1]
        opt = Option(name, args, list(alias), separators=sep, help_text=help_text, requires=requires)
        self.options.append(opt)
        command_manager.register(compile(self))
        return self

    def set_action(self, action: Union[Callable, str, ArgAction], custom_types: Optional[Dict[str, Type]] = None):  # type: ignore
        """设置针对main_args的action"""
        if isinstance(action, str):
            ns = {}
            exec(action, getattr(self, "custom_types", custom_types), ns)
            action: Callable = ns.popitem()[1]
        self.action = ArgAction.__validator__(action, self.args)
        return self

    @overload
    def parse(
            self,
            message: Union[str, DataCollection],
            duplication: Type[T_Duplication],
            static: bool = True,

    ) -> T_Duplication:
        ...

    @overload
    def parse(
            self,
            message: Union[str, DataCollection],
            duplication=None,
            static: bool = True
    ) -> Arpamar:
        ...

    def parse(
            self,
            message: Union[str, DataCollection],
            duplication: Optional[Type[T_Duplication]] = None,
            static: bool = True,
    ):
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        analyser = command_manager.require(self) if static else compile(self)
        analyser.process_message(message)
        arp = analyser.analyse()
        if arp.matched:
            arp.execute()
        if duplication:
            return duplication(self).set_target(arp)
        return arp

    def __truediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rtruediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rshift__(self, other):
        if isinstance(other, Option):
            command_manager.delete(self)
            self.options.append(other)
            command_manager.register(compile(self))
        elif isinstance(other, str):
            command_manager.delete(self)
            _part = other.split("/")
            self.options.append(Option(_part[0], _part[1] if len(_part) > 1 else None))
            command_manager.register(compile(self))
        return self

    def __add__(self, other):
        return self.__rshift__(other)

    def __hash__(self):
        return hash(
            (self.path + str(self.args.argument.keys()) + str([i['value'] for i in self.args.argument.values()])
             + str(self.headers), *self.options)
        )
