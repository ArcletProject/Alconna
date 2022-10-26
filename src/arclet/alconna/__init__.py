"""Alconna 概览"""

from typing import TYPE_CHECKING
from nepattern import AllParam as AllParam, Empty as Empty, AnyOne as AnyOne  # noqa
from .util import split_once, split
from .args import Args, ArgField, ArgFlag
from .base import CommandNode, Option, Subcommand
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analysis.analyser import compile, analyse
from .core import Alconna, CommandMeta
from .arpamar import Arpamar
from .config import config, load_lang_file, namespace, Namespace

from .builtin import store_value
from .output import output_manager, TextFormatter

alconna_version = (1, 4, 0)

if TYPE_CHECKING:
    from .builtin import version
