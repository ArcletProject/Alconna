"""Alconna 概览"""

from typing import TYPE_CHECKING

from .util import split_once, split, LruCache, Singleton
from .base import CommandNode, Args, Option, Subcommand
from .typing import (
    DataUnit, DataCollection, AnyOne, AllParam, Empty, PatternModel, ObjectPattern,
    set_converter, pattern_gen
)
from .exceptions import ParamsUnmatched, NullTextMessage, InvalidParam
from .analysis.base import compile, analyse
from .core import Alconna
from .arpamar import Arpamar
from .manager import command_manager
from .lang import load_lang_file, lang_config

from .builtin.actions import store_value, set_default, exclusion, cool_down
from .builtin.construct import AlconnaDecorate, AlconnaFormat, AlconnaString, AlconnaFire, Argument
from .builtin.formatter import ArgParserTextFormatter, DefaultTextFormatter
from .components.visitor import AlconnaNodeVisitor
from .components.output import output_send, output_manager, AbstractTextFormatter
from .components.duplication import AlconnaDuplication
from .components.stub import ArgsStub, OptionStub, SubcommandStub

alconna_version = (0, 9, 3)

if TYPE_CHECKING:
    from .builtin.actions import version
