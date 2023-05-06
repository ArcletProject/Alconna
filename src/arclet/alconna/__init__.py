"""Alconna 概览"""

from nepattern import AllParam as AllParam, AnyOne as AnyOne  # noqa
from tarina import Empty as Empty # noqa
from .config import config, namespace, Namespace
from .typing import MultiVar, KeyWordVar, Kw, Nargs
from .args import Args, Field, ArgFlag, Arg
from .base import Option, Subcommand
from .completion import CompSession
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .argv import Argv, set_default_argv_type, argv_config
from .core import Alconna, CommandMeta
from .arparma import Arparma, ArparmaBehavior
from .manager import command_manager, ShortcutArgs

from .action import store_value, store_true, store_false, append, count, append_value
from .builtin import set_default
from .output import output_manager
from .formatter import TextFormatter
from .duplication import Duplication
from .stub import ArgsStub, OptionStub, SubcommandStub

__version__ = "1.7.0"

Arpamar = Arparma
