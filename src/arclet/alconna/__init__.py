"""Alconna 概览"""

from nepattern import AllParam as AllParam, AnyOne as AnyOne  # noqa
from tarina import Empty as Empty # noqa
from .config import config, namespace, Namespace
from .typing import MultiVar, KeyWordVar, Kw, Nargs
from .args import Args, Field, ArgFlag, Arg
from .base import CommandNode, Option, Subcommand
from .completion import CompInterface
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analyser import Analyser
from .container import DataCollectionContainer
from .core import Alconna, CommandMeta
from .arparma import Arparma, ArparmaBehavior
from .manager import command_manager, ShortcutArgs

from .builtin import store_value, set_default, store_true, store_false
from .output import output_manager
from .formatter import TextFormatter
from .duplication import Duplication
from .stub import ArgsStub, OptionStub, SubcommandStub

__version__ = "1.7.0rc2"

Arpamar = Arparma
