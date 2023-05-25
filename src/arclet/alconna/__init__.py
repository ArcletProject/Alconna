"""Alconna 概览"""

from nepattern import AllParam as AllParam, AnyOne as AnyOne  # noqa
from tarina import Empty as Empty # noqa
from .typing import CommandMeta
from .base import Option, ArgFlag, Arg, OptionResult, Arparma, store_true, store_false, store_value, append, append_value, count
from .analysis import Argv, set_default_argv_type, argv_config
from .main import Alconna

__version__ = "0.1.1"

Arpamar = Arparma
DataCollectionContainer = Argv
Slot = Arg
