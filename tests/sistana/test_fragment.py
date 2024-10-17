import pytest
from elaina_segment import Buffer

from arclet.alconna.sistana.fragment import Fragment
from arclet.alconna.sistana.model.fragment import _Fragment, assert_fragments_order
from arclet.alconna.sistana.model.pattern import SubcommandPattern
from arclet.alconna.sistana.some import Value

from .asserts import analyze


def test_assert_fragments_order_valid():
    fragments = [
        _Fragment(name="frag1"),
        _Fragment(name="frag2", default=Value("default")),
        _Fragment(name="frag3", variadic=True),
    ]
    assert_fragments_order(fragments)


def test_assert_fragments_order_required_after_optional():
    fragments = [_Fragment(name="frag1", default=Value("default")), _Fragment(name="frag2")]
    with pytest.raises(ValueError, match="Found a required fragment after an optional fragment, which is not allowed."):
        assert_fragments_order(fragments)


def test_assert_fragments_order_variadic_with_default():
    fragments = [_Fragment(name="frag1", variadic=True, default=Value("default"))]
    with pytest.raises(ValueError, match="A variadic fragment cannot have a default value."):
        assert_fragments_order(fragments)


def test_assert_fragments_order_fragment_after_variadic():
    fragments = [_Fragment(name="frag1", variadic=True), _Fragment(name="frag2")]
    with pytest.raises(ValueError, match="Found fragment after a variadic fragment, which is not allowed."):
        assert_fragments_order(fragments)


def test_nepattern():
    from nepattern import WIDE_BOOLEAN

    pat = SubcommandPattern.build("test")

    pat.option("--foo", Fragment("foo", type=Value(int)))
    pat.option("--bar", Fragment("bar", type=Value(float)))
    pat.option("--baz", Fragment("baz", type=Value(bool)))
    pat.option("--qux", Fragment("qux").apply_nepattern(WIDE_BOOLEAN))

    a, sn, bf = analyze(pat, Buffer(["test --foo 123 --bar 123.456 --baz true --qux yes"]))
    a.expect_completed()
    sn.expect_determined()

    frag = sn.mix[("test",), "--foo"]["foo"]
    frag.expect_assigned()
    frag.expect_value(123)

    frag = sn.mix[("test",), "--bar"]["bar"]
    frag.expect_assigned()
    frag.expect_value(123.456)

    frag = sn.mix[("test",), "--baz"]["baz"]
    frag.expect_assigned()
    frag.expect_value(True)

    frag = sn.mix[("test",), "--qux"]["qux"]
    frag.expect_assigned()
    frag.expect_value(True)
