"""Alconna 概览"""

from typing import TYPE_CHECKING, Union, Type
from .util import split_once, split
from .base import TemplateCommand, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, AnyParam, AllParam, Empty, \
    AnyStr, AnyIP, AnyUrl, AnyDigit, AnyFloat, Bool
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam, UnexpectedElement
from .main import Alconna
from .actions import store_bool, store_const, ArgAction

alconna_version = (0, 5, 3)
default_chain_texts = ["Plain", "Text"]
default_black_elements = ["Source", "File", "Quote"]
default_white_elements = []

if TYPE_CHECKING:
    from .actions import version


def set_chain_texts(*text: Union[str, Type[NonTextElement]]):
    """设置文本类元素的集合"""
    global default_chain_texts
    default_chain_texts = [t if isinstance(t, str) else t.__name__ for t in text]


def set_black_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的黑名单"""
    global default_black_elements
    default_black_elements = [ele if isinstance(ele, str) else ele.__name__ for ele in element]


def set_white_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的白名单"""
    global default_white_elements
    default_white_elements = [ele if isinstance(ele, str) else ele.__name__ for ele in element]
