"""Alconna 概览"""

from nepattern import AllParam as AllParam, AnyOne as AnyOne  # noqa
from tarina import Empty as Empty # noqa
from .typing import CommandMeta
from .base import Option, Subcommand, Args, Field, ArgFlag, Arg, OptionResult, SubcommandResult, Arparma
from .analysis import Argv, set_default_argv_type, argv_config
from .main import Alconna

__version__ = "1.7.6"

Arpamar = Arparma
DataCollectionContainer = Argv
