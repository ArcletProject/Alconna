"""Alconna 概览"""

from nepattern import AllParam as AllParam, Empty as Empty, AnyOne as AnyOne  # noqa
from .util import split_once, split, LruCache
from .typing import MultiVar, KeyWordVar, Kw, Nargs
from .args import Args, Field, ArgFlag, Arg
from .base import CommandNode, Option, Subcommand
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analyser import compile, analyse
from .container import DataCollectionContainer
from .core import Alconna, CommandMeta
from .arparma import Arparma, ArparmaBehavior
from .manager import command_manager, ShortcutArgs
from .config import config, load_lang_file, namespace, Namespace

from .builtin import store_value, set_default, store_true, store_false
from .output import output_manager
from .formatter import TextFormatter
from .duplication import Duplication
from .stub import ArgsStub, OptionStub, SubcommandStub

__version__ = "1.6.2"

Arpamar = Arparma
