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
from .args import ArgFlag as ArgFlag
from .args import Args as Args
from .args import Field as Field
from .argv import Argv as Argv
from .argv import argv_config as argv_config
from .argv import set_default_argv_type as set_default_argv_type
from .arparma import Arparma as Arparma
from .arparma import ArparmaBehavior as ArparmaBehavior
from .base import Option as Option
from .base import Subcommand as Subcommand
from .builtin import set_default as set_default
from .completion import CompSession as CompSession
from .config import Namespace as Namespace
from .config import config as config
from .config import namespace as namespace
from .core import Alconna as Alconna
from .duplication import Duplication as Duplication
from .exceptions import AlconnaException as AlconnaException
from .exceptions import InvalidArgs as InvalidArgs
from .exceptions import InvalidParam as InvalidParam
from .exceptions import NullMessage as NullMessage
from .exceptions import ParamsUnmatched as ParamsUnmatched
from .formatter import TextFormatter as TextFormatter
from .manager import ShortcutArgs as ShortcutArgs
from .manager import command_manager as command_manager
from .model import HeadResult as HeadResult
from .model import OptionResult as OptionResult
from .model import SubcommandResult as SubcommandResult
from .output import output_manager as output_manager
from .stub import ArgsStub as ArgsStub
from .stub import OptionStub as OptionStub
from .stub import SubcommandStub as SubcommandStub
from .typing import AllParam as AllParam
from .typing import CommandMeta as CommandMeta
from .typing import KeyWordVar as KeyWordVar
from .typing import Kw as Kw
from .typing import MultiVar as MultiVar
from .typing import Nargs as Nargs
from .typing import UnpackVar as UnpackVar
from .typing import Up as Up

__version__ = "1.8.12"

# backward compatibility
AnyOne = ANY
