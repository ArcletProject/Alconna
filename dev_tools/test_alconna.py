import time
from devtools import debug
from graia.ariadne.message.parser.twilight import Twilight, Sparkle, WildcardMatch, FullMatch
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import At
from arclet.alconna import Alconna, Option, Arpamar, Subcommand, Args
from arclet.alconna.types import AnyStr, AnyDigit, AnyUrl

a = Arpamar()
ping = Alconna(
    headers=["."],
    command="test",
    options=[
        Option('--foo', Args["bar":At:At(123)])
    ]
)

pip = Alconna(
        command="/pip",
        options=[
            Option("--timeout", Args["foo":AnyDigit]).help("设置超时时间"),
        ]
    ).help("pip指令")

twi = Twilight(Sparkle([FullMatch(".test"), WildcardMatch()]))
msg = MessageChain.create(".test", " --foo", At(123))
msg1 = MessageChain.create("/pip --timeout 6")
count = 10000

if __name__ == "__main__":
    debug(ping.analyse_message(msg))
    st = time.time()
    for _ in range(count):
        ping.analyse_message(msg)
    ed = time.time()
    print(f"Alconna: {count / (ed - st):.2f}msg/s")

    # debug(twi.gen_sparkle(msg))
    st = time.time()
    for _ in range(count):
        twi.generate(msg)
    ed = time.time()
    print(f"Twilight: {count / (ed - st):.2f}msg/s")
