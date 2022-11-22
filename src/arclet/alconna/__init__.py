"""Alconna 概览"""

from typing import TYPE_CHECKING
from nepattern import AllParam as AllParam, Empty as Empty, AnyOne as AnyOne  # noqa
from .util import split_once, split, LruCache, Singleton
from .args import Args, ArgField, ArgFlag
from .base import CommandNode, Option, Subcommand
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analysis.base import compile, analyse
from .core import Alconna, AlconnaGroup, CommandMeta
from .arpamar import Arpamar
from .manager import command_manager
from .config import config, load_lang_file, namespace, Namespace

from .builtin import store_value, set_default
from .components.behavior import ArpamarBehavior
from .components.output import output_manager, TextFormatter
from .components.duplication import Duplication
from .components.stub import ArgsStub, OptionStub, SubcommandStub

alconna_version = (1, 3, 2)

if TYPE_CHECKING:
    from .builtin import version
