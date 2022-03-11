import abc
import asyncio
from typing import Optional, Union, Callable, Any
from .types import DataCollection
from .main import Alconna
from .arpamar import Arpamar


class Response:
    def __init__(self, origin: Union[str, DataCollection], result: Arpamar, help_text: Optional[str] = None):
        self.origin = origin
        self.result = result
        self.help_text = help_text


class AlconnaMessageProxy(metaclass=abc.ABCMeta):
    loop: asyncio.AbstractEventLoop

    @abc.abstractmethod
    async def fetch_message(self):
        """主动拉取消息"""
        ...

    @abc.abstractmethod
    async def push_message(self, message: Union[str, DataCollection]):
        """被动接收消息"""
        ...

    def register(self, alconna: Alconna, handler: Callable[[Response, Any], Any]):
        ...
