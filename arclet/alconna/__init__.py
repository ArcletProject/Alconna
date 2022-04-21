"""Alconna 概览"""

from typing import TYPE_CHECKING
from .util import split_once, split
from .base import CommandNode, Args, ArgAction, Option, Subcommand
from .arpamar import Arpamar
from .arpamar.duplication import AlconnaDuplication
from .arpamar.stub import ArgsStub, SubcommandStub, OptionStub
from .types import (
    DataUnit, DataCollection, AnyParam, AllParam, Empty, PatternToken, ObjectPattern,
    set_converter, pattern
)
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam, UnexpectedElement
from .analysis import compile, analyse, analyse_args, analyse_header, analyse_option, analyse_subcommand
from .main import Alconna
from .manager import command_manager
from .builtin.actions import store_value, help_send, help_manager, set_default, exclusion, cool_down
from .builtin.construct import AlconnaDecorate, AlconnaFormat, AlconnaString, AlconnaFire, delegate
from .builtin.formatter import ArgParserHelpTextFormatter, DefaultHelpTextFormatter
from .visitor import AlconnaNodeVisitor, AbstractHelpTextFormatter
from .lang_config import load_config_file, lang_config


all_command_help = command_manager.all_command_help
command_broadcast = command_manager.broadcast
delete_command = command_manager.delete
disable_command = command_manager.set_disable
enable_command = command_manager.set_enable
get_command = command_manager.get_command
get_commands = command_manager.get_commands
alconna_version = (0, 8, 3)

if TYPE_CHECKING:
    from .builtin.actions import version
