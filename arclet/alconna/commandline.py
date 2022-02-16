import sys
from typing import List, Dict, Union
import re
import json

from . import *
from .types import ArgPattern, PatternToken

list_type = ArgPattern(
    r"\[(.*?)]",
    token=PatternToken.REGEX_TRANSFORM,
    type_mark=list,
    transform_action=lambda x: x.split(",")
)

args_type = ArgPattern(
    r"(\[.+])*",
    token=PatternToken.REGEX_TRANSFORM,
    type_mark=list,
    transform_action=lambda x: [re.split("[:|=]", p) for p in re.findall(r"\[(.*?)]", x)]
)

alcli = Alconna(
    command="Alconna_CL",
    options=[
        Subcommand(
            "create",
            Option("--command|-C", Args["command_name":str]).help("指定命令名称"),
            Option("--header|-H", Args["command_header":list_type]).help("传入命令头"),
            Option("--option|-O", Args["option_name":str, "option_args":args_type:[]]).help("创建命令选项"),
            Option("--analysed|-A", actions=store_bool(True)).help("从已经分析的命令结构中创建Alconna"),
        ).help("开始创建 Alconna 命令"),
        Subcommand(
            "help",
            args=Args["target":str],
        ).help("展示指定Alconna组件的帮助信息"),
        Subcommand(
            "analysis",
            args=Args["command":AllParam],
        ).help("分析未知命令并尝试转换为Alconna命令结构"),
    ]
)


def command_create(
        command: Dict = None,
        option: Union[Dict, List[Dict]] = None,
        header: List = None,
        analysed: bool = False
):
    if analysed:
        try:
            with open('alconna_cache.json', 'r') as f_obj:
                analysed_args = json.load(f_obj)
        except FileNotFoundError:
            print("请先分析命令")
            return
        header_text = analysed_args.get("header")
        options = analysed_args.get("options")
        command_name = analysed_args.get("command")
        option_text = ""
        if options:
            option_text = "options=[\n"
            for option in options:
                _opt_name = option.get("name")
                _opt_args = option.get("args")
                if _opt_args:
                    _opt_args_text = "Args["
                    for _opt_arg_name, _opt_arg_value in _opt_args.items():
                        _opt_args_text += f"{_opt_arg_name}: {_opt_arg_value}, "
                    _opt_args_text = _opt_args_text[:-2] + "]"
                    _opt = f"\tOption(\"{_opt_name}\", {_opt_args_text}),\n"
                else:
                    _opt = f"\tOption(\"{_opt_name}\"),\n"
                option_text += _opt
            option_text = option_text[:-2] + "\n    ],"

        if header_text:
            construct_command = f"""
Alconna(
    header={header_text},
    command="{command_name}",
    {option_text}
)
"""
        else:
            construct_command = f"""
Alconna(
    command="{command_name}",
    {option_text}
)
"""
        print(construct_command)
        return
    if not command:
        print("你没有指定命令名称")
        return
    option_texts = []
    if option:
        if isinstance(option, list):
            for o in option:
                opt_name = o['option_name']
                if o['option_args']:
                    arg_text = "["
                    for arg in o['option_args']:
                        arg_text += f'"{arg[0]}":"{arg[1]}"' + ", "
                    arg_text = arg_text[:-2] + "]"
                    option_texts.append(f'Option("{opt_name}", Args{arg_text}),')
                else:
                    option_texts.append(f'Option("{opt_name}"),')
        else:
            opt_name = option['option_name']
            if option['option_args']:
                arg_text = "["
                for arg in option['option_args']:
                    arg_text += f'"{arg[0]}":"{arg[1]}"' + ", "
                arg_text = arg_text[:-2] + "]"
                option_texts.append(f'Option("{opt_name}", Args{arg_text}),')
            else:
                option_texts.append(f'Option("{opt_name}"),')
    option_text = ("options=[\n\t" + "\n\t".join(option_texts) + "\n    ],") if option_texts else ""
    if header:
        header_text = "["
        for h in header:
            header_text += f'"{h}", '
        header_text = header_text[:-2] + "]"
        construct_command = f"""
Alconna(
    header={header_text},
    command="{command['command_name']}",
    {option_text}
)
"""
    else:
        construct_command = f"""
Alconna(
    command="{command['command_name']}",
    {option_text}
)
"""
    print(construct_command)


def command_help(target: str):
    try:
        print(eval(target).__doc__)
    except NameError:
        print("没有找到指定的组件")


def command_analysis(command: list):
    result = {}
    command_parts = command[0].split(" ")
    command_headers = command_parts.pop(0)
    if re.match(r"\W.*?", command_headers):
        result['header'] = [command_headers[0]]
        result['command'] = command_headers[1:]
    else:
        result['command'] = command_headers
    if command_parts:
        result['options'] = []
        for i, part in enumerate(command_parts):
            if part.startswith("--"):
                _option = {"type": "Option", "name": part[2:]}
                _args = {}
                while i < len(command_parts) - 1:
                    i += 1
                    if command_parts[i].startswith("--"):
                        break
                    _args[command_parts[i]] = command_parts[i]
                if _args:
                    _option['args'] = _args
                result['options'].append(_option)
    with open('alconna_cache.json', 'w+') as f_obj:
        json.dump(result, f_obj, ensure_ascii=False)
    print(result)


def main(args=None):
    """
    Main entry point for the application.

    :param args: command line arguments
    :type args: list
    """
    if args is None:
        args = sys.argv[1:]
    if not args:
        args = ["--help"]
    args.insert(0, "Alconna_CL")
    text = " ".join(args)
    result = alcli.analyse_message(text)
    if result.matched:
        if result.options.get("create"):
            command_create(**result.all_matched_args)
        elif result.options.get("help"):
            command_help(**result.all_matched_args)
        elif result.options.get("analysis"):
            command_analysis(**result.all_matched_args)
