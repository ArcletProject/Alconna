from typing import List, Dict, Any, Union
import re

from arclet.alconna.types import Empty, ArgPattern, _AnyParam
from arclet.alconna.visitor import AbstractHelpTextFormatter


class DefaultHelpTextFormatter(AbstractHelpTextFormatter):
    """
    默认的帮助文本格式化器
    """
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        parts = trace.pop('sub_nodes')
        header = self.header(trace)
        body = self.body(parts)  # type: ignore
        return header % body

    def param(self, parameter: Dict[str, Any]) -> str:
        arg = f"<{parameter['name']}" if not parameter['optional'] else f"[{parameter['name']}"
        _sep = "=" if parameter['kwonly'] else ":"
        if not parameter['hidden']:
            if isinstance(parameter['value'], _AnyParam):
                arg += f"{_sep}WildMatch"
            elif isinstance(parameter['value'], ArgPattern):
                arg += f"{_sep}{parameter['value'].alias or parameter['value'].origin_type.__name__}"
            else:
                try:
                    arg += f"{_sep}Type_{parameter['value'].__name__}"
                except AttributeError:
                    arg += f"{_sep}Type_{repr(parameter['value'])}"
            if parameter['default'] is Empty:
                arg += ", default=None"
            elif parameter['default'] is not None:
                arg += f", default={parameter['default']}"
        return arg + (">" if not parameter['optional'] else f"]")

    def parameters(self, params: List[Dict[str, Any]], separator: str = " ") -> str:
        param_texts = []
        for param in params:
            param_texts.append(self.param(param))
        return separator.join(param_texts)

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
        command_string = f"{'|'.join(headers_text)}{root['separator']}" \
            if headers_text else root['name'] + root['separator']
        return (
            f"{command_string}{self.parameters(root['parameters'], root['separator'])}"
            f"{help_string}{usage}\n%s{example}"
        )

    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        if node_type == 'option':
            aliases = sub['additional_info'].get('aliases')
            alias_text = ", ".join(aliases)
            return (
                f"# {sub['description']}\n"
                f"  {alias_text}{sub['separator']}"
                f"{self.parameters(sub['parameters'], sub['separator'])}\n"
            )
        elif node_type == 'subcommand':
            option_string = "".join([self.part(i, 'option').replace("\n", "\n ") for i in sub['sub_nodes']])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {sub['description']}\n"
                f"  {sub['name']}{sub['separator']}"
                f"{self.parameters(sub['parameters'], sub['separator'])}\n"
                f"{option_help}{option_string}"
            )
        else:
            return f"unknown node type:{node_type}"

    def body(self, parts: List[Dict[str, Any]]) -> str:
        option_string = "".join(
            [
                self.part(opt, 'option') for opt in
                filter(lambda x: x['type'] == 'option', parts)
                if opt['name'] != "--help"
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


class ArgParserHelpTextFormatter(AbstractHelpTextFormatter):
    """
    argparser 风格的帮助文本格式化器
    """
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        parts: List[dict] = trace.pop('sub_nodes')  # type: ignore
        sub_names = [i['name'] for i in parts]
        topic = trace['name'].replace("ALCONNA::", "") + " " + " ".join(
            [f"[{i}]" for i in sub_names if i != "--help"]  # type: ignore
        )
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
            elif isinstance(parameter['value'], ArgPattern):
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

    def parameters(self, params: List[Dict[str, Any]], separator: str = " ") -> str:
        param_texts = []
        for param in params:
            param_texts.append(self.param(param))
        return separator.join(param_texts)

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
        command_string = f"{'|'.join(headers_text)}{root['separator']}" \
            if headers_text else root['name'] + root['separator']
        return (
            f"\n命令: {command_string}{help_string}{usage}"
            f"{self.parameters(root['parameters'], root['separator'])}\n%s{example}"
        )

    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        if node_type == 'option':
            aliases = sub['additional_info'].get('aliases')
            alias_text = ", ".join(aliases)
            return (
                f"# {sub['description']}\n"
                f"  {alias_text}{sub['separator']}"
                f"{self.parameters(sub['parameters'], sub['separator'])}\n"
            )
        elif node_type == 'subcommand':
            option_string = "".join([self.part(i, 'option').replace("\n", "\n ") for i in sub['sub_nodes']])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {sub['description']}\n"
                f"  {sub['name']}{sub['separator']}"
                f"{self.parameters(sub['parameters'], sub['separator'])}\n"
                f"{option_help}{option_string}"
            )
        else:
            return f"unknown node type:{node_type}"

    def body(self, parts: List[Dict[str, Any]]) -> str:
        option_string = ""
        options = []
        opt_description = []
        for opt in filter(lambda x: x['type'] == 'option', parts):
            aliases = opt['additional_info'].get('aliases')
            alias_text = ", ".join(aliases)
            args = f"{self.parameters(opt['parameters'], opt['separator'])}"
            options.append(f"  {alias_text}{opt['separator']}{args}")
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
            args = f"{self.parameters(sub['parameters'], sub['separator'])}"
            subcommands.append(f"  {sub['name']} {sub['separator'].join([args, sub_topic])}")
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
