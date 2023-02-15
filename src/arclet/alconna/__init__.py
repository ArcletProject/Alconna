"""Alconna 概览"""

from nepattern import AllParam as AllParam, Empty as Empty, AnyOne as AnyOne  # noqa
from .typing import MultiVar, KeyWordVar, Kw, Nargs
from .args import Args, Field, ArgFlag, Arg
from .base import CommandNode, Option, Subcommand
from .exceptions import ParamsUnmatched, NullMessage, InvalidParam
from .analysis.analyser import compile, analyse
from .analysis.container import DataCollectionContainer
from .core import Alconna, CommandMeta
from .arparma import Arparma
from .config import config, load_lang_file, namespace, Namespace
from .output import output_manager, TextFormatter

__version__ = "1.6.0"

Arpamar = Arparma
