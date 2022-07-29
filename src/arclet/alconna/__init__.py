"""Alconna 概览"""

from typing import TYPE_CHECKING

from .util import split_once, split, LruCache, Singleton
from .base import CommandNode, Args, Option, Subcommand
from .typing import DataCollection, AnyOne, AllParam, Empty, PatternModel, set_converter, Bind, BasePattern
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analysis.base import compile, analyse
from .core import Alconna
from .arpamar import Arpamar
from .manager import command_manager
from .config import config, load_lang_file

from .builtin.actions import store_value, set_default, exclusion, cool_down
from .builtin.construct import AlconnaDecorate, AlconnaFormat, AlconnaString, AlconnaFire, Argument, delegate
from .builtin.formatter import ArgParserTextFormatter, DefaultTextFormatter
from .builtin.pattern import ObjectPattern
from .components.behavior import ArpamarBehavior
from .components.output import output_manager, AbstractTextFormatter
from .components.duplication import Duplication
from .components.stub import ArgsStub, OptionStub, SubcommandStub

alconna_version = (1, 1, 2)

if TYPE_CHECKING:
    from .builtin.actions import version
