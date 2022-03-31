import asyncio
from asyncio import AbstractEventLoop
import sys
import re
import inspect
from functools import partial
from types import FunctionType, MethodType, ModuleType
from typing import Dict, Any, Optional, Callable, Union, TypeVar, List, Type, FrozenSet, Literal, get_args, Tuple, \
    Iterable, cast
from arclet.alconna.types import DataCollection
from arclet.alconna.builtin.actions import store_value
from arclet.alconna.main import Alconna
from arclet.alconna.component import Option, Subcommand
from arclet.alconna.base import Args, TAValue, ArgAction
from arclet.alconna.util import split, split_once

PARSER_TYPE = Callable[[Callable, Dict[str, Any], Optional[Dict[str, Any]], Optional[AbstractEventLoop]], Any]


def default_parser(
        func: Callable,
        args: Dict[str, Any],
        local_arg: Optional[Dict[str, Any]],
        loop: Optional[AbstractEventLoop]
) -> Any:
    return func(**{**args, **(local_arg or {})}, loop=loop)


class ALCCommand:
    """
    以 click-like 方法创建的 Alconna 结构体, 可以被视为一类 CommanderHandler
    """
    command: Alconna
    parser_func: PARSER_TYPE
    local_args: Dict[str, Any]
    exec_target: Callable
    loop: AbstractEventLoop

    def __init__(
            self,
            command: Alconna,
            target: Callable,
            loop: AbstractEventLoop,
    ):
        self.command = command
        self.exec_target = target
        self.loop = loop
        self.parser_func = default_parser
        self.local_args = {}

    def set_local_args(self, local_args: Optional[Dict[str, Any]] = None):
        """
        设置本地参数

        Args:
            local_args (Optional[Dict[str, Any]]): 本地参数
        """
        self.local_args = local_args or {}

    def set_parser(self, parser_func: PARSER_TYPE):
        """
        设置解析器

        Args:
            parser_func (PARSER_TYPE): 解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.parser_func = parser_func
        return self

    def __call__(self, message: Union[str, DataCollection]) -> Any:
        if not self.exec_target:
            raise Exception("This must behind a @xxx.command()")
        result = self.command.parse(message)
        if result.matched:
            self.parser_func(self.exec_target, result.all_matched_args, self.local_args, self.loop)

    def from_commandline(self):
        """从命令行解析参数"""
        if not self.command:
            raise Exception("You must call @xxx.command() before @xxx.from_commandline()")
        args = sys.argv[1:]
        args.insert(0, self.command.command)
        self.__call__(" ".join(args))


F = TypeVar("F", bound=Callable[..., Any])
FC = TypeVar("FC", bound=Union[Callable[..., Any], ALCCommand])


# ----------------------------------------
# click-like
# ----------------------------------------


class AlconnaDecorate:
    """
    Alconna Click-like 构造方法的生成器

    Examples:
        >>> cli = AlconnaDecorate()
        >>> @cli.build_command()
        ... @cli.option("--name|-n", Args["name":str:"your name"])
        ... @cli.option("--age|-a", Args["age":int:"your age"])
        ... def hello(name: str, age: int):
        ...     print(f"Hello {name}, you are {age} years old.")
        ...
        >>> hello("hello --name Alice --age 18")

    Attributes:
        namespace (str): 命令的命名空间
        loop (AbstractEventLoop): 事件循环
    """
    namespace: str
    loop: AbstractEventLoop
    building: bool
    __storage: Dict[str, Any]
    default_parser: PARSER_TYPE

    def __init__(
            self,
            namespace: str = "Alconna",
            loop: Optional[AbstractEventLoop] = None,
    ):
        """
        初始化构造器

        Args:
            namespace (str): 命令的命名空间
            loop (AbstractEventLoop): 事件循环
        """
        self.namespace = namespace
        self.building = False
        self.__storage = {"options": []}
        self.loop = loop or asyncio.new_event_loop()
        self.default_parser = default_parser

    def build_command(self, name: Optional[str] = None) -> Callable[[F], ALCCommand]:
        """
        开始构建命令

        Args:
            name (Optional[str]): 命令名称
        """
        self.building = True

        def wrapper(func: Callable[..., Any]) -> ALCCommand:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            command_name = name or self.__storage['func'].__name__
            help_string = self.__storage.get('func').__doc__
            command = Alconna(
                command=command_name,
                options=self.__storage.get("options"),
                namespace=self.namespace,
                main_args=self.__storage.get("main_args"),
                help_text=help_string or command_name
            )
            self.building = False
            return ALCCommand(command, self.__storage['func'], self.loop).set_parser(self.default_parser)

        return wrapper

    def option(
            self,
            name: str,
            args: Optional[Args] = None,
            help: Optional[str] = None,
            action: Optional[Callable] = None,
            sep: str = " "
    ) -> Callable[[FC], FC]:
        """
        添加命令选项

        Args:
            name (str): 选项名称
            args (Optional[Args]): 选项参数
            help (Optional[str]): 选项帮助信息
            action (Optional[Callable]): 选项动作
            sep (str): 参数分隔符
        """
        if not self.building:
            raise Exception("This must behind a @xxx.command()")

        def wrapper(func: FC) -> FC:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            self.__storage['options'].append(
                Option(name, args=args, action=action, separator=sep, help_text=help or name)
            )
            return func

        return wrapper

    def arguments(self, args: Args) -> Callable[[FC], FC]:
        """
        添加命令参数

        Args:
            args (Args): 参数
        """
        if not self.building:
            raise Exception("This must behind a @xxx.command()")

        def wrapper(func: FC) -> FC:
            if not self.__storage.get('func'):
                self.__storage['func'] = func
            self.__storage['main_args'] = args
            return func

        return wrapper

    def set_default_parser(self, parser_func: PARSER_TYPE):
        """
        设置默认的参数解析器

        Args:
            parser_func (PARSER_TYPE): 参数解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.default_parser = parser_func
        return self


# ----------------------------------------
# format
# ----------------------------------------


def _from_format(
        format_string: str,
        format_args: Optional[Dict[str, Union[TAValue, Args, Option, List[Option]]]] = None,
) -> "Alconna":
    """
    以格式化字符串的方式构造 Alconna

    Examples:

    >>> from arclet.alconna import AlconnaFormat
    >>> alc1 = AlconnaFormat(
    ...     "lp user {target} perm set {perm} {default}",
    ...     {"target": str, "perm": str, "default": Args["de":bool:True]},
    ... )
    >>> alc1.parse("lp user AAA perm set admin.all False")
    """
    format_args = format_args or {}
    _key_ref = 0
    strings = split(format_string)
    command = strings.pop(0)
    options = []
    main_args = Args()

    _string_stack: List[str] = []
    for i, string in enumerate(strings):
        if not (arg := re.findall(r"{(.+)}", string)):
            _string_stack.append(string)
            _key_ref = 0
            continue
        _key_ref += 1
        key = arg[0]
        try:
            value = format_args[key]
            try:
                _param = _string_stack.pop(-1)
                if isinstance(value, Option):
                    options.append(Subcommand(_param, [value]))
                elif isinstance(value, List):
                    options.append(Subcommand(_param, value))
                elif _key_ref > 1 and isinstance(options[-1], Option):
                    if isinstance(value, Args):
                        options.append(Subcommand(_param, [options.pop(-1)], args=value))
                    else:
                        options.append(Subcommand(_param, [options.pop(-1)], args=Args(**{key: value})))
                elif isinstance(value, Args):
                    options.append(Option(_param, args=value))
                else:
                    options.append(Option(_param, Args(**{key: value})))
            except IndexError:
                if i == 0:
                    if isinstance(value, Args):
                        main_args.__merge__(value)
                    elif not isinstance(value, Option) and not isinstance(value, List):
                        main_args.__merge__(Args(**{key: value}))
                else:
                    if isinstance(value, Option):
                        options.append(value)
                    elif isinstance(value, Args):
                        options[-1].args = value
                    else:
                        options[-1].args.argument.update({key: value})
                        options[-1].nargs += 1
        except KeyError:
            may_parts = re.split(r"[:|=]", key.replace(" ", ''))
            if len(may_parts) == 1:
                _arg = Args[may_parts[0]:Any]
            else:
                _arg = Args.from_string_list([may_parts], {})
            if _string_stack:
                if _key_ref > 1:
                    options[-1].args.__merge__(_arg)
                    options[-1].nargs += 1
                else:
                    options.append(Option(_string_stack.pop(-1), _arg))
            else:
                main_args.__merge__(_arg)
    alc = Alconna(command=command, options=options, main_args=main_args)
    return alc


# ----------------------------------------
# koishi-like
# ----------------------------------------


def _from_string(
        command: str,
        *option: str,
        custom_types: Optional[Dict[str, Type]] = None,
        sep: str = " "
) -> "Alconna":
    """
    以纯字符串的形式构造Alconna的简易方式, 或者说是koishi-like的方式

    Examples:

    >>> from arclet.alconna import AlconnaString
    >>> alc = AlconnaString(
    ... "test <message:str> #HELP_STRING",
    ... "--foo|-f <val:bool:True>", "--bar [134]"
    ... )
    >>> alc.parse("test abcd --foo True")
    """

    _options = []
    head, others = split_once(command, sep)
    headers = [head]
    if re.match(r"^\[(.+?)]$", head):
        headers = head.strip("[]").split("|")
    args = [re.split("[:|=]", p) for p in re.findall(r"<(.+?)>", others)]
    if not (help_string := re.findall(r"#(.+)", others)):
        help_string = headers
    if not custom_types:
        custom_types = Alconna.custom_types.copy()
    else:
        custom_types.update(Alconna.custom_types)
    custom_types.update(getattr(inspect.getmodule(inspect.stack()[1][0]), "__dict__", {}))
    _args = Args.from_string_list(args, custom_types.copy())
    for opt in option:
        if opt.startswith("--"):
            opt_head, opt_others = split_once(opt, sep)
            opt_args = [re.split("[:|=]", p) for p in re.findall(r"<(.+?)>", opt_others)]
            _opt_args = Args.from_string_list(opt_args, custom_types.copy())
            opt_action_value = re.findall(r"\[(.+?)]$", opt_others)
            if not (opt_help_string := re.findall(r"#(.+)", opt_others)):
                opt_help_string = [opt_head]
            if opt_action_value:
                val = eval(opt_action_value[0], {"true": True, "false": False})
                _options.append(Option(opt_head, args=_opt_args, action=store_value(val)))
            else:
                _options.append(Option(opt_head, args=_opt_args))
            _options[-1].help_text = opt_help_string[0]
    return Alconna(headers=headers, main_args=_args, options=_options, help_text=help_string[0])


config_key = Literal["headers", "raise_exception", "description", "get_subcommand", "extra", "namespace", "command"]


def visit_config(obj: Any, config_keys: Iterable[str]):
    result = {}
    if not isinstance(obj, (FunctionType, MethodType)):
        config = inspect.getmembers(
            obj, predicate=lambda x: inspect.isclass(x) and x.__name__.endswith("Config")
        )
        if config:
            config = config[0][1]
            configs = list(filter(lambda x: not x.startswith("_"), dir(config)))
            for key in config_keys:
                if key in configs:
                    result[key] = getattr(config, key)
    else:
        codes, _ = inspect.getsourcelines(obj)
        _get_config = False
        _start_indent = 0
        for line in codes:
            indent = len(line) - len(line.lstrip())
            if line.lstrip().startswith("class") and line.lstrip().rstrip('\n').endswith("Config:"):
                _get_config = True
                _start_indent = indent
                continue
            if _get_config:
                if indent == _start_indent:
                    break
                if line.lstrip().startswith('def'):
                    continue
                _contents = re.split(r"\s*=\s*", line.strip())
                if len(_contents) == 2 and _contents[0] in config_keys:
                    result[_contents[0]] = eval(_contents[1])
    return result


class AlconnaMounter(Alconna):
    mount_cls: Type
    instance: object
    config_keys: FrozenSet[str] = frozenset(get_args(config_key))

    def _instance_action(self, option_dict, varargs, kwargs):
        if not self.instance:
            self.instance = self.mount_cls(*option_dict.values(), *varargs, **kwargs)
        else:
            for key, value in option_dict.items():
                setattr(self.instance, key, value)
        return option_dict

    def _inject_instance(self, target: Callable):
        return partial(target, self.instance)

    def _get_instance(self):
        return self.instance

    def _parse_action(self, message):
        ...

    def parse(self, message: Union[str, DataCollection], duplication: Optional[Any] = None, static: bool = True):  # noqa
        message = self._parse_action(message) or message
        return super(AlconnaMounter, self).parse(message, duplication=duplication, static=static)


class FuncMounter(AlconnaMounter):

    def __init__(self, func: Union[FunctionType, MethodType], config: Optional[dict] = None):
        config = config or visit_config(func, self.config_keys)
        func_name = func.__name__
        if func_name.startswith("_"):
            raise ValueError("function name can not start with '_'")
        _args, method = Args.from_callable(func, extra=config.get("extra", "ignore"))
        if method and isinstance(func, MethodType):
            self.instance = func.__self__
            func = cast(FunctionType, partial(func, self.instance))
        super(FuncMounter, self).__init__(
            headers=config.get("headers", None),
            command=config.get("command", func_name),
            main_args=_args,
            help_text=config.get("description", func.__doc__ or func_name),
            action=func,
            is_raise_exception=config.get("raise_exception", True),
            namespace=config.get("namespace", None),
        )


def visit_subcommand(obj: Any):
    result = []
    subcommands: List[Tuple[str, Type]] = inspect.getmembers(
        obj, predicate=lambda x: inspect.isclass(x) and not x.__name__.endswith("Config")
    )

    class _MountSubcommand(Subcommand):
        sub_instance: object

    for cls_name, subcommand_cls in subcommands:
        if cls_name.startswith("_"):
            continue
        init = inspect.getfullargspec(subcommand_cls.__init__)
        members = inspect.getmembers(
            subcommand_cls, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        config = visit_config(subcommand_cls, ["command", "description"])
        _options = []
        sub_help_text = subcommand_cls.__doc__ or subcommand_cls.__init__.__doc__ or cls_name

        if len(init.args + init.kwonlyargs) > 1:
            sub_args = Args.from_callable(subcommand_cls.__init__, extra='ignore')[0]
            sub = _MountSubcommand(
                config.get("command", cls_name),
                help_text=config.get("description", sub_help_text),
                args=sub_args
            )
            sub.sub_instance = subcommand_cls

            def _instance_action(option_dict, varargs, kwargs):
                if not sub.sub_instance:
                    sub.sub_instance = subcommand_cls(*option_dict.values(), *varargs, **kwargs)
                else:
                    for key, value in option_dict.items():
                        setattr(sub.sub_instance, key, value)
                return option_dict

            class _InstanceAction(ArgAction):
                def handle(self, option_dict, varargs, kwargs, is_raise_exception):
                    return _instance_action(option_dict, varargs, kwargs)

            class _TargetAction(ArgAction):
                origin: Callable

                def __init__(self, target: Callable):
                    self.origin = target
                    super().__init__(target)

                def handle(self, option_dict, varargs, kwargs, is_raise_exception):
                    self.action = partial(self.origin, sub.sub_instance)
                    return super().handle(option_dict, varargs, kwargs, is_raise_exception)

                async def handle_async(self, option_dict, varargs, kwargs, is_raise_exception):
                    self.action = partial(self.origin, sub.sub_instance)
                    return await super().handle_async(option_dict, varargs, kwargs, is_raise_exception)

            for name, func in members:
                if name.startswith("_"):
                    continue
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func, extra='ignore')
                if method:
                    _options.append(Option(name, args=_opt_args, action=_TargetAction(func), help_text=help_text))
                else:
                    _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
            sub.options = _options
            sub.action = _InstanceAction(lambda: None)
            result.append(sub)
        else:
            sub = _MountSubcommand(config.get("command", cls_name), help_text=config.get("description", sub_help_text))
            sub.sub_instance = subcommand_cls()
            for name, func in members:
                if name.startswith("_"):
                    continue
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func, extra='ignore')
                if method:
                    func = partial(func, sub.sub_instance)
                _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
            sub.options = _options
            result.append(sub)
    return result


class ClassMounter(AlconnaMounter):

    def __init__(self, mount_cls: Type, config: Optional[dict] = None):
        self.mount_cls = mount_cls
        self.instance: mount_cls = None
        config = config or visit_config(mount_cls, self.config_keys)
        init = inspect.getfullargspec(mount_cls.__init__)
        members = inspect.getmembers(
            mount_cls, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        _options = []
        if config.get('get_subcommand', False):
            subcommands = visit_subcommand(mount_cls)
            _options.extend(subcommands)
        main_help_text = mount_cls.__doc__ or mount_cls.__init__.__doc__ or mount_cls.__name__

        if len(init.args + init.kwonlyargs) > 1:
            main_args = Args.from_callable(mount_cls.__init__, extra=config.get("extra", "ignore"))[0]

            instance_handle = self._instance_action

            class _InstanceAction(ArgAction):
                def handle(self, option_dict, varargs, kwargs, is_raise_exception):
                    return instance_handle(option_dict, varargs, kwargs)

            inject = self._inject_instance

            class _TargetAction(ArgAction):
                origin: Callable

                def __init__(self, target: Callable):
                    self.origin = target
                    super().__init__(target)

                def handle(self, option_dict, varargs, kwargs, is_raise_exception):
                    self.action = inject(self.origin)
                    return super().handle(option_dict, varargs, kwargs, is_raise_exception)

                async def handle_async(self, option_dict, varargs, kwargs, is_raise_exception):
                    self.action = inject(self.origin)
                    return await super().handle_async(option_dict, varargs, kwargs, is_raise_exception)

            main_action = _InstanceAction(lambda: None)
            for name, func in members:
                if name.startswith("_"):
                    continue
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func, extra=config.get("extra", "ignore"))
                if method:
                    _options.append(Option(name, args=_opt_args, action=_TargetAction(func), help_text=help_text))
                else:
                    _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
            super().__init__(
                headers=config.get('headers', None),
                namespace=config.get('namespace', None),
                command=config.get('command', mount_cls.__name__),
                main_args=main_args,
                options=_options,
                help_text=config.get('description', main_help_text),
                is_raise_exception=config.get('raise_exception', True),
                action=main_action,
            )
        else:
            self.instance = mount_cls()
            for name, func in members:
                if name.startswith("_"):
                    continue
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func, extra=config.get("extra", "ignore"))
                if method:
                    func = partial(func, self.instance)
                _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
            super().__init__(
                headers=config.get('headers', None),
                namespace=config.get('namespace', None),
                command=config.get('command', mount_cls.__name__),
                options=_options,
                help_text=config.get('description', main_help_text),
                is_raise_exception=config.get('raise_exception', True),
            )

    def _parse_action(self, message):
        if self.instance:
            for k, a in self.args.argument.items():
                if hasattr(self.instance, k):
                    a['default'] = getattr(self.instance, k)


class ModuleMounter(AlconnaMounter):

    def __init__(self, module: ModuleType, config: Optional[dict] = None):
        self.mount_cls = module.__class__
        self.instance = module
        config = config or visit_config(module, self.config_keys)
        _options = []
        members = inspect.getmembers(
            module, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        for name, func in members:
            if name.startswith("_") or func.__name__.startswith("_"):
                continue
            help_text = func.__doc__ or name
            _opt_args, method = Args.from_callable(func, extra=config.get("extra", "ignore"))
            if method:
                func = partial(func, func.__self__)
            _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
        super().__init__(
            headers=config.get('headers', None),
            namespace=config.get('namespace', None),
            command=config.get('command', module.__name__),
            options=_options,
            help_text=config.get("description", module.__doc__ or module.__name__),
            is_raise_exception=config.get("raise_exception", True)
        )

    def _parse_action(self, message):
        if self.command.startswith("_"):
            if isinstance(message, str):
                message = self.command + " " + message
            else:
                message.inject(0, self.command)
        return message


class ObjectMounter(AlconnaMounter):

    def __init__(self, obj: object, config: Optional[dict] = None):
        self.mount_cls = type(obj)
        self.instance = obj
        config = config or visit_config(obj, self.config_keys)
        obj_name = obj.__class__.__name__
        init = inspect.getfullargspec(obj.__init__)
        members = inspect.getmembers(
            obj, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        _options = []
        if config.get('get_subcommand', False):
            subcommands = visit_subcommand(obj)
            _options.extend(subcommands)
        main_help_text = obj.__doc__ or obj.__init__.__doc__ or obj_name
        for name, func in members:
            if name.startswith("_"):
                continue
            help_text = func.__doc__ or name
            _opt_args, _ = Args.from_callable(func, extra=config.get("extra", "ignore"))
            _options.append(Option(name, args=_opt_args, action=ArgAction(func), help_text=help_text))
        if len(init.args) > 1:
            main_args = Args.from_callable(obj.__init__, extra=config.get("extra", "ignore"))[0]
            for k, a in main_args.argument.items():
                if hasattr(self.instance, k):
                    a['default'] = getattr(self.instance, k)

            instance_handle = self._instance_action

            class _InstanceAction(ArgAction):

                def handle(self, option_dict, varargs, kwargs, is_raise_exception: bool):
                    return instance_handle(option_dict, varargs, kwargs)

            main_action = _InstanceAction(lambda: None)
            super().__init__(
                headers=config.get('headers', None),
                command=config.get('command', obj_name),
                main_args=main_args,
                options=_options,
                help_text=config.get("description", main_help_text),
                is_raise_exception=config.get("raise_exception", True),
                action=main_action,
                namespace=config.get('namespace', None)
            )
        else:
            super().__init__(
                headers=config.get('headers', None),
                command=config.get('command', obj_name),
                options=_options,
                namespace=config.get('namespace', None),
                help_text=config.get("description", main_help_text),
                is_raise_exception=config.get("raise_exception", True),
            )


def _from_object(
        target: Optional[Union[Type, object, FunctionType, MethodType, ModuleType]] = None,
        command: Optional[str] = None,
        config: Optional[Dict[config_key, Any]] = None,
) -> AlconnaMounter:
    """
    通过解析传入的对象，生成 Alconna 实例的方法, 或者说是Fire-like的方式

    Examples:

    >>> from arclet.alconna import AlconnaFire
    >>> def test_func(a, b, c):
    ...     print(a, b, c)
    ...
    >>> alc = AlconnaFire(test_func)
    >>> alc.parse("test_func 1 2 3")
    """
    if inspect.isfunction(target) or inspect.ismethod(target):
        r = FuncMounter(target, config)
    elif inspect.isclass(target):
        r = ClassMounter(target, config)
    elif inspect.ismodule(target):
        r = ModuleMounter(target, config)
    else:
        if target:
            r = ObjectMounter(target, config)
        else:
            r = ModuleMounter(inspect.getmodule(inspect.stack()[1][0]) or sys.modules["__main__"], config)
    command = command or (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else None)
    if command:
        r.parse(command)
    return r


AlconnaFormat = _from_format
AlconnaString = _from_string
AlconnaFire = _from_object
