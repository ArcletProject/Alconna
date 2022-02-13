import sys
from typing import List, Dict, Union
import re

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
            Option("--show|-S", actions=store_bool(True)).help("展示创建命令的生成代码"),
        ).help("开始创建 Alconna 命令"),
        Subcommand(
            "help",
            args=Args["target":str],
        ).help("展示指定Alconna组件的帮助信息"),
    ]
)


def command_create(
        command: Dict = None,
        option: Union[Dict, List[Dict]] = None,
        header: List = None,
        show: bool = False

):
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
    if show:
        print(construct_command)


def command_help(target: str):
    try:
        print(eval(target).__doc__)
    except NameError:
        print("没有找到指定的组件")


def main(args=None):
    """
    Main entry point for the application.

    :param args: command line arguments
    :type args: list
    """
    if args is None:
        args = sys.argv[1:]

    args.insert(0, "Alconna_CL")
    text = " ".join(args)
    result = alcli.analyse_message(text)
    if result.matched:
        if result.options.get("create"):
            command_create(**result.all_matched_args)
        elif result.options.get("help"):
            command_help(**result.all_matched_args)
