import time
from arclet.alconna import Alconna, Args, AnyOne, compile, command_manager, config
import cProfile
import pstats


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


alc = Alconna(
    headers=["."],
    command="test",
    main_args=Args["bar", AnyOne]
)
compile_alc = compile(alc)

msg = [Plain(".test"), At(124)]
count = 20000

config.enable_message_cache = True

if __name__ == "__main__":

    sec = 0.0
    for _ in range(count):
        st = time.time()
        compile_alc.process(msg)
        compile_alc.analyse()
        ed = time.time()
        sec += ed - st
    print(f"Alconna: {count / sec:.2f}msg/s")

    print("RUN 2:")
    li = []

    pst = time.time()
    for _ in range(count):
        st = time.thread_time_ns()
        compile_alc.process(msg)
        compile_alc.analyse()
        ed = time.thread_time_ns()
        li.append(ed - st)
    led = time.time()

    print(f"Alconna: {sum(li) / count} ns per loop with {count} loops")

    command_manager.records.clear()

    prof = cProfile.Profile()
    prof.enable()
    for _ in range(count):
        compile_alc.process(msg)
        compile_alc.analyse()
    prof.create_stats()

    stats = pstats.Stats(prof)
    stats.strip_dirs()
    stats.sort_stats('tottime')
    stats.print_stats(20)
