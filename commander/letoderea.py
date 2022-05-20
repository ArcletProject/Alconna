from typing import List, Callable, Dict, Union, Type, Any
from arclet.letoderea.utils import argument_analysis
from arclet.letoderea.handler import await_exec_target
from arclet.alconna import Alconna, Arpamar, Default
from arclet.alconna.types import AnyStr, Bool


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
            params = argument_analysis(func)
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
            index, args = default.position, default.convert()
            result_dict[str(index)] = args
            reflect_map[str(index)] = name
        return result_dict, reflect_map, option_list

    def post_message(self, msg):
        for command in self.command_list:
            if args := command.exec(msg):
                self.broadcast.loop.create_task(await_exec_target(command.callable_func, args))

