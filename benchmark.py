import cProfile
import pstats
import time

from arclet.alconna import ANY, Alconna, Args, command_manager, namespace


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


with namespace("test") as np:
    np.to_text = lambda x: x.text if x.__class__ is Plain else None
    alc = Alconna(
        ["."],
        "test",
        Args["bar", ANY]
    )

analyser = command_manager.require(alc)
argv = analyser.argv
print(alc)
msg = [Plain(".test"), At(124)]
count = 20000

if __name__ == "__main__":

    sec = 0.0
    for _ in range(count):
        st = time.perf_counter()
        argv.build(msg)
        analyser.process(argv)
        analyser.reset()
        sec += time.perf_counter() - st
    print(f"Alconna: {count / sec:.2f}msg/s")

    print("RUN 2:")
    li = 0.0

    for _ in range(count):
        st = time.thread_time_ns()
        argv.build(msg)
        analyser.process(argv)
        analyser.reset()
        li += (time.thread_time_ns() - st)

    print(f"Alconna: {li / count} ns per loop with {count} loops")

    command_manager.records.clear()

    prof = cProfile.Profile()
    prof.enable()
    for _ in range(count):
        argv.build(msg)
        analyser.process(argv)
        analyser.reset()
    prof.create_stats()

    stats = pstats.Stats(prof)
    stats.strip_dirs()
    stats.sort_stats('tottime')
    stats.print_stats(40)
