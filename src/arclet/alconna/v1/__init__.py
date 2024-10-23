"""Alconna 概览"""

from nepattern import ANY as ANY  # noqa
from tarina import Empty as Empty  # noqa

from arclet.alconna.action import append as append  # noqa: F401
from arclet.alconna.action import append_value as append_value  # noqa: F401
from arclet.alconna.action import count as count  # noqa: F401
from arclet.alconna.action import store_false as store_false  # noqa: F401
from arclet.alconna.action import store_true as store_true  # noqa: F401
from arclet.alconna.action import store_value as store_value  # noqa: F401
from arclet.alconna.args import Arg as Arg  # noqa: F401
# from arclet.alconna.args import ArgFlag as ArgFlag  # noqa: F401
from arclet.alconna.args import Args as Args  # noqa: F401
from arclet.alconna.args import Field as Field  # noqa: F401
from arclet.alconna.ingedia._argv import Argv as Argv  # noqa: F401
from arclet.alconna.ingedia._argv import argv_config as argv_config  # noqa: F401
from arclet.alconna.ingedia._argv import set_default_argv_type as set_default_argv_type  # noqa: F401
from arclet.alconna.arparma import Arparma as Arparma  # noqa: F401
from arclet.alconna.arparma import ArparmaBehavior as ArparmaBehavior  # noqa: F401
from arclet.alconna.base import Option as Option  # noqa: F401
from arclet.alconna.base import Subcommand as Subcommand  # noqa: F401
from arclet.alconna.base import HeadResult as HeadResult  # noqa: F401
from arclet.alconna.base import OptionResult as OptionResult  # noqa: F401
from arclet.alconna.base import SubcommandResult as SubcommandResult  # noqa: F401
from arclet.alconna.builtin import conflict as conflict  # noqa: F401
from arclet.alconna.builtin import set_default as set_default  # noqa: F401
from arclet.alconna.completion import CompSession as CompSession  # noqa: F401
from arclet.alconna.config import global_config as config  # noqa: F401
from arclet.alconna.core import Alconna as Alconna  # noqa: F401
from arclet.alconna.exceptions import AlconnaException as AlconnaException  # noqa: F401
from arclet.alconna.exceptions import InvalidArgs as InvalidArgs  # noqa: F401
from arclet.alconna.exceptions import InvalidParam as InvalidParam  # noqa: F401
from arclet.alconna.exceptions import NullMessage as NullMessage  # noqa: F401
from arclet.alconna.exceptions import ParamsUnmatched as ParamsUnmatched  # noqa: F401
from arclet.alconna.formatter import TextFormatter as TextFormatter  # noqa: F401
from arclet.alconna.manager import ShortcutArgs as ShortcutArgs  # noqa: F401
from arclet.alconna.manager import command_manager as command_manager  # noqa: F401
from arclet.alconna.typing import AllParam as AllParam  # noqa: F401
# from arclet.alconna.typing import KeyWordVar as KeyWordVar  # noqa: F401
# from arclet.alconna.typing import Kw as Kw  # noqa: F401
from arclet.alconna.typing import MultiVar as MultiVar  # noqa: F401
from arclet.alconna.typing import Nargs as Nargs  # noqa: F401
from arclet.alconna.typing import StrMulti as StrMulti  # noqa: F401
# from arclet.alconna.typing import UnpackVar as UnpackVar  # noqa: F401
# from arclet.alconna.typing import Up as Up  # noqa: F401

from .compat import CommandMeta as CommandMeta
from .compat import Namespace as Namespace
from .compat import namespace as namespace

from .duplication import Duplication as Duplication
from .duplication import generate_duplication as generate_duplication
from .stub import ArgsStub as ArgsStub
from .stub import OptionStub as OptionStub
from .stub import SubcommandStub as SubcommandStub
