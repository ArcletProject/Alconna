from typing import List, Callable, Dict, Union, Type, Any
import re
from arclet.alconna import Alconna, Arpamar, Default, Option
from arclet.alconna.types import AnyStr, Bool
from arclet.alconna.util import split_once
from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.interfaces.decorator import DecoratorInterface
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import argument_signature


class Positional:

    def __init__(
            self,
            position: Union[str, int],
            *,
            type: Type = str,
            default: Any = None
    ):
        self.position = position
        self.type = type
        self.default = default

    def convert(self):
        alc_type = Bool if self.type == bool else AnyStr
        if not self.default:
            return alc_type
        return Default(alc_type, self.default)


class AdditionParam(Decorator):
    pre = True

    def __init__(
            self,
            params: List[str],
            *,
            type: Type = str,
            default: Any = None,
            return_pos: Union[str, int] = None
    ):
        self.params = params
        self.type = type
        self.default = default
        self.return_pos = return_pos

    def convert(self, key: str):
        opt_list = []
        alc_type = Bool if self.type == bool else AnyStr
        for param in self.params:
            if re.match(r"^.+{(.+)}", param):
                if self.default:
                    opt_list.append(Option(split_once(param, " ")[0], **{key: Default(alc_type, self.default)}))
                else:
                    opt_list.append(Option(split_once(param, " ")[0], **{key: alc_type}))
            else:
                opt_list.append(Option(param))
        return opt_list

    async def target(self, interface: DecoratorInterface):
        if interface.name in interface.local_storage:
            return interface.local_storage.get(interface.name)
        elif self.default is not None:
            return self.default


class BaseCommand:
    name: str
    alconna: Alconna
    callable_func: Callable
    result: Arpamar

    def __init__(self, alc: Alconna, func: Callable):
        self.alconna = alc
        self.name = alc.command
        self.callable_func = func

    def __repr__(self):
        return f'<Command,name={self.name}>'

    def __eq__(self, other: "BaseCommand"):
        return self.alconna == other.alconna

    def exec(self, msg: str) -> Dict:
        self.result = self.alconna.analyse_message(msg)
        return self.result.option_args


class AlconnaCommander:
    command_list: List[BaseCommand]

    def __init__(self, broadcast):
        self.broadcast = broadcast
        self.command_list = []

    def command(self, format_string: str):
        def wrapper(func):
            params = argument_signature(func)
            format_args, reflect_map, option_list = self.param_handler(params)
            bc = BaseCommand(Alconna.format(format_string, format_args, reflect_map), func)
            if option_list:
                bc.alconna.add_options(option_list)
            self.command_list.append(bc)
            return func

        return wrapper

    @staticmethod
    def param_handler(param):
        result_dict = {}
        reflect_map = {}
        option_list = []
        for name, _, default in param:
            if isinstance(default, Positional):
                index, args = default.position, default.convert()
                result_dict[str(index)] = args
                reflect_map[str(index)] = name
            elif isinstance(default, AdditionParam):
                option_list.extend(default.convert(name))
        return result_dict, reflect_map, option_list

    @staticmethod
    def dispatcher_generator(opt_args):
        class _Dispatcher(BaseDispatcher):
            async def catch(self, interface: DispatcherInterface):
                interface.execution_contexts[-1].local_storage = opt_args
                if interface.name in opt_args:
                    return opt_args.get(interface.name)

        return _Dispatcher()

    def post_message(self, msg):
        for command in self.command_list:
            if args := command.exec(msg):
                self.broadcast.loop.create_task(
                    self.broadcast.Executor(
                        command.callable_func,
                        dispatchers=[self.dispatcher_generator(args)]
                    )
                )
