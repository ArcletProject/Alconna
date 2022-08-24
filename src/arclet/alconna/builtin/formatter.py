import re
from typing import List, Dict, Any, Union, Set
from nepattern import Empty, AllParam, BasePattern

from arclet.alconna.args import Args, ArgUnit
from arclet.alconna.base import Subcommand, Option
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
            if parameter['value'] is AllParam:
                return f"<...{name}>"
            if not isinstance(parameter['value'], BasePattern) or parameter['value'].pattern != name:
                arg += f"{'@' if parameter['kwonly'] else ':'}{parameter['value']}"
            if parameter['default'].display is Empty:
                arg += " = None"
            elif parameter['default'].display is not None:
                arg += f" = {parameter['default'].display} "
        return arg + ("]" if parameter['optional'] else ">")

    def parameters(self, args: Args) -> str:
        param_texts = [self.param(k, param) for k, param in args.argument.items()]
        if len(args.separators) == 1:
            separator = tuple(args.separators)[0]
            res = separator.join(param_texts)
        else:
            res = " ".join(param_texts) + " splitBy:" + "/".join(args.separators)
        notice = [(k, param['notice']) for k, param in args.argument.items() if param['notice']]
        if not notice:
            return res
        return res + "\n## 注释\n  " + "\n  ".join(f"{v[0]}: {v[1]}" for v in notice)

    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        help_string = ("\n" + root['description']) if root.get('description') else ""
        usage = ""
        if res := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Usage:{res[0]};", "")
            usage = '\n用法:\n' + res[0]
        example = ""
        if res := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Example:{res[0]};", "")
            example = '\n使用示例:\n' + res[0]
        headers = f"[{''.join(map(str, headers))}]" if (headers := root.get('header', [''])) != [''] else ""
        cmd = f"{headers}{root.get('name', '')}"
        command_string = cmd or (root['name'] + tuple(separators)[0])
        return f"{command_string} %s{help_string}{usage}\n%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        if isinstance(node, Subcommand):
            name = " ".join(node.requires) + (' ' if node.requires else '') + node.name
            option_string = "".join([self.part(i).replace("\n", "\n ") for i in node.options])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {node.help_text}\n"
                f"  {name}{tuple(node.separators)[0]}"
                f"{self.parameters(node.args)}\n"
                f"{option_help}{option_string}"
            )
        elif isinstance(node, Option):
            alias_text = " ".join(node.requires) + (' ' if node.requires else '') + ", ".join(node.aliases)
            return (
                f"# {node.help_text}\n"
                f"  {alias_text}{tuple(node.separators)[0]}"
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
            if parameter['value'] is AllParam:
                return f"{name.upper()}..."
            if not isinstance(parameter['value'], BasePattern) or parameter['value'].pattern != name:
                arg += f"=[{parameter['value']}]" if parameter['kwonly'] else f"[{parameter['value']}]"
            if parameter['default'].display is Empty:
                arg += "=None"
            elif parameter['default'].display is not None:
                arg += f"={parameter['default'].display}"
        return arg + ("]" if parameter['optional'] else "")

    def parameters(self, args: Args) -> str:
        param_texts = [self.param(k, param) for k, param in args.argument.items()]
        if len(args.separators) == 1:
            separator = tuple(args.separators)[0]
            res = separator.join(param_texts)
        else:
            res = " ".join(param_texts) + ", USED SPLIT:" + "/".join(args.separators)
        notice = [(k, param['notice']) for k, param in args.argument.items() if param['notice']]
        if not notice:
            return res
        return res + "\n  内容:\n  " + "\n  ".join(f"{v[0]}: {v[1]}" for v in notice)

    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        help_string = ("\n描述: " + root['description'] + "\n") if root.get('description') else ""
        usage = ""
        if res := re.findall(r".*Usage:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Usage:{res[0]};", "")
            usage = '\n用法:' + res[0] + '\n'
        example = ""
        if res := re.findall(r".*Example:(.+?);", help_string, flags=re.S):
            help_string = help_string.replace(f"Example:{res[0]};", "")
            example = '\n样例:' + res[0] + '\n'
        header_text = f"/{''.join(map(str, headers))}/" if (headers := root.get('header', [''])) != [''] else ""
        cmd = f"{header_text}{root.get('name', '')}"
        sep = tuple(separators)[0]
        command_string = cmd or (root['name'] + sep)
        return f"\n命令: {command_string}%s{help_string}{usage}%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        ...

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        option_string = ""
        options = []
        opt_description = []
        for opt in filter(lambda x: isinstance(x, Option) and x.name != "--shortcut", parts):
            alias_text = " ".join(opt.requires) + (' ' if opt.requires else '') + ", ".join(opt.aliases)
            options.append(f"  {alias_text}{tuple(opt.separators)[0]}{self.parameters(opt.args)}")
            opt_description.append(opt.help_text)
        if options:
            max_len = max(map(lambda x: len(x), options))
            option_string = "\n".join(f"{i.ljust(max_len)} {j}" for i, j in zip(options, opt_description))
        subcommand_string = ""
        subcommands = []
        sub_description = []
        for sub in filter(lambda x: isinstance(x, Subcommand), parts):
            name = " ".join(sub.requires) + (' ' if sub.requires else '') + sub.name
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            args = self.parameters(sub.args)
            subcommands.append(f"  {name} {tuple(sub.separators)[0].join([args, sub_topic])}")
            sub_description.append(sub.help_text)
        if subcommands:
            max_len = max(map(lambda x: len(x), subcommands))
            subcommand_string = "\n".join(f"{i.ljust(max_len)} {j}" for i, j in zip(subcommands, sub_description))
        option_help = "选项:\n" if option_string else ""
        subcommand_help = "子命令:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}\n{option_help}{option_string}\n"
