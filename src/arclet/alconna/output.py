from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable
from weakref import finalize


@dataclass(init=True, unsafe_hash=True)
class Sender:
    """发送器"""

    action: Callable[..., Any]
    """发送行为函数"""
    generator: Callable[[], str]
    """发送内容生成器"""

    def __call__(self, *args, **kwargs):
        res = self.generator()
        data = self.action(res)
        return data if data and isinstance(data, dict) else {"output": res}


@dataclass
class OutputManager:
    """命令输出管理器"""

    cache: dict[str, Callable] = field(default_factory=dict)
    """缓存的输出行为"""
    outputs: dict[str, Sender] = field(default_factory=dict)
    """输出行为"""
    send_action: Callable[[str], Any] = field(default=print)  # type: ignore
    """默认的发送行为"""
    _out_cache: dict[str, dict[str, Any]] = field(default_factory=dict, hash=False, init=False)

    def __post_init__(self):
        def _clr(mgr: OutputManager):
            mgr.cache.clear()
            mgr.outputs.clear()
            mgr._out_cache.clear()

        finalize(self, _clr, self)

    def send(self, command: str | None = None, generator: Callable[[], str] | None = None):
        """调用指定的输出行为

        Args:
            command (str | None, optional): 输出行为对应的命令名称
            generator (Callable[[], str] | None, optional): 输出内容生成器
        """
        if sender := self.get(command):
            if generator:
                sender.generator = generator
        elif generator:
            sender = self.set(generator, command)
        else:
            raise KeyError(f"Command {command} not found")
        res = sender()
        if command in self._out_cache:
            self._out_cache[command].update(res)
        return res

    def get(self, command: str | None = None) -> Sender | None:
        """获取指定的输出行为

        Args:
            command (str | None, optional): 输出行为对应的命令名称
        """
        return self.outputs.get(command or "$global")

    def set(self, generator: Callable[[], str], command: str | None = None) -> Sender:
        """设置指定的输出行为

        Args:
            generator (Callable[[], str]): 输出内容生成器
            command (str | None, optional): 输出行为对应的命令名称
        """
        command = command or "$global"
        if command in self.outputs:
            self.outputs[command].generator = generator
        elif command in self.cache:
            self.outputs[command] = Sender(self.cache.pop(command), generator)
        else:
            self.outputs[command] = Sender(self.send_action, generator)
        return self.outputs[command]

    def set_action(self, action: Callable[[str], Any], command: str | None = None):
        """修改输出行为

        Args:
            action (Callable[[str], Any]): 输出行为函数
            command (str | None, optional): 输出行为指定对应的命令名称
        """
        if command is None or command == "$global":
            self.send_action = action
        elif cmd := self.outputs.get(command):
            cmd.action = action
        else:
            self.cache[command] = action

    @contextmanager
    def capture(self, command: str | None = None):
        """捕获输出

        Args:
            command (str | None, optional): 输出行为指定对应的命令名称

        Yields:
            dict[str, Any]: 输出内容
        """
        command = command or "$global"
        _cache = self._out_cache.setdefault(command, {})
        yield _cache
        _cache.clear()


output_manager = OutputManager()

__all__ = ["output_manager"]
