from __future__ import annotations

import re

import pytest
from elaina_segment import Buffer

from arclet.alconna.sistana import Fragment, SubcommandPattern
from arclet.alconna.sistana.err import RegexMismatch, UnexpectedType
from arclet.alconna.sistana.model.capture import ObjectCapture, PlainCapture, RegexCapture

from .asserts import analyze


def test_object_capture():
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", capture=ObjectCapture(int)))

    a, sn, bf = analyze(pat, Buffer(["test --name", 1]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    frag.expect_value(1)

    with pytest.raises(UnexpectedType, match=f"Expected {int}, got {str}"):
        a, sn, bf = analyze(pat, Buffer(["test --name 1"]))


def test_plain_capture():
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", capture=PlainCapture()))

    a, sn, bf = analyze(pat, Buffer(["test --name hello"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    frag.expect_value("hello")

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got {int}"):
        # Quoted
        a, sn, bf = analyze(pat, Buffer(["test --name '", 1, "'"]))

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got {int}"):
        # UnmatchedQuoted
        a, sn, bf = analyze(pat, Buffer(["test --name '", 1]))

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got {int}"):
        a, sn, bf = analyze(pat, Buffer(["test --name", 1]))

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got {int}"):
        # raise for first segment that is not string
        a, sn, bf = analyze(pat, Buffer(["test --name '123", 2]))


def test_regex_capture():
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", capture=RegexCapture(r"\d+")))

    a, sn, bf = analyze(pat, Buffer(["test --name 123"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    assert isinstance(frag.value, re.Match)
    assert frag.value.group() == "123"

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got 1"):
        a, sn, bf = analyze(pat, Buffer(["test --name", 1]))

    with pytest.raises(RegexMismatch):
        a, sn, bf = analyze(pat, Buffer(["test --name abc"]))

    with pytest.raises(UnexpectedType, match=f"Expected {str}, got .*"):
        # reason: match_quote = False
        a, sn, bf = analyze(pat, Buffer(["test --name '123", 2]))

    # tail
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", capture=RegexCapture(r"123")), Fragment("tail"))

    a, sn, bf = analyze(pat, Buffer(["test --name 123345"]))
    a.expect_completed()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    assert isinstance(frag.value, re.Match)
    assert frag.value.group() == "123"

    frag = sn.mix[("test",), "--name"]["tail"]
    frag.expect_assigned()
    frag.expect_value("345")

    # match_quote
    pat = SubcommandPattern.build("test")
    pat.option("--name", Fragment("name", capture=RegexCapture(r"123", match_quote=True)))

    a, sn, bf = analyze(pat, Buffer(["test --name '123'"]))
    a.expect_completed()

    frag = sn.mix[("test",), "--name"]["name"]
    frag.expect_assigned()
    assert isinstance(frag.value, re.Match)
    assert frag.value.group() == "123"

    with pytest.raises(UnexpectedType):
        a, sn, bf = analyze(pat, Buffer(["test --name '123", 1]))