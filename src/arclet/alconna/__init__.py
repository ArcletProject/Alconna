"""Alconna 概览"""

from typing import TYPE_CHECKING
from nepattern import AllParam as AllParam, Empty as Empty, AnyOne as AnyOne  # noqa
from .util import split_once, split, LruCache, Singleton
from .typing import MultiVar, KeyWordVar, Kw, Nargs
from .args import Args, Field, ArgFlag, Arg
from .base import CommandNode, Option, Subcommand
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analysis.base import compile, analyse
from .core import Alconna, AlconnaGroup, CommandMeta
from .arparma import Arparma
from .manager import command_manager, ShortcutArgs
from .config import config, load_lang_file, namespace, Namespace

from .builtin import store_value, set_default, store_true, store_false
from .components.behavior import ArparmaBehavior
from .components.output import output_manager, TextFormatter
from .components.duplication import Duplication
from .components.stub import ArgsStub, OptionStub, SubcommandStub

__version__ = "1.6.0"

if TYPE_CHECKING:
    from .builtin import version

Arpamar = Arparma
