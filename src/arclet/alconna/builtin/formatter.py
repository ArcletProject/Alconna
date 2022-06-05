from typing import List, Dict, Any, Union, Set
import re

from arclet.alconna.base import Args, Subcommand, Option, ArgUnit
from arclet.alconna.typing import Empty, AllParam, BasePattern
from arclet.alconna.components.output import AbstractTextFormatter, Trace


class DefaultTextFormatter(AbstractTextFormatter):
    """
    默认的帮助文本格式化器
    """
    def format(self, trace: Trace) -> str:
        header = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(trace.body)
        return header % (param, body)

    def param(self, name: str, parameter: ArgUnit) -> str:
        arg = ("[" if parameter['optional'] else "<") + name
        if not parameter['hidden']:
            _sep = "@" if parameter['kwonly'] else ":"
            if parameter['value'] is AllParam:
                return f"<...{name}>"
            if isinstance(parameter['value'], BasePattern) and parameter['value'].pattern == name:
                pass
            else:
                arg += f"{_sep}{parameter['value']}"
            if parameter['default'] is Empty:
                arg += " = None"
            elif parameter['default'] is not None:
                arg += f" = {parameter['default']} "
        return arg + ("]" if parameter['optional'] else ">")

    def parameters(self, args: Args) -> str:
        param_texts = [self.param(k, param) for k, param in args.argument.items()]
        if len(args.separators) == 1:
            separator = args.separators.copy().pop()
            return separator.join(param_texts)
        return " ".join(param_texts) + " splitBy:" + "/".join(args.separators)

    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        help_string = ("\n" + root['description']) if root.get('description') else ""
        if usage := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Usage:{usage[0]};", "")
            usage = '\n用法:\n' + usage[0]
        else:
            usage = ""
        if example := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Example:{example[0]};", "")
            example = '\n使用示例:\n' + example[0]
        else:
            example = ""
        headers = root.get('headers', [''])
        command = root.get('name', '')
        headers = f"[{''.join(map(str, headers))}]" if headers != [''] else ""
        cmd = f"{headers}{command}"
        sep = separators.copy().pop()
        command_string = cmd or (root['name'] + sep)
        return f"{command_string} %s{help_string}{usage}\n%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        if isinstance(node, Subcommand):
            sep = node.separators.copy().pop()
            name = " ".join(node.requires) + (' ' if node.requires else '') + node.name
            option_string = "".join([self.part(i).replace("\n", "\n ") for i in node.options])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {node.help_text}\n"
                f"  {name}{sep}"
                f"{self.parameters(node.args)}\n"
                f"{option_help}{option_string}"
            )
        elif isinstance(node, Option):
            sep = node.separators.copy().pop()
            alias_text = ", ".join(node.aliases)
            alias_text = " ".join(node.requires) + (' ' if node.requires else '') + alias_text
            return (
                f"# {node.help_text}\n"
                f"  {alias_text}{sep}"
                f"{self.parameters(node.args)}\n"
            )
        else:
            raise TypeError(f"{node} is not a valid node")

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        option_string = "".join(
            self.part(opt) for opt in filter(lambda x: isinstance(x, Option), parts)
            if opt.name not in {"--help", "--shortcut"}
        )
        subcommand_string = "".join(self.part(sub) for sub in filter(lambda x: isinstance(x, Subcommand), parts))
        option_help = "可用的选项有:\n" if option_string else ""
        subcommand_help = "可用的子命令有:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"


class ArgParserTextFormatter(AbstractTextFormatter):
    """
    argparser 风格的帮助文本格式化器
    """
    def format(self, trace: Trace) -> str:
        parts = trace.body  # type: ignore
        sub_names = [i.name for i in filter(lambda x: isinstance(x, Subcommand), parts)]
        opt_names = [i.name for i in filter(lambda x: isinstance(x, Option), parts)]
        sub_names = (
            " ".join(f"[{i}]" for i in sub_names) if len(sub_names) < 5 else " [COMMANDS]"
        ) if sub_names else ""

        opt_names = (
            " ".join(f"[{i}]" for i in opt_names) if len(opt_names) < 6 else " [OPTIONS]"
        ) if opt_names else ""

        topic = trace.head['name'] + " " + sub_names + " " + opt_names
        header = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(parts)
        return topic + '\n' + header % (param, body)

    def param(self, name: str, parameter: ArgUnit) -> str:
        # FOO[str], BAR=<int>
        arg = ("[" if parameter['optional'] else "") + name.upper()
        if not parameter['hidden']:
            _sep = "=[%s]" if parameter['kwonly'] else "[%s]"
            if parameter['value'] is AllParam:
                return f"{name.upper()}..."
            if isinstance(parameter['value'], BasePattern) and parameter['value'].pattern == name:
                pass
            else:
                arg += _sep % f"{parameter['value']}"
            if parameter['default'] is Empty:
                arg += "=None"
            elif parameter['default'] is not None:
                arg += f"={parameter['default']}"
        return arg + ("]" if parameter['optional'] else "")

    def parameters(self, args: Args) -> str:
        param_texts = [self.param(k, param) for k, param in args.argument.items()]
        if len(args.separators) == 1:
            separator = args.separators.copy().pop()
            return separator.join(param_texts)
        return " ".join(param_texts) + ", USED SPLIT:" + "/".join(args.separators)

    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        help_string = ("\n描述: " + root['description'] + "\n") if root.get('description') else ""
        if usage := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Usage:{usage[0]};", "")
            usage = '\n用法:' + usage[0] + '\n'
        else:
            usage = ""
        if example := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Example:{example[0]};", "")
            example = '\n样例:' + example[0] + '\n'
        else:
            example = ""
        headers = root.get('headers', [''])
        command = root.get('name', '')
        header_text = f"/{''.join(map(str, headers))}/" if headers != [''] else ""
        cmd = f"{header_text}{command}"
        sep = separators.copy().pop()
        command_string = cmd or (root['name'] + sep)
        return f"\n命令: {command_string}{help_string}{usage}%s\n%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        ...

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        option_string = ""
        options = []
        opt_description = []
        for opt in filter(lambda x: isinstance(x, Option) and x.name != "--shortcut", parts):
            alias_text = ", ".join(opt.aliases)
            alias_text = " ".join(opt.requires) + (' ' if opt.requires else '') + alias_text
            args = self.parameters(opt.args)
            sep = opt.separators.copy().pop()
            options.append(f"  {alias_text}{sep}{args}")
            opt_description.append(opt.help_text)
        if options:
            max_len = max(map(lambda x: len(x), options))
            option_string = "\n".join(
                [f"{i.ljust(max_len)} {j}" for i, j in zip(options, opt_description)]
            )
        subcommand_string = ""
        subcommands = []
        sub_description = []
        for sub in filter(lambda x: isinstance(x, Subcommand), parts):
            name = " ".join(sub.requires) + (' ' if sub.requires else '') + sub.name
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            args = self.parameters(sub.args)
            sep = sub.separators.copy().pop()
            subcommands.append(f"  {name} {sep.join([args, sub_topic])}")
            sub_description.append(sub.help_text)
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
