from arclet.alconna import Alconna, Option, CommandMeta, Args, CompSession, Arg, OptionResult
from tarina import lang

lang.set("completion", "node", "")
lang.set("completion", "prompt_select", "")


api_list = ["saucenao", "ascii2d", "ehentai", "iqdb", "tracemoe"]
alc = Alconna(
    "setu",
    Args['content', str],
    Option("use", Args['api', api_list], help_text="选择搜图使用的 API"),
    Option("count", Args(Arg("num", int)), help_text="设置每次搜图展示的最多数量"),
    Option("--similarity|-s", Args["val", float], help_text="设置相似度过滤的值", default=OptionResult(args={"val": 0.5})),
    Option("--timeout|-t", Args["sec", int], help_text="设置超时时间", default=OptionResult(args={"sec": 60})),
    meta=CommandMeta(
        "依据输入的图片寻找可能的原始图片来源",
        usage="可以传入图片, 也可以是图片的网络链接",
        example="setu搜索 [图片]",
    ),
)
interface = CompSession(alc)

with interface:
    res = alc.parse(input(">>> "))
while interface.available:
    print("---------------------------------------------------")
    print(interface)
    print("---------------------------------------------------")
    print(".enter to confirm, .tab to switch, ctrl+c to cancel")
    print("---------------------------------------------------")
    while True:
        cmd = input(">>> ")
        if cmd in (".exit", ".quit", ".q"):
            print("exit.")
            exit(0)
        if cmd == ".tab":
            print(interface.tab())
        elif cmd.startswith(".enter"):
            _res = interface.enter(None)
            if _res.result:
                res = _res.result
            elif _res.exception:
                print(_res.exception)
            break
        else:
            _res = interface.enter([cmd])
            if _res.result:
                res = _res.result
            elif _res.exception:
                print(_res.exception)
            break
print(res.matched)
print(res.all_matched_args)
