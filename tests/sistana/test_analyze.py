from __future__ import annotations

from arclet.alconna.sistana import SubcommandPattern, Fragment
from elaina_segment import Buffer

from arclet.alconna.sistana.analyzer import LoopflowExitReason

from .asserts import analyze


def test_analyze_simple():
    pattern = SubcommandPattern.build("test")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test"]),
    )
    a.expect_completed()

    sn.expect_determined()
    sn.expect_endpoint("test")

    sn.mix["test",].expect_emitted()
    bf.expect_empty()


def test_analyze_slots():
    pattern = SubcommandPattern.build("test", Fragment("name"))

    a, sn, bf = analyze(pattern, Buffer(["test hello"]))
    a.expect_completed()
    bf.expect_empty()

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    frag_name = track_test["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("hello")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test"]),
    )
    a.expect(LoopflowExitReason.unsatisfied)
    bf.expect_empty()

    sn.expect_determined(False)
    
    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied(False)

    frag_name = track_test["name"]
    frag_name.expect_assigned(False)

def test_analyze_option():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name hello"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("test")

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    track_opt_name = sn.mix[("test",), "--name"]
    track_opt_name.expect_emitted()
    track_opt_name.expect_satisfied()

    frag_name = track_opt_name["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("hello")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test"]),
    )
    a.expect(LoopflowExitReason.unsatisfied)

    sn.expect_determined(False)

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied(True)

    track_opt_name = sn.mix[("test",), "--name"]
    track_opt_name.expect_emitted(False)
    track_opt_name.expect_satisfied(False)

    frag_name = track_opt_name["name"]
    frag_name.expect_assigned(False)

def test_analyze_option_unsatisfied():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name"]),
    )
    a.expect(LoopflowExitReason.unsatisfied)
    bf.expect_empty()

    sn.expect_determined(False)

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied(True)

    track_opt_name = sn.mix[("test",), "--name"]
    track_opt_name.expect_emitted()
    track_opt_name.expect_satisfied(False)

    frag_name = track_opt_name["name"]
    frag_name.expect_assigned(False)