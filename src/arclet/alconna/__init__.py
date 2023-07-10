"""Alconna 概览"""

from nepattern import AllParam as AllParam, AnyOne as AnyOne  # noqa
from tarina import Empty as Empty # noqa
from .config import config, namespace, Namespace
from .typing import MultiVar, KeyWordVar, Kw, Nargs, CommandMeta
from .args import Args, Field, ArgFlag, Arg
from .base import Option, Subcommand
from .completion import CompSession
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .argv import Argv, set_default_argv_type, argv_config
from .core import Alconna
from .arparma import Arparma, ArparmaBehavior
from .manager import command_manager, ShortcutArgs

from .action import store_value, store_true, store_false, append, count, append_value
from .builtin import set_default
from .model import OptionResult, SubcommandResult, HeadResult
from .output import output_manager
from .formatter import TextFormatter

__version__ = "2.0.0a1"

# backward compatibility
Arpamar = Arparma
DataCollectionContainer = Argv
