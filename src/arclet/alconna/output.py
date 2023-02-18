from __future__ import annotations

from weakref import finalize
from typing import Callable, Any
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass(init=True, unsafe_hash=True)
class OutputAction:
    action: Callable[..., Any]
    generator: Callable[[], str]

    def handle(self, raise_exc: bool = False):
        res = self.generator()
        try:
            data = self.action(res)
            return data if data and isinstance(data, dict) else {"output": res}
        except Exception as e:
            if raise_exc:
                raise e
        return {"output": res}


@dataclass
class OutputActionManager:
    """帮助信息"""
    cache: dict[str, Callable] = field(default_factory=dict)
    outputs: dict[str, OutputAction] = field(default_factory=dict)
    send_action: Callable[[str], Any] = field(default=lambda x: print(x))
    _out_cache: dict[str, dict[str, Any]] = field(default_factory=dict, hash=False, init=False)

    def __post_init__(self):
        def _clr(mgr: OutputActionManager):
            mgr.cache.clear()
            mgr.outputs.clear()
            mgr._out_cache.clear()

        finalize(self, _clr, self)

    def send(self, command: str | None = None, generator: Callable[[], str] | None = None, raise_exception=False):
        """调用指定的输出行为"""
        if action := self.get(command):
            if generator:
                action.generator = generator
        elif generator:
            action = self.set(generator, command)
        else:
            raise KeyError(f"Command {command} not found")
        res = action.handle(raise_exc=raise_exception)
        if command in self._out_cache:
            self._out_cache[command].update(res)
        return res

    def get(self, command: str | None = None) -> OutputAction | None:
        """获取指定的输出行为"""
        return self.outputs.get(command or "$global")

    def set(self, generator: Callable[[], str], command: str | None = None) -> OutputAction:
        """设置指定的输出行为"""
        command = command or "$global"
        if command in self.outputs:
            self.outputs[command].generator = generator
        elif command in self.cache:
            self.outputs[command] = OutputAction(self.cache.pop(command), generator)
        else:
            self.outputs[command] = OutputAction(self.send_action, generator)
        return self.outputs[command]

    def set_action(self, action: Callable[[str], Any], command: str | None = None):
        """修改输出行为"""
        if command is None or command == "$global":
            self.send_action = action
        elif cmd := self.outputs.get(command):
            cmd.action = action
        else:
            self.cache[command] = action

    @contextmanager
    def capture(self, command: str | None = None):
        """捕获输出"""
        command = command or "$global"
        _cache = self._out_cache.setdefault(command, {})
        yield _cache
        _cache.clear()


output_manager = OutputActionManager()

__all__ = ["output_manager"]
