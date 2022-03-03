import time
from arclet.alconna import Alconna, Option, Arpamar, Args, AnyParam, compile


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
    main_args=Args["bar":AnyParam]
)
s_ping = compile(ping)

msg = [Plain(".test"), At(124)]
count = 10000

if __name__ == "__main__":
    st = time.process_time()

    for _ in range(count):
        s_ping.analyse(msg)
    ed = time.process_time()
    print(f"Alconna: {count / (ed - st):.2f}msg/s")
