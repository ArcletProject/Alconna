from typing import Dict, List, Optional, Union, Any, overload
import re
from .util import split_once, split
from .component import Option, CommandInterface, Subcommand, Arpamar
from .types import NonTextElement, MessageChain, TAValue, Args
from .exceptions import ParamsUnmatched, InvalidFormatMap, NullTextMessage, InvalidName

_builtin_option = Option("-help")


class Alconna(CommandInterface):
    """
    亚尔康娜（Alconna），Cesloi的妹妹

    用于更加奇怪(大雾)精确的命令解析，支持String与MessageChain

    样例：Alconna(
        headers=[""],
        command="name",
        options=[
            Subcommand("sub_name",Option("sub_opt", args=sub_arg), args=sub_main_args),
            Option("opt", args=arg)
            ]
        main_args=main_args
        )

    其中
        - name: 命令名称
        - sub_name: 子命令名称
        - sub_opt: 子命令选项名称
        - sub_arg: 子命令选项参数
        - sub_main_args: 子命令主参数
        - opt: 命令选项名称
        - arg: 命令选项参数

    Args:
        headers: 呼叫该命令的命令头，一般是你的机器人的名字或者符号，与 command 至少有一个填写
        command: 命令名称，你的命令的名字，与 headers 至少有一个填写
        options: 命令选项，你的命令可选择的所有 option ，包括子命令与单独的选项
        main_args: 主参数，填入后当且仅当命令中含有该参数时才会成功解析
    """

    name = "Alconna"
    headers: List[str]
    command: str
    options: List[Union[Option, Subcommand]]
    result: Arpamar

    def __init__(
            self,
            headers: List[str] = None,
            command: Optional[str] = None,
            options: List[Union[Option, Subcommand]] = None,
            main_args: Optional[Args] = None,
            exception_in_time: bool = False,
            **kwargs
    ):
        # headers与command二者必须有其一
        if all([all([not headers, not command]), not options, not main_args]):
            raise InvalidName
        self.headers = headers or [""]
        self.command = command or ""
        self.options = options or []
        self.args = main_args or Args(**kwargs)
        self.exception_in_time = exception_in_time
        self.options.append(_builtin_option)
        self._initialise_arguments()

    def help(self, help_string: str):
        help_string += "\n" if help_string else ""
        command_string = f"{'|'.join(self._command_headers)}{self.separator}"
        option_string = "".join(list(map(lambda x: getattr(x, "help_doc", ""),
                                         filter(lambda x: isinstance(x, Option), self.options))))
        subcommand_string = "".join(list(map(lambda x: getattr(x, "help_doc", ""),
                                             filter(lambda x: isinstance(x, Subcommand), self.options))))
        option_help = "可用的选项有:\n" if option_string else ""
        subcommand_help = "可用的子命令有:\n" if subcommand_string else ""
        setattr(self, "help_doc", f"{command_string}{self.args.params(self.separator)}{help_string}\n"
                                  f"{subcommand_help}{subcommand_string}"
                                  f"{option_help}{option_string}")
        return self

    def get_help(self):
        return getattr(self, "help_doc", getattr(self.help(""), "help_doc"))

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: List[Union[TAValue, Args, Option, List[Option]]],
            reflect_map: Optional[Dict[str, str]] = None
    ) -> "Alconna":
        ...

    @classmethod
    @overload
    def format(
            cls,
            format_string: str,
            format_args: Dict[str, Union[TAValue, Args, Option, List[Option]]],
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
        main_args = None

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
                if isinstance(value, Args):
                    options.append(Subcommand(sub_name, Option(opt_name, args=value)))
                elif not isinstance(value, Option) and not isinstance(value, List):
                    options.append(Subcommand(sub_name, Option(opt_name, **{key: value})))
                _string_stack.clear()

            if stack_count == 1:
                may_name = _string_stack.pop(0)
                if isinstance(value, Option):
                    options.append(Subcommand(may_name, value))
                elif isinstance(value, List):
                    options.append(Subcommand(may_name, *value))
                elif isinstance(value, Args):
                    options.append(Option(may_name, args=value))
                else:
                    options.append(Option(may_name, **{key: value}))

            if stack_count == 0:
                if i == 0:
                    if isinstance(value, Args):
                        main_args = value
                    elif not isinstance(value, Option) and not isinstance(value, List):
                        main_args = Args(**{key: value})
                else:
                    if isinstance(value, Option):
                        options.append(value)
                    elif isinstance(value, List):
                        options[-1].options.extend(value)
                    elif isinstance(value, Args):
                        options[-1].args = value
                    else:
                        options[-1].args.argument.update({key: value})

        alc = cls(command=command, options=options, main_args=main_args)
        return alc

    def option(self, name: str, sep: str = " ", args: Optional[Args] = None, alias: Optional[str] = None, **kwargs):
        self.options.append(Option(name, args=args, alias=alias, **kwargs).separate(sep))
        self._initialise_arguments()
        return self

    def add_options(self, options: List[Option]):
        self.options.extend(options)
        self._initialise_arguments()

    def _initialise_arguments(self):
        # params是除开命令头的剩下部分
        self._params: Dict[str, Union[Args, Option, Subcommand]] = {"main_args": self.args}
        for opts in self.options:
            if isinstance(opts, Subcommand):
                for sub_opts in opts.options:
                    opts.sub_params.setdefault(sub_opts.name, sub_opts)
            self._params[opts.name] = opts

        self._command_headers: List[str] = []  # 依据headers与command生成一个列表，其中含有所有的命令头
        if self.headers != [""]:
            for i in self.headers:
                self._command_headers.append(i + self.command)
        elif self.command:
            self._command_headers.append(self.command)

    def _analyse_args(
            self,
            opt_args: Args,
            may_args: str,
            sep: str,
            rest_text: str
    ) -> Dict[str, Any]:

        _option_dict: Dict[str, Any] = {}
        may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
        for key, value, default in opt_args:
            if isinstance(value, str):
                if sep != self.separator:
                    may_arg, may_args = split_once(may_args, sep)
                else:
                    may_arg, rest_text = self.result.split_by(sep)
                if not (_arg_find := re.findall('^' + value + '$', may_arg)):
                    if default is not None:
                        _arg_find = [default]
                    else:
                        raise ParamsUnmatched(f"param {may_arg} is incorrect")
                if may_arg == value:
                    _arg_find[0] = Ellipsis
                _option_dict[key] = _arg_find[0]
                if sep == self.separator:
                    self.result.raw_texts[self.result.current_index][0] = rest_text
            else:
                if type(self.result.elements[may_element_index]) is value:
                    _option_dict[key] = self.result.elements.pop(may_element_index)
                    may_element_index += 1
                elif default is not None:
                    _option_dict[key] = default
                    may_element_index += 1
                else:
                    raise ParamsUnmatched(
                        f"param type {type(self.result.elements[may_element_index])} is incorrect")
        return _option_dict

    def _analyse_option(
            self,
            param: Option,
            text: str,
            rest_text: str
    ) -> Dict[str, Any]:

        opt: str = param.name
        alias: str = param.alias
        args: Args = param.args
        sep: str = param.separator
        name, may_args = split_once(text, sep)
        if sep == self.separator:  # 在sep等于separator的情况下name是被提前切出来的
            name = text
        if (not re.match('^' + opt + '$', name)) and (not re.match('^' + alias + '$', name)):  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {opt}")
        self.result.raw_texts[self.result.current_index][0] = rest_text
        name = name.lstrip("-")
        if not args.argument:
            return {name: Ellipsis}
        return {name: self._analyse_args(args, may_args, sep, rest_text)}

    def _analyse_subcommand(
            self,
            param: Subcommand,
            text: str,
            rest_text: str
    ) -> Dict[str, Any]:
        command: str = param.name
        sep: str = param.separator
        sub_params: Dict = param.sub_params
        name, may_text = split_once(text, sep)
        if sep == self.separator:
            name = text
        if not re.match('^' + command + '$', name):
            raise ParamsUnmatched(f"{name} dose not matched with {command}")

        self.result.raw_texts[self.result.current_index][0] = may_text
        if sep == self.separator:
            self.result.raw_texts[self.result.current_index][0] = rest_text

        name = name.lstrip("-")
        if not param.args.argument and not param.options:
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
                if isinstance(sub_param, Option):
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
            raise ParamsUnmatched(f"{head_text} does not matched")

    def analyse_message(self, message: Union[str, MessageChain]) -> Arpamar:  # TODO:cache功能, 即保存解析步骤
        if hasattr(self, "result"):
            del self.result
        self.result: Arpamar = Arpamar()

        if self.args.argument:
            self.result.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument

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
            if self.exception_in_time:
                raise NullTextMessage
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
                    _param = self._params['main_args']
                    for p, value in self._params.items():
                        if _text.startswith(p) or _text.startswith(getattr(value, 'alias', p)):
                            _param = value
                            break
                if isinstance(_param, Option):
                    self.result.results['options'].update(self._analyse_option(_param, _text, _rest_text))
                elif isinstance(_param, Subcommand):
                    self.result.results['options'].update(self._analyse_subcommand(_param, _text, _rest_text))
                elif not self.result.results.get("main_args"):
                    self.result.results['main_args'] = self._analyse_args(_param, _text, self.separator, _rest_text)
            except (IndexError, KeyError):
                pass
            except ParamsUnmatched:
                if self.exception_in_time:
                    raise
                break

        try:
            may_element_index = self.result.raw_texts[self.result.current_index][1] + 1
            for key, value, default in self.args:
                if type(self.result.elements[may_element_index]) is value:
                    self.result.results['main_args'][key] = self.result.elements.pop(may_element_index)
                    may_element_index += 1
                elif default is not None:
                    self.result.results['main_args'][key] = default
                    may_element_index += 1
                else:
                    raise ParamsUnmatched(
                        f"param element type {type(self.result.elements[may_element_index])} is incorrect")
        except (KeyError, IndexError):
            pass
        except ParamsUnmatched:
            if self.exception_in_time:
                raise
            pass

        if len(self.result.elements) == 0 and all(
                [t[0] == "" for t in self.result.raw_texts]
        ) and (not self.result.need_main_args or (
                self.result.need_main_args and not self.result.has('help') and self.result.results.get('main_args')
        )):
            self.result.matched = True
            self.result.encapsulate_result()
        else:
            if self.exception_in_time:
                raise ParamsUnmatched(", ".join([t[0] for t in self.result.raw_texts]))
            self.result.results.clear()
        return self.result
