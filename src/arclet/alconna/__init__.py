"""Alconna 概览"""

from nepattern import ANY as ANY  # noqa
from tarina import Empty as Empty  # noqa

from .action import append as append
from .action import append_value as append_value
from .action import count as count
from .action import store_false as store_false
from .action import store_true as store_true
from .action import store_value as store_value
from .args import Arg as Arg
from .args import ArgsBase as ArgsBase
from .args import Args as Args
from .args import arg_field as arg_field
from .args import Field as Field
from .arparma import Arparma as Arparma
from .arparma import ArparmaBehavior as ArparmaBehavior
from .base import Option as Option
from .base import Subcommand as Subcommand
from .base import Metadata as Metadata
from .base import Config as Config
from .base import HeadResult as HeadResult
from .base import OptionResult as OptionResult
from .base import SubcommandResult as SubcommandResult
from .builtin import conflict as conflict
from .builtin import set_default as set_default
from .completion import CompSession as CompSession
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
from .manager import ShortcutArgs as ShortcutArgs
from .manager import command_manager as command_manager
from .typing import AllParam as AllParam

__version__ = "1.8.31"

# backward compatibility
AnyOne = ANY
