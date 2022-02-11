import time
from arclet.alconna import Alconna, Option, Arpamar, Args, AnyParam


class Plain:
    type = "Plain"
    text: str

    def __init__(self, t: str):
        self.text = t


class At:
    type = "At"
    target: int

    def __init__(self, t: int):
        self.target = t


a = Arpamar()
ping = Alconna(
    headers=["."],
    command="test",
    options=[
        Option('--foo', Args["bar":AnyParam])
    ]
)

msg = [Plain(".test"), Plain(" --foo"), At(124)]
count = 10000

if __name__ == "__main__":
    st = time.time()

    for _ in range(count):
        ping.analyse_message(msg)
    ed = time.time()
    print(f"Alconna: {count / (ed - st):.2f}msg/s")
