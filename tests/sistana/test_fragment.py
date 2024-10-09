import pytest
from arclet.alconna.sistana.model.fragment import _Fragment, assert_fragments_order
from arclet.alconna.sistana.some import Value

def test_assert_fragments_order_valid():
    fragments = [
        _Fragment(name="frag1"),
        _Fragment(name="frag2", default=Value("default")),
        _Fragment(name="frag3", variadic=True)
    ]
    assert_fragments_order(fragments)

def test_assert_fragments_order_required_after_optional():
    fragments = [
        _Fragment(name="frag1", default=Value("default")),
        _Fragment(name="frag2")
    ]
    with pytest.raises(ValueError, match="Found a required fragment after an optional fragment, which is not allowed."):
        assert_fragments_order(fragments)

def test_assert_fragments_order_variadic_with_default():
    fragments = [
        _Fragment(name="frag1", variadic=True, default=Value("default"))
    ]
    with pytest.raises(ValueError, match="A variadic fragment cannot have a default value."):
        assert_fragments_order(fragments)

def test_assert_fragments_order_fragment_after_variadic():
    fragments = [
        _Fragment(name="frag1", variadic=True),
        _Fragment(name="frag2")
    ]
    with pytest.raises(ValueError, match="Found fragment after a variadic fragment, which is not allowed."):
        assert_fragments_order(fragments)