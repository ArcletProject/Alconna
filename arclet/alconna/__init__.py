"""Alconna 概览"""

from typing import TYPE_CHECKING
from .util import split_once, split, set_chain_texts, set_black_elements, set_white_elements
from .base import TemplateCommand, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, AnyParam, AllParam, Empty, \
    AnyStr, AnyIP, AnyUrl, AnyDigit, AnyFloat, Bool
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam, UnexpectedElement
from .actions import store_bool, store_const, ArgAction, change_help_send_action
from .manager import enable_command, disable_command, get_command, get_commands, all_command
from .main import Alconna

alconna_version = (0, 5, 9)

if TYPE_CHECKING:
    from .actions import version
