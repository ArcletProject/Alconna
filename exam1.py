from arclet.alconna import Alconna, Option, Subcommand, Args, CompSession

alc = Alconna(
    "/pip",
    Subcommand(
        "install",
        Option("--upgrade", help_text="升级包"),
        Option("-i|--index-url", Args["url", "url"]),
        Args["pak", str],
        help_text="安装一个包",
    ),
    Option("--retries", Args["retries", int], help_text="设置尝试次数"),
    Option("-t|--timeout", Args["sec", int], help_text="设置超时时间"),
    Option("--exists-action", Args["action", str], help_text="添加行为"),
    Option("--trusted-host", Args["host", str], help_text="选择可信赖地址"),
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
            content = cmd[6:].lstrip()
            with interface:
                res = interface.enter([content] if content else None)
            break
        else:
            print(interface.current())
print(res.matched)
print(res.all_matched_args)
