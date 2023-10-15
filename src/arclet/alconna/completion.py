from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tarina import ContextModel, lang

from .arparma import Arparma
from .exceptions import ParamsUnmatched, PauseTriggered, SpecialOptionTriggered
from .manager import command_manager
from .output import output_manager

if TYPE_CHECKING:
    from .core import Alconna


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class Prompt:
    text: str = field(hash=True)
    can_use: bool = field(default=True, hash=False)
    removal_prefix: str | None = field(default=None, hash=False)

@dataclass
class EnterResult:
    result: Arparma | None = None
    exception: Exception | None = None


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
        argv = command_manager.resolve(self.source.command)
        _b, _r, _i, _n = argv.bak_data.copy(), argv.raw_data.copy(), argv.current_index, argv.ndata
        if content:
            input_ = content
        else:
            if not self.prompts:
                return EnterResult(exception=ValueError(lang.require("completion", "prompt_empty")))
            prompt = self.prompts[self.index]
            if not prompt.can_use:
                return EnterResult(exception=ValueError(lang.require("completion", "prompt_unavailable")))
            if prompt.removal_prefix:
                argv.bak_data[-1] = argv.bak_data[-1][:-len(prompt.removal_prefix)]
                argv.next(move=True)
            input_ = [prompt.text]
        if isinstance(self.trigger, ParamsUnmatched):
            argv.raw_data = argv.bak_data[:max(_i, 1)]
            argv.addon(input_)
            argv.raw_data.extend(_r[max(_i, 1):])
        else:
            argv.raw_data = argv.bak_data.copy()
            argv.addon(input_)
        argv.bak_data = argv.raw_data.copy()
        argv.ndata = len(argv.bak_data)
        argv.current_index = 0
        if argv.message_cache:
            argv.token = argv.generate_token(argv.raw_data)
        exc = None
        try:
            res = self.source.process(argv)
            if not res.matched:
                exc = res.error_info
            if isinstance(exc, SpecialOptionTriggered):
                self.exit()
                return EnterResult(res)
        except Exception as e:
            exc = e
        if exc:
            if isinstance(exc, PauseTriggered):
                self.fresh(exc)
                return EnterResult(exception=self.trigger if isinstance(self.trigger, ParamsUnmatched) else None)
            argv.bak_data, argv.raw_data, argv.current_index, argv.ndata = _b, _r, _i, _n
            return EnterResult(exception=exc)
        self.exit()
        return EnterResult(res)  # noqa

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
        return [
            f"{'>>' if self.index == index else '*'} {sug.text}"
            for index, sug in enumerate(self.prompts)
        ]

    def __repr__(self):
        return f"{lang.require('completion', 'node')}\n" + "\n".join(self.lines())

    def send_prompt(self):
        """打印补全文本。"""
        return output_manager.send(self.source.command.name, self.__repr__)

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
        self.trigger = exc.args[1]
        return True

comp_ctx: ContextModel[CompSession] = ContextModel("comp_ctx")
