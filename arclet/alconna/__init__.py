from typing import Dict, List, Optional, Union, Any, overload
import re
from .util import split_once, split
from .component import Option, CommandInterface, Subcommand, Default, Arpamar, Options_T, Argument_T
from .types import NonTextElement, MessageChain
from .exceptions import ParamsUnmatched, NullName, InvalidOptionName, InvalidFormatMap

_builtin_option = Option("-help")


class Alconna(CommandInterface):
    """
    亚尔康娜（Alconna），Cesloi的妹妹

    用于更加奇怪(大雾)精确的命令解析，支持String与MessageChain

    样例：Alconna(
        headers=[""],
        command="name",
        options=[
            Subcommand("sub_name",Option("sub-opt", sub_arg=sub_arg), args=sub_main_arg),
            Option("opt", arg=arg)
            ]
        main_argument=main_argument
        )

    其中
        - name: 命令名称
        - sub_name: 子命令名称
        - sub-opt: 子命令选项名称
        - sub_arg: 子命令选项参数
        - sub_main_arg: 子命令主参数
        - opt: 命令选项名称
        - arg: 命令选项参数

    Args:
        headers: 呼叫该命令的命令头，一般是你的机器人的名字或者符号，与 command 至少有一个填写
        command: 命令名称，你的命令的名字，与 headers 至少有一个填写
        options: 命令选项，你的命令可选择的所有 option ，包括子命令与单独的选项
        main_argument: 主参数，填入后当且仅当命令中含有该参数时才会成功解析
    """

    name = "Alconna"
    headers: List[str]
    command: str
    options: Options_T
    main_argument: Argument_T

    def __init__(
            self,
            headers: Optional[List[str]] = None,
            command: Optional[str] = None,
            separator: Optional[str] = None,
            options: Optional[Options_T] = None,
            main_argument: Optional[Argument_T] = None,
            exception_in_time: bool = False
    ):
        # headers与command二者必须有其一
        if all([all([not headers, not command]), not options, not main_argument]):
            raise NullName
        super().__init__(
            headers=headers or [""],
            command=command or "",
            separator=separator or " ",
            options=options or [],
            main_argument=main_argument or "",
        )
        self.exception_in_time = exception_in_time
        self.options.append(_builtin_option)
        self._initialise_arguments()

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: List[Union[Argument_T, Option, Dict[str, Union[Argument_T, List[Option]]]]],
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        ...

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: Dict[str, Union[Argument_T, Option, Dict[str, Union[Argument_T, List[Option]]]]],
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        ...

    @classmethod
    def format(
            cls,
            format_string: str,
            format_args: ...,
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        strings = split(format_string)
        command = strings.pop(0)
        options = []
        main_argument = None

        _string_stack: List[str] = list()
        for i in range(len(strings)):
            if not (arg := re.findall(r"{(.+)}", strings[i])):
                _string_stack.append(strings[i])
                continue

            key = arg[0] if not reflect_map else (reflect_map[arg[0]] if reflect_map.get(arg[0]) else arg[0])

            if isinstance(format_args, List) and arg[0].isdigit():
                value = format_args[int(arg[0])]
            elif isinstance(format_args, Dict):
                value = format_args[arg[0]]
            else:
                raise InvalidFormatMap

            stack_count = len(_string_stack)

            if stack_count == 2:
                sub_name, opt_name = _string_stack
                if isinstance(value, Dict):
                    if "args" in value:
                        options.append(Subcommand(sub_name, Option(opt_name, **value['args'])))
                    else:
                        options.append(Subcommand(sub_name, Option(opt_name, **value)))
                else:
                    options.append(Subcommand(sub_name, Option(opt_name, **{key: value})))
                _string_stack.clear()

            if stack_count == 1:
                may_name = _string_stack.pop(0)
                if isinstance(value, Dict):
                    if "Options" in value:
                        options.append(Subcommand(may_name, *value['Options'], **(value.get('args') or {})))
                    elif "name" in value:
                        options.append(Subcommand(may_name, Option.parse_obj(value)))
                    elif "args" in value:
                        options.append(Option(may_name, **value['args']))
                    else:
                        options.append(Option(may_name, **value))
                elif isinstance(value, List):
                    options.append(Subcommand(may_name, *value))
                else:
                    options.append(Option(may_name, **{key: value}))

            if stack_count == 0:
                if i == 0:
                    if isinstance(main_argument, Dict) and value.get("main_argument"):
                        main_argument = value["main_argument"]
                    else:
                        main_argument = value
                else:
                    if isinstance(value, Dict):
                        if value.get("main_argument"):
                            main_argument = value["main_argument"]
                        elif "name" in value:
                            options.append(Option.parse_obj(value))
                        elif "args" in value:
                            options[-1].args.update(value.get('args'))
                    elif isinstance(value, List):
                        options[-1].Options.extend(value)
                    elif isinstance(value, Option):
                        options.append(value)
                    else:
                        options[-1].args.update({key: value})

        alc = cls(command=command, options=options, main_argument=main_argument)
        return alc

    def add_options(self, options: Options_T):
        self.options.extend(options)
        self._initialise_arguments()

    def _initialise_arguments(self):
        # params是除开命令头的剩下部分
        self._params: Dict[str, Union[Argument_T, Dict[str, Any]]] = {"main_argument": self.main_argument}
        for opts in self.dict()['options']:
            if opts['type'] == "SBC":
                opts.setdefault('sub_params', {"sub_args": opts['args']})
                for sub_opts in opts['Options']:
                    opts['sub_params'][sub_opts['name']] = sub_opts
            self._params[opts['name']] = opts

        self._command_headers: List[str] = []  # 依据headers与command生成一个列表，其中含有所有的命令头
        if self.headers != [""]:
            for i in self.headers:
                self._command_headers.append(i + self.command)
        elif self.command:
            self._command_headers.append(self.command)

    def _analyse_args(
            self,
            opt_args: Dict[str, Argument_T],
            may_args: str,
            sep: str,
            rest_text: str
    ) -> Dict[str, Any]:

        _option_dict: Dict[str, Any] = {}
        for k, v in opt_args.items():
            if isinstance(v, Default):
                arg = v.args
                if isinstance(arg, str):
                    if sep != self.separator:
                        may_arg, may_args = split_once(may_args, sep)
                    else:
                        may_arg, rest_text = self.result.split_by(sep)
                    if not (_arg_find := re.findall('^' + arg + '$', may_arg)):
                        if v.default is not None:
                            _arg_find = [v.default]
                        else:
                            raise ParamsUnmatched
                    elif sep == self.separator:
                        self.result.raw_texts[self.result.current_index][0] = rest_text
                    if _arg_find[0] == arg:
                        _arg_find[0] = Ellipsis
                    _option_dict[k] = _arg_find[0]

                else:
                    may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
                    if type(self.result.elements[may_element_index]) is arg:
                        _option_dict[k] = self.result.elements.pop(may_element_index)
                    elif v.default is not None:
                        _option_dict[k] = v.default
                    else:
                        raise ParamsUnmatched

            elif isinstance(v, str):
                if sep != self.separator:
                    may_arg, may_args = split_once(may_args, sep)
                else:
                    may_arg, rest_text = self.result.split_by(sep)
                if not (_arg_find := re.findall('^' + v + '$', may_arg)):
                    raise ParamsUnmatched
                if _arg_find[0] == v:
                    may_arg = Ellipsis
                _option_dict[k] = may_arg
                if sep == self.separator:
                    self.result.raw_texts[self.result.current_index][0] = rest_text
            else:
                may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
                if type(self.result.elements[may_element_index]) is not v:
                    raise ParamsUnmatched
                _option_dict[k] = self.result.elements.pop(may_element_index)
        return _option_dict

    def _analyse_option(
            self,
            param: Dict[str, Union[str, Dict[str, Argument_T]]],
            text: str,
            rest_text: str
    ) -> Dict[str, Any]:

        opt: str = param['name']
        arg: Dict[str, Argument_T] = param['args']
        sep: str = param['separator']
        name, may_args = split_once(text, sep)
        if sep == self.separator:  # 在sep等于separator的情况下name是被提前切出来的
            name = text
        if not re.match('^' + opt + '$', name):  # 先匹配选项名称
            raise ParamsUnmatched
        self.result.raw_texts[self.result.current_index][0] = rest_text
        name = name.lstrip("-")
        if not arg:
            return {name: Ellipsis}
        return {name: self._analyse_args(arg, may_args, sep, rest_text)}

    def _analyse_subcommand(
            self,
            param: Dict[str, Union[str, Dict]],
            text: str,
            rest_text: str
    ) -> Dict[str, Any]:
        command: str = param['name']
        sep: str = param['separator']
        sub_params: Dict = param['sub_params']
        name, may_text = split_once(text, sep)
        if sep == self.separator:
            name = text
        if not re.match('^' + command + '$', name):
            raise ParamsUnmatched

        self.result.raw_texts[self.result.current_index][0] = may_text
        if sep == self.separator:
            self.result.raw_texts[self.result.current_index][0] = rest_text

        name = name.lstrip("-")
        if not param['args'] and not param['Options']:
            return {name: Ellipsis}

        subcommand = {}
        _get_args = False
        for i in range(len(sub_params)):
            try:
                _text, _rest_text = self.result.split_by(sep)
                if not (sub_param := sub_params.get(_text)):
                    sub_param = sub_params['sub_args']
                    for sp in sub_params:
                        if _text.startswith(sp):
                            sub_param = sub_params.get(sp)
                            break
                if sub_param.get('type'):
                    subcommand.update(self._analyse_option(sub_param, _text, _rest_text))
                elif not _get_args:
                    if args := self._analyse_args(sub_param, _text, sep, _rest_text):
                        _get_args = True
                        subcommand.update(args)
            except (IndexError, KeyError):
                continue
            except ParamsUnmatched:
                if self.exception_in_time:
                    raise
                break

        if sep != self.separator:
            self.result.raw_texts[self.result.current_index][0] = rest_text
        return {name: subcommand}

    def _analyse_header(self) -> str:
        head_text, self.result.raw_texts[0][0] = self.result.split_by(self.separator)
        for ch in self._command_headers:
            if not (_head_find := re.findall('^' + ch + '$', head_text)):
                continue
            self.result.head_matched = True
            if _head_find[0] != ch:
                return _head_find[0]
        if not self.result.head_matched:
            raise ParamsUnmatched

    def _analyse_main_argument(
            self,
            param: Argument_T,
            text: str,
            rest_text: str
    ) -> Union[str, NonTextElement]:
        if isinstance(param, str):
            if not (_param_find := re.findall('^' + param + '$', text)):
                raise ParamsUnmatched
            self.result.raw_texts[self.result.current_index][0] = rest_text
            if _param_find[0] != param:
                return _param_find[0]
        else:
            try:
                # 既不是str也不是dict的情况下，认为param传入了一个类的Type
                may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
                if type(self.result.elements[may_element_index]) is param:
                    return self.result.elements.pop(may_element_index)
            except KeyError:
                pass

    def analyse_message(self, message: Union[str, MessageChain]) -> Arpamar:
        self.result: Arpamar = Arpamar()

        if self.main_argument != "":
            self.result.need_marg = True  # 如果need_marg那么match的元素里一定得有main_argument

        if isinstance(message, str):
            self.result.is_str = True
            self.result.raw_texts.append([message, 0])
        else:
            for i, ele in enumerate(message):
                if ele.__class__.__name__ not in ("Plain", "Source", "Quote", "File"):
                    self.result.elements[i] = ele
                elif ele.__class__.__name__ == "Plain":
                    self.result.raw_texts.append([ele.text.lstrip(' '), i])

        if not self.result.raw_texts:
            self.result.results.clear()
            return self.result

        try:
            self.result.results['header'] = self._analyse_header()
        except ParamsUnmatched:
            self.result.results.clear()
            return self.result

        for i in range(len(self._params)):
            if all([t[0] == "" for t in self.result.raw_texts]):
                break
            try:
                _text, _rest_text = self.result.split_by(self.separator)
                _param = self._params.get(_text)
                if not _param:
                    _param = self._params['main_argument']
                    for p in self._params:
                        if _text.startswith(p):
                            _param = self._params.get(p)
                            break
                if isinstance(_param, dict):
                    if _param['type'] == 'OPT':
                        self.result.results['options'].update(self._analyse_option(_param, _text, _rest_text))
                    elif _param['type'] == 'SBC':
                        self.result.results['options'].update(self._analyse_subcommand(_param, _text, _rest_text))
                elif not self.result.results.get("main_argument"):
                    self.result.results['main_argument'] = self._analyse_main_argument(_param, _text, _rest_text)
            except (IndexError, KeyError):
                pass
            except ParamsUnmatched:
                if self.exception_in_time:
                    raise
                break

        try:
            # 如果没写options并且marg不是str的话，匹配完命令头后是进不去上面的代码的，这里单独拿一段出来
            may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
            if self.result.elements and type(self.result.elements[may_element_index]) is self._params['main_argument']:
                self.result.results['main_argument'] = self.result.elements.pop(may_element_index)
        except (IndexError, KeyError):
            pass

        if len(self.result.elements) == 0 and all([t[0] == "" for t in self.result.raw_texts]) and (
            not self.result.need_marg or (
                self.result.need_marg and not self.result.has('help') and 'main_argument' in self.result.results
            )
        ):
            self.result.matched = True
            self.result.encapsulate_result()
        else:
            self.result.results.clear()
        return self.result
