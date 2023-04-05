from arclet.alconna import Alconna, Option, Subcommand, Args, CompInterface

alc = Alconna(
    "setting",
    Option("add"),
    Subcommand("group", Args["name", int]),

)
interface = CompInterface(alc)

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
                res = interface.enter(content)
            break
        else:
            print(interface.current())
print(res.matched)
print(res.all_matched_args)
