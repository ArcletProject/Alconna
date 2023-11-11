import time
from arclet.alconna import Alconna, Option, Args, command_manager
import cProfile
import pstats

alc = Alconna(
    "test",
    Option("--foo", Args["f", str]),
    Option("--bar", Args["b", str]),
    Option("--baz", Args["z", str]),
    Option("--qux", Args["q", str]),
)

argv = command_manager.resolve(alc)
analyser = command_manager.require(alc)
msg = ["test --qux 123"]

print(alc.parse(msg))
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
    stats.print_stats(40)
