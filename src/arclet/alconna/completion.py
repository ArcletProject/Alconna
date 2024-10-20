from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tarina import ContextModel, lang

from .arparma import Arparma
from .exceptions import InvalidParam, ParamsUnmatched, PauseTriggered
from .manager import command_manager
from .base import Subcommand, SPECIAL_OPTIONS, Option
from .args import Arg

if TYPE_CHECKING:
    from .argv import Argv
    from .core import Alconna


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class Prompt:
    text: str = field(hash=True)
    can_use: bool = field(default=True, hash=False)
    removal_prefix: str | None = field(default=None, hash=False)


@dataclass
class EnterResult:
    result: Arparma | None = None
    exception: type[Exception] | Exception | None = None


class CompSession:
    """补全会话，用于交互式处理触发的补全选项。

    Examples:
        >>> from arclet.alconna import Alconna, CompSession
        >>> alc = Alconna(...)
        >>> with CompSession(alc) as comp:
        ...     res = alc.parse("test")
        ...
        >>> while comp.available:
        ...     print(comp.current())
        ...     print(comp.tab())
        ...     _res = comp.enter()
        ...     if _res.result:
        ...         res = _res.result
        ...         break
        ...
        >>> print(res)

    Attributes:
        index (int): 当前选中的补全选项的索引。
        prompts (list[Prompt]): 补全选项列表。
    """

    index: int
    prompts: list[Prompt]

    def __init__(self, source: Alconna):
        """初始化补全会话。

        Args:
            source (Alconna): 补全的源命令。
        """
        self.source = command_manager.require(source)
        self.index = 0
        self.prompts = []
        self.trigger = None
        self._token = None

        self.raw_data = []
        self.bak_data = []
        self.current_index = 0

    @property
    def available(self):
        """表示当前补全会话是否可用。"""
        return bool(self.prompts)

    def current(self):
        """获取当前选中的补全选项的文本。"""
        if not self.prompts:
            raise ValueError(lang.require("completion", "prompt_empty"))
        return self.prompts[self.index].text

    def tab(self, offset: int = 1):
        """切换补全选项。

        Args:
            offset (int, optional): 切换的偏移量。默认为 1。

        Returns:
            str: 切换后的补全选项的文本。

        Raises:
            ValueError: 当前没有可用的补全选项。
        """
        if not self.prompts:
            raise ValueError(lang.require("completion", "prompt_empty"))
        self.index += offset
        self.index %= len(self.prompts)
        return self.prompts[self.index].text

    def enter(self, content: list | None = None) -> EnterResult:
        """确认当前补全选项。

        Args:
            content (list, optional): 补全选项的内容。不传入则使用当前选中的补全选项文本

        Returns:
            Any: 补全后执行的结果。

        Raises:
            ValueError: 当前没有可用的补全选项, 或者当前补全选项不可用。
        """
        argv = command_manager.require(self.source.command).argv
        argv.raw_data = self.raw_data.copy()
        argv.bak_data = self.bak_data.copy()
        argv.current_index = self.current_index
        if content:
            input_ = content
        else:
            if not self.prompts:
                return EnterResult(exception=ValueError(lang.require("completion", "prompt_empty")))
            prompt = self.prompts[self.index]
            if not prompt.can_use:
                return EnterResult(exception=ValueError(lang.require("completion", "prompt_unavailable")))
            if prompt.removal_prefix:
                argv.bak_data[-1] = argv.bak_data[-1][: -len(prompt.removal_prefix)]
                argv.next()
            input_ = [prompt.text]
        if isinstance(self.trigger, InvalidParam):
            argv.raw_data = argv.bak_data[: max(self.current_index, 1)]
            argv.addon(input_)
            argv.raw_data.extend(self.raw_data[max(self.current_index, 1):])
        else:
            argv.raw_data = argv.bak_data.copy()
            argv.addon(input_)
        argv.raw_data = [i for i in argv.raw_data if i != ""]
        argv.bak_data = argv.raw_data.copy()
        argv.ndata = len(argv.bak_data)
        argv.current_index = 0
        argv.origin = argv.converter(argv.raw_data)
        if argv.message_cache:
            argv.token = argv.generate_token(argv.raw_data)
            if res := command_manager.get_record(argv.token):
                self.exit()
                return EnterResult(res)
        if exc := self.source.process(argv):
            if isinstance(exc, ParamsUnmatched):
                self.exit()
                return EnterResult(self.source.export(argv, True, exc))
            if isinstance(exc, PauseTriggered):
                self.fresh(exc)
                return EnterResult(exception=self.trigger if isinstance(self.trigger, InvalidParam) else None)
            return EnterResult(exception=exc)
        self.exit()
        return EnterResult(self.source.export(argv))  # noqa # type: ignore

    def push(self, *suggests: Prompt):
        """添加补全选项。

        Args:
            suggests (Prompt): 补全选项。

        Returns:
            self: 补全会话本身。
        """
        self.prompts.extend(suggests)
        return self

    def clear(self):
        """清空补全选项。"""
        self.index = 0
        self.prompts.clear()
        self.source.reset()
        self.raw_data = []
        self.bak_data = []
        self.current_index = 0
        return self

    def exit(self):
        """退出补全会话。"""
        self.clear()
        if self._token:
            comp_ctx.reset(self._token)
            self._token = None
        return self

    def lines(self):
        """获取补全选项的文本列表。"""
        select = lang.require("completion", "prompt_select")
        other = lang.require("completion", "prompt_other")
        return [f"{select if self.index == index else other}{sug.text}" for index, sug in enumerate(self.prompts)]

    def __repr__(self):
        node = lang.require('completion', 'node')
        node = f"{node}\n" if node else ""
        return node + "\n".join(self.lines())

    def __enter__(self):
        self._token = comp_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is PauseTriggered:
            self.fresh(exc_val)
            return True

    def fresh(self, exc: PauseTriggered):
        """刷新补全会话。

        Args:
            exc (PauseTriggered): 暂停异常。
        """
        self.clear()
        self.push(*exc.args[0])
        self.trigger = exc.context_node
        argv = exc.argv
        self.raw_data = argv.raw_data
        self.bak_data = argv.bak_data
        self.current_index = argv.current_index
        return True


comp_ctx: ContextModel[CompSession] = ContextModel("comp_ctx")


def _prompt_none(command: Alconna, args_got: list[str], opts_got: list[str]):
    res: list[Prompt] = []
    if unit := next((arg for arg in command.args if arg.name not in args_got), None):
        if not (comp := unit.field.get_completion()):
            res.append(Prompt(command.formatter.param(unit), False))
        elif isinstance(comp, str):
            res.append(Prompt(f"{unit.name}: {comp}", False))
        else:
            res.extend(Prompt(f"{unit.name}: {i}", False) for i in comp)
    for opt in command.options:
        if isinstance(opt, SPECIAL_OPTIONS):
            continue
        if opt.dest not in opts_got:
            res.extend([Prompt(al) for al in opt.aliases] if isinstance(opt, Option) else [Prompt(opt.name)])
    return res


def prompt(command: Alconna, argv: Argv, args_got: list[str], opts_got: list[str], trigger: str | Arg | Subcommand | None = None):
    """获取补全列表"""
    releases = argv.release(recover=True)
    target = str(releases[-1])
    if isinstance(releases[-1], str) and releases[-1] in command.namespace_config.builtin_option_name["completion"]:
        target = str(releases[-2])
    if isinstance(trigger, Arg):
        if not (comp := trigger.field.get_completion()):
            return [Prompt(command.formatter.param(trigger), False)]
        if isinstance(comp, str):
            return [Prompt(f"{trigger.name}: {comp}", False)]
        o = list(filter(lambda x: target in x, comp)) or comp
        return [Prompt(f"{trigger.name}: {i}", False, target) for i in o]
    elif isinstance(trigger, Subcommand):
        return [Prompt(i) for i in argv.stack_params.stack[-1]]
    if isinstance(trigger, str):
        target = trigger
    if _res := list(filter(lambda x: target in x, argv.stack_params.base)):
        out = [i for i in _res if i not in opts_got]
        return [Prompt(i, True, target) for i in (out or _res)]
    return _prompt_none(command, args_got, opts_got)
