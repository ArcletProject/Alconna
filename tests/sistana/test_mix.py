from __future__ import annotations

from elaina_segment import Buffer

from arclet.alconna.sistana import Fragment, SubcommandPattern
from arclet.alconna.sistana.model.receiver import Rx
from arclet.alconna.sistana.some import Value

from .asserts import analyze


def test_assignable():
    pat = SubcommandPattern.build("test", Fragment("arg1"), Fragment("arg2", default=Value("default")))

    a, sn, bf = analyze(pat, Buffer(["test n hello"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",)]["arg1"]
    frag.expect_assigned()
    frag.expect_value("n")

    frag = sn.mix[("test",)]["arg2"]
    frag.expect_assigned()
    frag.expect_value("hello")

    track = sn.mix[("test",)]
    track.expect_assignable(False)

    a, sn, bf = analyze(pat, Buffer(["test n"]))
    a.expect_completed()

    frag = sn.mix[("test",)]["arg1"]
    frag.expect_assigned()
    frag.expect_value("n")

    frag = sn.mix[("test",)]["arg2"]
    frag.expect_assigned()
    frag.expect_value("default")

    track = sn.mix[("test",)]
    track.expect_assignable(True)


def test_header_edge_case():
    class DoNothingRx(Rx):
        def receive(self, fetch, prev, put): ...

    pat = SubcommandPattern.build(
        "test", header_fragment=Fragment("arg1", receiver=DoNothingRx(), default=Value("default"))
    )

    a, sn, bf = analyze(pat, Buffer(["test"]))
    a.expect_completed()

    track = sn.mix["test",]
    track.expect_emitted()

    frag = sn.mix["test",].header
    frag.expect_assigned()
    frag.expect_value("default")


def test_variadic():
    pat = SubcommandPattern.build("test", Fragment("arg1"), Fragment("arg2", variadic=True))

    a, sn, bf = analyze(pat, Buffer(["test n hello world"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",)]["arg1"]
    frag.expect_assigned()
    frag.expect_value("n")

    frag = sn.mix[("test",)]["arg2"]
    frag.expect_assigned()
    frag.expect_value(["hello", "world"])

    a, sn, bf = analyze(pat, Buffer(["test n"]))
    a.expect_completed()

    frag = sn.mix[("test",)]["arg1"]
    frag.expect_assigned()
    frag.expect_value("n")

    frag = sn.mix[("test",)]["arg2"]
    frag.expect_assigned()
    frag.expect_value([])
