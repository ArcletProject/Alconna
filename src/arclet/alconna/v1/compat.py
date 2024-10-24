from __future__ import annotations

from typing import Literal, Any, Callable, ContextManager
from typing_extensions import deprecated
from arclet.alconna import Metadata, Config, global_config
from arclet.alconna import Namespace as _Namespace


@deprecated("CommandMeta is deprecated, use Metadata and Config instead", category=DeprecationWarning, stacklevel=1)
def CommandMeta(
    description: str = "Unknown",
    usage: str | None = None,
    example: str | None = None,
    author: str | None = None,
    fuzzy_match: bool = False,
    fuzzy_threshold: float = 0.6,
    raise_exception: bool = False,
    hide: bool = False,
    hide_shortcut: bool = False,
    keep_crlf: bool = False,
    compact: bool = False,
    strict: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    extra: dict[str, Any] | None = None,
):
    return (
        Metadata(description, usage, example, author),
        Config(
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            raise_exception=raise_exception,
            hide=hide,
            hide_shortcut=hide_shortcut,
            keep_crlf=keep_crlf,
            compact=compact,
            strict=strict,
            context_style=context_style,
            extra=extra or {},
        )
    )


def Namespace(
    name: str,
    prefixes: list[str] | None = None,
    separators: tuple[str, ...] = (" ",),
    formatter_type: Any = None,
    fuzzy_match: bool = False,
    raise_exception: bool = False,
    enable_message_cache: bool = True,
    disable_builtin_options: set[Literal["help", "shortcut", "completion"]] | None = None,
    builtin_option_name: dict[str, set[str]] | None = None,
    to_text: Callable[[Any], str | None] = lambda x: x if isinstance(x, str) else None,
    converter: Callable[[str | list], Any] | None = lambda x: x,
    compact: bool = False,
    strict: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
):
    return _Namespace(
        name,
        Config(
            fuzzy_match=fuzzy_match,
            raise_exception=raise_exception,
            enable_message_cache=enable_message_cache,
            disable_builtin_options=disable_builtin_options or {"shortcut"},  # type: ignore
            builtin_option_name=builtin_option_name or {"help": {"--help", "-h"}, "shortcut": {"--shortcut", "-sct"}, "completion": {"--comp", "-cp", "?"}},  # type: ignore
            compact=compact,
            strict=strict,
            context_style=context_style,
        ),
        prefixes or [],
        "".join(separators),
        formatter_type,
        to_text,
        converter,
    )


class _ProxyNamespace:
    def __init__(self, origin: _Namespace):
        self.origin = origin

    def __getattr__(self, item):
        if item == "separators":
            return tuple(self.origin.separators)
        if item in ("name", "prefixes", "formatter_type", "to_text", "converter"):
            return getattr(self.origin, item)
        return getattr(self.origin.config, item)

    def __setattr__(self, key, value):
        if key == "separators":
            self.origin.separators = "".join(value)
        elif key in ("name", "prefixes", "formatter_type", "to_text", "converter"):
            setattr(self.origin, key, value)
        else:
            setattr(self.origin.config, key, value)


class namespace(ContextManager[Namespace]):
    def __init__(self, name: _Namespace | str):
        """传入新建的命名空间的名称, 或者是一个存在的命名空间配置"""
        if isinstance(name, _Namespace):
            self.np = name
            self.name = name.name
            if name.name not in global_config.namespaces:
                global_config.namespaces[name.name] = name
        elif name in global_config.namespaces:
            self.np = global_config.namespaces[name]
            self.name = name
        else:
            self.np = Namespace(name)
            self.name = name
            global_config.namespaces[name] = self.np
        self.old = global_config.default_namespace
        global_config.default_namespace = self.np

    def __enter__(self) -> _ProxyNamespace:
        return _ProxyNamespace(self.np)

    def __exit__(self, exc_type, exc_val, exc_tb):
        global_config.default_namespace = self.old
        global_config.namespaces[self.name] = self.np
        del self.old
        del self.np
        if exc_type or exc_val or exc_tb:
            return False


__all__ = ["CommandMeta", "Namespace", "namespace"]
