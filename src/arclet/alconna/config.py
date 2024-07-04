from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, ContextManager, Literal, TypedDict


from .i18n import lang as lang
from .typing import DataCollection, TPrefixes

if TYPE_CHECKING:
    from .formatter import TextFormatter


class OptionNames(TypedDict):
    help: set[str]
    """帮助选项的名称"""
    shortcut: set[str]
    """快捷选项的名称"""
    completion: set[str]
    """补全选项的名称"""


@dataclass(init=True, repr=True)
class Namespace:
    """命名空间配置, 用于规定同一命名空间下的选项的默认配置"""

    name: str
    """命名空间名称"""
    prefixes: TPrefixes = field(default_factory=list)
    """默认前缀配置"""
    separators: tuple[str, ...] = field(default_factory=lambda: (" ",))
    """默认分隔符配置"""
    formatter_type: type[TextFormatter] | None = field(default=None)  # type: ignore
    """默认格式化器类型"""
    fuzzy_match: bool = field(default=False)
    """默认是否开启模糊匹配"""
    raise_exception: bool = field(default=False)
    """默认是否抛出异常"""
    enable_message_cache: bool = field(default=True)
    """默认是否启用消息缓存"""
    disable_builtin_options: set[Literal["help", "shortcut", "completion"]] = field(default_factory=set)
    builtin_option_name: OptionNames = field(
        default_factory=lambda: {
            "help": {"--help", "-h"},
            "shortcut": {"--shortcut", "-sct"},
            "completion": {"--comp", "-cp", "?"},
        }
    )
    """默认的内置选项名称"""
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    """默认的选项转文本函数"""
    converter: Callable[[str | list], DataCollection[Any]] | None = field(default=lambda x: x)
    """默认的文本转选项函数"""
    compact: bool = field(default=False)
    """默认是否开启紧凑模式"""
    strict: bool = field(default=True)
    "命令是否严格匹配，若为 False 则未知参数将作为名为 $extra 的参数"
    context_style: Literal["bracket", "parentheses"] | None = field(default=None)
    "命令上下文插值的风格，None 为关闭，bracket 为 {...}，parentheses 为 $(...)"

    def __eq__(self, other):
        return isinstance(other, Namespace) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    @property
    def headers(self):
        """默认前缀配置"""
        return self.prefixes

    @headers.setter
    def headers(self, value):
        self.prefixes = value


class namespace(ContextManager[Namespace]):
    """新建一个命名空间配置并暂时作为默认命名空间

    Example:
        >>> with namespace("xxx") as ns:
        ...     ns.headers = ["aaa"]
        ...     alc = Alconna(...)
        ... assert alc.prefixes == ["aaa"]
    """

    def __init__(self, name: Namespace | str):
        """传入新建的命名空间的名称, 或者是一个存在的命名空间配置"""
        if isinstance(name, Namespace):
            self.np = name
            self.name = name.name
            if name.name not in config.namespaces:
                config.namespaces[name.name] = name
        elif name in config.namespaces:
            self.np = config.namespaces[name]
            self.name = name
        else:
            self.np = Namespace(name)
            self.name = name
            config.namespaces[name] = self.np
        self.old = config.default_namespace
        config.default_namespace = self.np

    def __enter__(self) -> Namespace:
        return self.np

    def __exit__(self, exc_type, exc_val, exc_tb):
        config.default_namespace = self.old
        config.namespaces[self.name] = self.np
        del self.old
        del self.np
        if exc_type or exc_val or exc_tb:
            return False


class _AlconnaConfig:
    """全局配置类"""

    command_max_count: int = 200
    """最大命令数量"""
    _default_namespace = "Alconna"
    """默认命名空间名称"""
    remainders: set[str] = {"--"}
    """参数分隔标记"""
    namespaces: dict[str, Namespace] = {_default_namespace: Namespace(_default_namespace)}

    @property
    def default_namespace(self):
        return self.namespaces[self._default_namespace]

    @default_namespace.setter
    def default_namespace(self, np: str | Namespace):
        if isinstance(np, str):
            if np not in self.namespaces:
                old = self.namespaces.pop(self._default_namespace, Namespace(np))
                old.name = np
                self.namespaces[np] = old
            self._default_namespace = np
        else:
            self._default_namespace = np.name
            self.namespaces[np.name] = np


config = _AlconnaConfig()

__all__ = ["config", "Namespace", "namespace", "lang"]
