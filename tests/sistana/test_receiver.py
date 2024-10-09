from __future__ import annotations

from elaina_segment import Buffer

from arclet.alconna.sistana import Fragment, SubcommandPattern
from arclet.alconna.sistana.model.receiver import AccumRx, ConstRx, CountRx

from .asserts import analyze


def test_accumrx():
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", receiver=AccumRx()), allow_duplicate=True)

    a, sn, bf = analyze(pat, Buffer(["test --name hello --name world"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    frag.expect_value(["hello", "world"])


def test_countrx():
    pat = SubcommandPattern.build("test")
    pat.option("--name", allow_duplicate=True, header_fragment=Fragment("name", receiver=CountRx()))

    a, sn, bf = analyze(pat, Buffer(["test --name --name"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"].header
    frag.expect_assigned()
    frag.expect_value(2)


def test_constrx():
    pat = SubcommandPattern.build("test")
    pat.option("--name", header_fragment=Fragment("name", receiver=ConstRx("hello")))

    a, sn, bf = analyze(pat, Buffer(["test --name"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"].header
    frag.expect_assigned()
    frag.expect_value("hello")
