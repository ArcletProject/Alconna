import time
from arclet.alconna import Alconna, Arg, AnyOne, argv_config
import cProfile
import pstats


class Plain:
    type = "Plain"
    text: str

    def __init__(self, t: str):
        self.text = t

    def __repr__(self):
        return self.text


class At:
    type = "At"
    target: int

    def __init__(self, t: int):
        self.target = t

    def __repr__(self):
        return f"At:{self.target}"

argv_config(
    to_text=lambda x: x.text if x.__class__ is Plain else None
)
alc = Alconna(
    ["."],
    "test",
    Arg("bar", AnyOne)
)

argv = alc.argv
analyser = alc.analyser
print(alc)
msg = [Plain(".test"), At(124)]
count = 20000

if __name__ == "__main__":

    sec = 0.0
    for _ in range(count):
        st = time.perf_counter()
        argv.build(msg)
        analyser.process(argv)
        sec += time.perf_counter() - st
    print(f"Alconna: {count / sec:.2f}msg/s")

    print("RUN 2:")
    li = 0.0

    for _ in range(count):
        st = time.thread_time_ns()
        argv.build(msg)
        analyser.process(argv)
        li += (time.thread_time_ns() - st)

    print(f"Alconna: {li / count} ns per loop with {count} loops")

    prof = cProfile.Profile()
    prof.enable()
    for _ in range(count):
        argv.build(msg)
        analyser.process(argv)
    prof.create_stats()

    stats = pstats.Stats(prof)
    stats.strip_dirs()
    stats.sort_stats('tottime')
    stats.print_stats(20)