"""Alconna 概览"""

from typing import TYPE_CHECKING
from .util import split_once, split, set_chain_texts, set_black_elements, set_white_elements
from .base import TemplateCommand, Args
from .component import Option, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, AnyParam, AllParam, Empty, \
    AnyStr, AnyIP, AnyUrl, AnyDigit, AnyFloat, Bool, PatternToken
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam, UnexpectedElement
from .actions import store_bool, store_const, ArgAction, change_help_send_action
from .main import Alconna
from .manager import command_manager

delete_command = command_manager.delete
disable_command = command_manager.set_disable
enable_command = command_manager.set_enable
get_command = command_manager.get_command
get_commands = command_manager.get_commands
all_command = command_manager.commands
alconna_version = (0, 6, 1)

if TYPE_CHECKING:
    from .actions import version
