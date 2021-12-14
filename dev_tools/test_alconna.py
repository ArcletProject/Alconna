import time
from devtools import debug
from graia.ariadne.message.parser.pattern import WildcardMatch, FullMatch
from graia.ariadne.message.parser.twilight import Twilight, Sparkle
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import At

from arclet.alconna import Alconna, Option

ping = Alconna(
    headers=["."],
    command="test",
    options=[
        Option('--foo', bar=At)
    ]
)
twi = Twilight(Sparkle([FullMatch(".test"), WildcardMatch()]))
msg = MessageChain.create(".test", " --foo", At(123))
count = 10000

if __name__ == "__main__":
    debug(ping.analyse_message(msg))
    st = time.time()
    for _ in range(count):
        ping.analyse_message(msg)
    ed = time.time()
    print(f"Alconna: {count / (ed - st):.2f}msg/s")

    debug(twi.gen_sparkle(msg))
    st = time.time()
    for _ in range(count):
        twi.gen_sparkle(msg)
    ed = time.time()
    print(f"Twilight: {count / (ed - st):.2f}msg/s")
