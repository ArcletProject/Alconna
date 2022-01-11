"""Alconna 概览"""

from typing import TYPE_CHECKING
from .util import split_once, split
from .base import TemplateCommand, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, AnyParam, AllParam, Empty, \
    AnyStr, AnyIP, AnyUrl, AnyDigit, AnyFloat, Bool
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam
from .main import Alconna
from .actions import store_bool, store_const, ArgAction
alconna_version = (0, 5, 1)

if TYPE_CHECKING:
    from .actions import version
