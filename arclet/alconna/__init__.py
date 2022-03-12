"""Alconna 概览"""

from typing import TYPE_CHECKING
from .util import split_once, split
from .base import CommandNode, Args, ArgAction
from .component import Option, Subcommand
from .arpamar import Arpamar
from .types import (
    DataUnit, DataCollection, AnyParam, AllParam, Empty,
    AnyStr, AnyIP, AnyUrl, AnyDigit, AnyFloat, Bool, PatternToken, Email, ObjectPattern,
    add_check
)
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam, UnexpectedElement
from .analysis import compile, analyse, analyse_args, analyse_header, analyse_option, analyse_subcommand
from .main import Alconna
from .manager import command_manager
from .builtin.actions import store_value, require_help_send_action, set_default, exclusion, cool_down
from .builtin.construct import AlconnaDecorate, AlconnaFormat, AlconnaString, AlconnaFire
from .visitor import AlconnaNodeVisitor, AbstractHelpTextFormatter

all_command_help = command_manager.all_command_help
command_broadcast = command_manager.broadcast
delete_command = command_manager.delete
disable_command = command_manager.set_disable
enable_command = command_manager.set_enable
get_command = command_manager.get_command
get_commands = command_manager.get_commands
alconna_version = (0, 7, 5)

if TYPE_CHECKING:
    from .builtin.actions import version
