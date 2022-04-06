"""Alconna 主体"""
from typing import Dict, List, Optional, Union, Type, Callable, Any, Tuple, TypeVar, overload
from .analysis.analyser import Analyser
from .analysis import compile
from .base import CommandNode, Args, ArgAction
from .component import Option, Subcommand
from .arpamar import Arpamar, ArpamarBehavior
from .arpamar.duplication import AlconnaDuplication
from .types import DataCollection, DataUnit
from .manager import command_manager
from .visitor import AlconnaNodeVisitor, AbstractHelpTextFormatter
from .builtin.formatter import DefaultHelpTextFormatter
from .builtin.analyser import DisorderCommandAnalyser

T_Duplication = TypeVar('T_Duplication', bound=AlconnaDuplication)


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
    ...         Option("opt", Args["opt_arg":"opt_arg"]),
    ...         Subcommand(
    ...             "sub_name",
    ...             Option("sub_opt", Args["sub_arg":"sub_arg"]),
    ...             args=Args["sub_main_args":"sub_main_args"]
    ...         )
    ...     ],
    ...     main_args=Args["main_args":"main_args"],
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

    headers: Union[List[Union[str, DataUnit]], List[Tuple[DataUnit, str]]]  # type: ignore
    command: str
    options: List[Union[Option, Subcommand]]
    analyser_type: Type[Analyser]
    custom_types: Dict[str, Type] = {}
    namespace: str
    __cls_name__: str = "Alconna"
    local_args: dict = {}
    formatter: AbstractHelpTextFormatter
    default_analyser: Type[Analyser] = DisorderCommandAnalyser  # type: ignore

    def __init__(
            self,
            command: Optional[str] = None,
            main_args: Union[Args, str, None] = None,
            headers: Optional[Union[List[Union[str, DataUnit]], List[Tuple[DataUnit, str]]]] = None,
            options: Optional[List[Union[Option, Subcommand]]] = None,
            is_raise_exception: bool = False,
            action: Optional[Union[ArgAction, Callable]] = None,
            namespace: Optional[str] = None,
            separator: str = " ",
            help_text: Optional[str] = None,
            analyser_type: Optional[Type[Analyser]] = None,
            behaviors: Optional[List[ArpamarBehavior]] = None,
            formatter: Optional[AbstractHelpTextFormatter] = None,
            is_fuzzy_match: bool = False
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
            separator: 命令参数分隔符, 默认为空格
            help_text: 帮助文档, 默认为 'Unknown Information'
            analyser_type: 命令解析器类型, 默认为 DisorderCommandAnalyser
            behaviors: 命令解析行为，默认为 None
            formatter: 命令帮助文本格式器, 默认为 DefaultHelpTextFormatter
            is_fuzzy_match: 是否开启模糊匹配, 默认为 False
        """
        # headers与command二者必须有其一
        if all((not headers, not command)):
            command = "Alconna"
        self.headers = headers or [""]
        self.command = command or ""
        self.options = options or []
        super().__init__(
            f"ALCONNA::{command or self.headers[0]}",
            main_args,
            action,
            separator,
            help_text or "Unknown Information"
        )
        self.is_raise_exception = is_raise_exception
        self.namespace = namespace or self.__cls_name__
        self.options.append(Option("--help", alias=["-h"], help_text="显示帮助信息"))
        self.analyser_type = analyser_type or self.default_analyser
        command_manager.register(compile(self))
        self.__class__.__cls_name__ = "Alconna"
        self.behaviors = behaviors
        self.formatter = formatter or DefaultHelpTextFormatter()  # type: ignore
        self.is_fuzzy_match = is_fuzzy_match

    def __class_getitem__(cls, item):
        if isinstance(item, str):
            cls.__cls_name__ = item
        return cls

    def reset_namespace(self, namespace: str):
        """重新设置命名空间"""
        command_manager.delete(self)
        self.namespace = namespace
        command_manager.register(self)
        return self

    def reset_behaviors(self, behaviors: List[ArpamarBehavior]):
        self.behaviors = behaviors
        return self

    def get_help(self) -> str:
        """返回 help 文档"""
        return AlconnaNodeVisitor(self).format_node(self.formatter)

    @classmethod
    def set_custom_types(cls, **types: Type):
        """设置自定义类型"""
        cls.custom_types = types

    def shortcut(self, short_key: str, command: str, reserve_args: bool = False):
        """添加快捷键"""
        command_manager.add_shortcut(self, short_key, command, reserve_args)

    def __repr__(self):
        return (
            f"<ALC.{self.namespace}::{self.command or self.headers[0]} "
            f"with {len(self.options)} options; args={self.args}>"
        )

    def option(
            self,
            name: str,
            sep: str = " ",
            args: Optional[Args] = None,
            help_text: Optional[str] = None,
    ):
        """链式注册一个 Option"""
        command_manager.delete(self)
        opt = Option(name, args, separator=sep, help_text=help_text)
        self.options.append(opt)
        command_manager.register(self)
        return self

    def set_action(self, action: Union[Callable, str, ArgAction], custom_types: Optional[Dict[str, Type]] = None):
        """设置针对main_args的action"""
        if isinstance(action, str):
            ns = {}
            exec(action, getattr(self, "custom_types", custom_types), ns)
            action = ns.popitem()[1]
        self.__check_action__(action)
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
        if static:
            analyser = command_manager.require(self)
        else:
            analyser = compile(self)
        result = analyser.handle_message(message)
        if duplication:
            arp = (result or analyser.analyse()).update(self.behaviors)
            dup = duplication(self).set_target(arp)
            return dup
        return (result or analyser.analyse()).update(self.behaviors)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "headers": self.headers,
            "command": self.command,
            "options": [opt.to_dict() for opt in self.options if opt.name != "--help"],
            "main_args": self.args.to_dict(),
            "is_raise_exception": self.is_raise_exception,
            "separator": self.separator,
            "namespace": self.namespace,
            "help_text": self.help_text,
        }

    def __truediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rtruediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rmatmul__(self, other):
        self.reset_namespace(other)
        return self

    def __matmul__(self, other):
        self.reset_namespace(other)
        return self

    def __radd__(self, other):
        if isinstance(other, Option):
            command_manager.delete(self)
            self.options.append(other)
            command_manager.register(self)
        return self

    def __add__(self, other):
        return self.__radd__(other)

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alconna":
        """从字典中恢复一个 Alconna 对象"""
        headers = data["headers"]
        command = data["command"]
        options = []
        for o in data["options"]:
            if o['type'] == 'Option':
                options.append(Option.from_dict(o))
            elif o['type'] == 'Subcommand':
                options.append(Subcommand.from_dict(o))
        main_args = Args.from_dict(data["main_args"])
        is_raise_exception = data["is_raise_exception"]
        namespace = data["namespace"]
        return cls(
            command=command, options=options, main_args=main_args, headers=headers,
            is_raise_exception=is_raise_exception, namespace=namespace,
            separator=data["separator"], help_text=data["help_text"],
        )

    def __setstate__(self, state):
        options = []
        for o in state["options"]:
            if o['type'] == 'Option':
                options.append(Option.from_dict(o))
            elif o['type'] == 'Subcommand':
                options.append(Subcommand.from_dict(o))
        self.__init__(
            headers=state["headers"], command=state["command"], options=options,
            main_args=Args.from_dict(state["main_args"]), is_raise_exception=state["is_raise_exception"],
            namespace=state["namespace"], separator=state["separator"], help_text=state["help_text"],
        )
