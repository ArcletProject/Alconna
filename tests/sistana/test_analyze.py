from __future__ import annotations

from elaina_segment import Buffer

from arclet.alconna.sistana import Fragment, SubcommandPattern
from arclet.alconna.sistana.analyzer import LoopflowExitReason
from arclet.alconna.sistana.model.receiver import CountRx, Rx
from arclet.alconna.sistana.some import Value

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


def test_analyze_option_duplicated():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name hello --name world"]),
    )
    a.expect(LoopflowExitReason.option_duplicated_prohibited)
    bf.expect_empty()

    sn.expect_determined(False)

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied(True)

    track_opt_name = sn.mix[("test",), "--name"]
    track_opt_name.expect_emitted()
    track_opt_name.expect_satisfied(True)

    frag_name = track_opt_name["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("hello")

    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"), allow_duplicate=True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name hello --name world"]),
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
    frag_name.expect_value("world")


def test_prefix():
    pattern = SubcommandPattern.build("test", prefixes=[".", "//", "/?", "///"])

    a, sn, bf = analyze(
        pattern,
        Buffer(["hello"]),
    )
    a.expect(LoopflowExitReason.prefix_mismatch)
    bf.expect_empty()

    sn.expect_determined(False)

    track_test = sn.mix["test",]
    track_test.expect_emitted(False)
    track_test.expect_satisfied(True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["//test"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("test")

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    a, sn, bf = analyze(
        pattern,
        Buffer(["///test"]),
    )
    a.expect_completed()
    bf.expect_empty()

    a, sn, bf = analyze(
        pattern,
        Buffer([1, "test"]),
    )
    a.expect(LoopflowExitReason.prefix_expect_str)


def test_header():
    pattern = SubcommandPattern.build("test")

    a, sn, bf = analyze(
        pattern,
        Buffer(["hello"]),
    )
    a.expect(LoopflowExitReason.header_mismatch)

    a, sn, bf = analyze(
        pattern,
        Buffer([1]),
    )
    a.expect(LoopflowExitReason.header_expect_str)


def test_compact_header():
    pattern = SubcommandPattern.build("test", Fragment("tail"), compact_header=True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["test1"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("test")

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    frag_tail = track_test["tail"]
    frag_tail.expect_assigned()
    frag_tail.expect_value("1")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test 1"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("test")

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    frag_tail = track_test["tail"]
    frag_tail.expect_assigned()
    frag_tail.expect_value("1")


def test_subcommand():
    lp = SubcommandPattern.build("lp")
    lp_user = lp.subcommand("user", Fragment("name"))
    lp_user.subcommand("permission", Fragment("permission"))

    a, sn, bf = analyze(
        lp,
        Buffer(["lp user alice permission read"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("lp", "user", "permission")

    track_lp = sn.mix["lp",]
    track_lp.expect_emitted()
    track_lp.expect_satisfied()

    track_user = sn.mix["lp", "user"]
    track_user.expect_emitted()
    track_user.expect_satisfied()

    frag_name = track_user["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("alice")

    track_permission = sn.mix["lp", "user", "permission"]
    track_permission.expect_emitted()
    track_permission.expect_satisfied()

    frag_permission = track_permission["permission"]
    frag_permission.expect_assigned()
    frag_permission.expect_value("read")

    a, sn, bf = analyze(
        lp,
        Buffer(["lp user permission permission read"]),
    )
    a.expect(LoopflowExitReason.unsatisfied_switch_subcommand)

    lp = SubcommandPattern.build("lp")
    lp_user = lp.subcommand("user", Fragment("name"))
    lp_user.subcommand("permission", Fragment("permission"), soft_keyword=True)

    a, sn, bf = analyze(
        lp,
        Buffer(["lp user permission permission read"]),
    )
    a.expect_completed()


def test_subcommand_compact():
    pattern = SubcommandPattern.build("test")
    pattern.subcommand("add", Fragment("tail"), compact_header=True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["test add1"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("test", "add")

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    track_add = sn.mix["test", "add"]
    track_add.expect_emitted()
    track_add.expect_satisfied()

    frag_tail = track_add["tail"]
    frag_tail.expect_assigned()
    frag_tail.expect_value("1")


def test_option_compact():
    pattern = SubcommandPattern.build("mysql")
    pattern.option("-u", Fragment("username"), compact_header=True)
    pattern.option("-p", Fragment("password"), compact_header=True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["mysql -uroot -ppassword"]),
    )
    a.expect_completed()
    bf.expect_empty()

    sn.expect_determined()
    sn.expect_endpoint("mysql")

    track_mysql = sn.mix["mysql",]
    track_mysql.expect_emitted()
    track_mysql.expect_satisfied()

    track_u = sn.mix[("mysql",), "-u"]
    track_u.expect_emitted()
    track_u.expect_satisfied()

    frag_username = track_u["username"]
    frag_username.expect_assigned()
    frag_username.expect_value("root")

    track_p = sn.mix[("mysql",), "-p"]
    track_p.expect_emitted()
    track_p.expect_satisfied()

    frag_password = track_p["password"]
    frag_password.expect_assigned()
    frag_password.expect_value("password")


def test_switch_from_option():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))
    pattern.option("--age", Fragment("age"))
    pattern.subcommand("add", Fragment("tail"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name alice --age 18 add bob"]),
    )
    a.expect_completed()
    bf.expect_empty()
    sn.expect_determined()
    sn.expect_endpoint("test", "add")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name add alice"]),
    )
    a.expect(LoopflowExitReason.unsatisfied_switch_option)

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name --age 20 add bob"]),
    )
    a.expect(LoopflowExitReason.previous_unsatisfied)

    # unless option keyword is soft

    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))
    pattern.option("--age", Fragment("age"), soft_keyword=True)
    pattern.subcommand("add", Fragment("tail"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name --age --age 12"]),
    )
    a.expect_completed()
    bf.expect_empty()

    # switch to subcommand and subcommand keyword is soft

    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))
    pattern.subcommand("add", Fragment("tail"), soft_keyword=True)

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name add add alice"]),
    )
    a.expect_completed()
    bf.expect_empty()

    track_test = sn.mix["test",]
    track_test.expect_emitted()
    track_test.expect_satisfied()

    track_add = sn.mix["test", "add"]
    track_add.expect_emitted()
    track_add.expect_satisfied()

    frag_tail = track_add["tail"]
    frag_tail.expect_assigned()
    frag_tail.expect_value("alice")

    track_name = sn.mix[("test",), "--name"]

    frag_name = track_name["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("add")


def test_unexpected_segment():
    pattern = SubcommandPattern.build("test", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test alice bob"]),
    )
    a.expect(LoopflowExitReason.unexpected_segment)
    bf.expect_empty()

    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name alice bob"]),
    )
    a.expect(LoopflowExitReason.unexpected_segment)
    bf.expect_empty()

    # but name is alice.
    track_name = sn.mix[("test",), "--name"]
    frag_name = track_name["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("alice")


def test_determined_and_exit():
    pattern = SubcommandPattern.build("test", Fragment("name"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test alice bob"]),
        complete_on_determined=True,
    )
    a.expect_completed()
    bf.expect_non_empty()


def test_header_separator():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"), header_separators="=")

    a, sn, bf = analyze(
        pattern,
        Buffer(["test --name=alice"]),
    )
    a.expect_completed()
    bf.expect_empty()

    track_name = sn.mix[("test",), "--name"]
    frag_name = track_name["name"]
    frag_name.expect_assigned()
    frag_name.expect_value("alice")


def test_stage_unsatisfied():
    pattern = SubcommandPattern.build("test")
    pattern.option("--name", Fragment("name"), forwarding=False)
    pattern.subcommand("add", Fragment("tail"))

    a, sn, bf = analyze(
        pattern,
        Buffer(["test add 111"]),
    )
    a.expect(LoopflowExitReason.unsatisfied_switch_subcommand)
    bf.expect_empty()


def test_header_fragment():
    class LengthRx(Rx):
        def receive(self, fetch, prev, put) -> None:
            le = len(fetch())
            n = prev()
            if n is not None:
                n = n.value
            else:
                n = 0

            put(le + n)

    pat = SubcommandPattern.build("test")
    pat.option(
        "-t",
        Fragment(
            "verbose_level",
            receiver=LengthRx(),
            default=Value(0),
        ),
        header_fragment=Fragment(
            "verbose_level",
            default=Value(0),
            receiver=CountRx(),
        ),
        allow_duplicate=True,
        compact_header=True,
    )

    a, sn, bf = analyze(
        pat,
        Buffer(["test -t"]),  # verbose_level = 1
    )
    a.expect_completed()
    bf.expect_empty()

    frag_verbose_level = sn.mix[("test",), "-t"]["verbose_level"]
    frag_verbose_level.expect_assigned()
    frag_verbose_level.expect_value(1)

    a, sn, bf = analyze(
        pat,
        Buffer(["test -t -t"]),
    )
    a.expect_completed()
    bf.expect_empty()

    frag_verbose_level = sn.mix[("test",), "-t"]["verbose_level"]
    frag_verbose_level.expect_assigned()
    frag_verbose_level.expect_value(2)

    a, sn, bf = analyze(
        pat,
        Buffer(["test -tt"]),
    )
    a.expect_completed()
    bf.expect_empty()

    frag_verbose_level = sn.mix[("test",), "-t"]["verbose_level"]
    frag_verbose_level.expect_assigned()
    frag_verbose_level.expect_value(2)

    a, sn, bf = analyze(
        pat,
        Buffer(["test -t -tt"]),
    )
    a.expect_completed()
    bf.expect_empty()

    frag_verbose_level = sn.mix[("test",), "-t"]["verbose_level"]
    frag_verbose_level.expect_assigned()
    frag_verbose_level.expect_value(3)

    a, sn, bf = analyze(
        pat,
        Buffer(["test -tttttttttttttttttttt"]),
    )
    a.expect_completed()
    bf.expect_empty()

    frag_verbose_level = sn.mix[("test",), "-t"]["verbose_level"]
    frag_verbose_level.expect_assigned()
    frag_verbose_level.expect_value(20)
