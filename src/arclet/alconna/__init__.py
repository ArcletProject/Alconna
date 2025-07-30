"""Alconna 概览"""

from nepattern import ANY as ANY  # noqa
from tarina import Empty as Empty  # noqa

from .receiver import append as append
from .receiver import append_value as append_value
from .receiver import count as count
from .receiver import store_false as store_false
from .receiver import store_true as store_true
from .receiver import store_value as store_value
from .base import Arg as Arg
from .base import ArgsBase as ArgsBase
from .base import Args as Args
from .base import arg_field as arg_field
from .base import Field as Field
from .base import Slot as Slot
from .arparma import Arparma as Arparma
from .arparma import ArparmaBehavior as ArparmaBehavior
from .base import Subcommand as Subcommand
from .base import Metadata as Metadata
from .base import Config as Config
from .builtin import conflict as conflict
from .builtin import set_default as set_default
from .ingedia._completion import CompSession as CompSession  # FIXME
from .config import Namespace as Namespace
from .config import global_config as global_config
from .config import namespace as namespace
from .core import Alconna as Alconna
from .exceptions import AlconnaException as AlconnaException
from .exceptions import InvalidArgs as InvalidArgs
from .exceptions import InvalidParam as InvalidParam
from .exceptions import NullMessage as NullMessage
from .exceptions import ParamsUnmatched as ParamsUnmatched
from .formatter import TextFormatter as TextFormatter
from .shortcut import ShortcutArgs as ShortcutArgs
from .manager import command_manager as command_manager

__version__ = "1.8.38"
