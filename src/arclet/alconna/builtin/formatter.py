from typing import List, Dict, Any, Union, Set
import re

from arclet.alconna.types import Empty, ArgPattern, _AnyParam, TypePattern
from arclet.alconna.components.output import AbstractTextFormatter


class DefaultTextFormatter(AbstractTextFormatter):
    """
    默认的帮助文本格式化器
    """
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        parts = trace.pop('sub_nodes')
        header = self.header(trace)
        body = self.body(parts)  # type: ignore
        return header % body

    def param(self, parameter: Dict[str, Any]) -> str:
        arg = ("<" if not parameter['optional'] else "[") + parameter['name']
        _sep = "=" if parameter['kwonly'] else ":"
        if not parameter['hidden']:
            if isinstance(parameter['value'], _AnyParam):
                arg += f"{_sep}WildMatch"
            elif isinstance(parameter['value'], (ArgPattern, TypePattern)):
                arg += f"{_sep}{parameter['value'].alias or parameter['value'].origin_type.__name__}"
            else:
                try:
                    arg += f"{_sep}Type@{parameter['value'].__name__}"
                except AttributeError:
                    arg += f"{_sep}Type@{repr(parameter['value'])}"
            if parameter['default'] is Empty:
                arg += ", default=None"
            elif parameter['default'] is not None:
                arg += f", default={parameter['default']}"
        return arg + (">" if not parameter['optional'] else "]")

    def parameters(self, params: List[Dict[str, Any]], separators: Set[str]) -> str:
        param_texts = []
        for param in params:
            param_texts.append(self.param(param))
        if len(separators) == 1:
            separator = separators.copy().pop()
            return separator.join(param_texts)
        return " ".join(param_texts) + " splitBy:" + "/".join(separators)

    def header(self, root: Dict[str, Any]) -> str:
        help_string = ("\n" + root['description']) if root.get('description') else ""
        if usage := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace("Usage:" + usage[0] + ";", "")
            usage = '\n用法:\n' + usage[0]
        else:
            usage = ""
        if example := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace("Example:" + example[0] + ";", "")
            example = '\n使用示例:\n' + example[0]
        else:
            example = ""
        headers = root['additional_info'].get('headers')
        command = root['additional_info'].get('command')
        headers_text = []
        if headers and headers != [""]:
            for i in headers:
                if isinstance(i, str):
                    headers_text.append(i + command)
                else:
                    headers_text.extend((f"{i}", command))
        elif command:
            headers_text.append(command)
        sep = root['separators'].copy().pop()
        command_string = f"{'|'.join(headers_text)}{sep}" \
            if headers_text else root['name'] + sep
        return (
            f"{command_string}{self.parameters(root['parameters'], root['param_separators'])}"
            f"{help_string}{usage}\n%s{example}"
        )

    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        sep = sub['separators'].copy().pop()
        if node_type == 'option':
            aliases = sub['additional_info'].get('aliases')
            alias_text = ", ".join(aliases)
            return (
                f"# {sub['description']}\n"
                f"  {alias_text}{sep}"
                f"{self.parameters(sub['parameters'], sub['param_separators'])}\n"
            )
        elif node_type == 'subcommand':
            option_string = "".join([self.part(i, 'option').replace("\n", "\n ") for i in sub['sub_nodes']])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {sub['description']}\n"
                f"  {sub['name']}{sep}"
                f"{self.parameters(sub['parameters'], sub['param_separators'])}\n"
                f"{option_help}{option_string}"
            )
        else:
            return f"unknown node type:{node_type}"

    def body(self, parts: List[Dict[str, Any]]) -> str:
        option_string = "".join(
            [
                self.part(opt, 'option') for opt in
                filter(lambda x: x['type'] == 'option', parts)
                if opt['name'] not in {"--help", "--shortcut"}
            ]
        )
        subcommand_string = "".join(
            [
                self.part(sub, 'subcommand') for sub in
                filter(lambda x: x['type'] == 'subcommand', parts)
            ]
        )
        option_help = "可用的选项有:\n" if option_string else ""
        subcommand_help = "可用的子命令有:\n" if subcommand_string else ""
        return (
            f"{subcommand_help}{subcommand_string}"
            f"{option_help}{option_string}"
        )


class ArgParserTextFormatter(AbstractTextFormatter):
    """
    argparser 风格的帮助文本格式化器
    """
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        parts: List[dict] = trace.pop('sub_nodes')  # type: ignore
        sub_names = [i['name'] for i in parts if i['type'] == 'subcommand']
        opt_names = [i['name'] for i in parts if i['type'] == 'option']
        sub_names = "" if not sub_names else [f" [{i}]" for i in sub_names] if len(sub_names) < 5 else " [COMMANDS]"
        opt_names = "" if not opt_names else [f" [{i}]" for i in opt_names] if len(opt_names) < 6 else " [OPTIONS]"
        topic = trace['name'].replace("ALCONNA::", "") + " " + sub_names + opt_names
        header = self.header(trace)
        body = self.body(parts)  # type: ignore
        return topic + '\n' + header % body

    def param(self, parameter: Dict[str, Any]) -> str:
        # FOO(str), BAR=(int)
        arg = f"{parameter['name'].upper()}" if not parameter['optional'] else f"[{parameter['name'].upper()}"
        _sep = "=(%s)" if parameter['kwonly'] else "(%s)"
        if not parameter['hidden']:
            if isinstance(parameter['value'], _AnyParam):
                arg += _sep % "Any"
            elif isinstance(parameter['value'], (ArgPattern, TypePattern)):
                arg += _sep % f"{parameter['value'].alias or parameter['value'].origin_type.__name__}"
            else:
                try:
                    arg += _sep % f"Type_{parameter['value'].__name__}"
                except AttributeError:
                    arg += _sep % f"Type_{repr(parameter['value'])}"
            if parameter['default'] is Empty:
                arg += "=None"
            elif parameter['default'] is not None:
                arg += f"={parameter['default']}"
        return (arg + "") if not parameter['optional'] else (arg + "]")

    def parameters(self, params: List[Dict[str, Any]], separators: Set[str]) -> str:
        param_texts = []
        for param in params:
            param_texts.append(self.param(param))
        if len(separators) == 1:
            separator = separators.copy().pop()
            return separator.join(param_texts)
        return " ".join(param_texts) + ", USED SPLIT:" + "/".join(separators)

    def header(self, root: Dict[str, Any]) -> str:
        help_string = ("\n描述: " + root['description'] + "\n") if root.get('description') else ""
        if usage := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace("Usage:" + usage[0] + ";", "")
            usage = '\n用法:' + usage[0] + '\n'
        else:
            usage = ""
        if example := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace("Example:" + example[0] + ";", "")
            example = '\n样例:' + example[0] + '\n'
        else:
            example = ""
        headers = root['additional_info'].get('headers')
        command = root['additional_info'].get('command')
        headers_text = []
        if headers and headers != [""]:
            for i in headers:
                if isinstance(i, str):
                    headers_text.append(i + command)
                else:
                    headers_text.extend((f"{i}", command))
        elif command:
            headers_text.append(command)
        sep = root['separators'].copy().pop()
        command_string = f"{'|'.join(headers_text)}{sep}" \
            if headers_text else root['name'] + sep
        return (
            f"\n命令: {command_string}{help_string}{usage}"
            f"{self.parameters(root['parameters'], root['param_separators'])}\n%s{example}"
        )

    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        ...

    def body(self, parts: List[Dict[str, Any]]) -> str:
        option_string = ""
        options = []
        opt_description = []
        for opt in filter(lambda x: x['type'] == 'option' and x['name'] != "--shortcut", parts):
            aliases = opt['additional_info'].get('aliases')
            alias_text = ", ".join(aliases)
            args = f"{self.parameters(opt['parameters'], opt['param_separators'])}"
            sep = opt['separators'].copy().pop()
            options.append(f"  {alias_text}{sep}{args}")
            opt_description.append(opt['description'])
        if options:
            max_len = max(map(lambda x: len(x), options))
            option_string = "\n".join(
                [f"{i.ljust(max_len)} {j}" for i, j in zip(options, opt_description)]
            )
        subcommand_string = ""
        subcommands = []
        sub_description = []
        for sub in filter(lambda x: x['type'] == 'subcommand', parts):
            sub_topic = " ".join([f"[{i['name']}]" for i in sub['sub_nodes']])
            args = f"{self.parameters(sub['parameters'], sub['param_separators'])}"
            sep = sub['separators'].copy().pop()
            subcommands.append(f"  {sub['name']} {sep.join([args, sub_topic])}")
            sub_description.append(sub['description'])
        if subcommands:
            max_len = max(map(lambda x: len(x), subcommands))
            subcommand_string = "\n".join(
                [f"{i.ljust(max_len)} {j}" for i, j in zip(subcommands, sub_description)]
            )
        option_help = "选项:\n" if option_string else ""
        subcommand_help = "子命令:\n" if subcommand_string else ""
        return (
            f"{subcommand_help}{subcommand_string}\n"
            f"{option_help}{option_string}\n"
        )
