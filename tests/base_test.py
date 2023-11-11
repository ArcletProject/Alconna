from arclet.alconna.args import Arg, Args
from arclet.alconna.base import CommandNode, Option, Subcommand
from arclet.alconna.model import OptionResult, SubcommandResult
from devtool import analyse_option, analyse_subcommand


def test_node_create():
    node = CommandNode("foo", Args["bar", int], dest="test")
    assert node.name == "foo"
    assert node.dest != "foo"
    assert node.nargs == 1


def test_single_args():
    node1 = CommandNode("foo", Arg("bar", int))
    assert node1.args == Args["bar", int]


def test_node_requires():
    node2 = CommandNode("foo", requires=["baz", "qux"])
    assert node2.dest == "baz_qux_foo"
    node2_1 = CommandNode("baz qux foo")
    assert node2_1.name == "foo"
    assert node2_1.requires == ["baz", "qux"]


def test_option_aliases():
    opt = Option("test|T|t")
    assert opt.aliases == {"test", "T", "t"}
    opt_1 = Option("test", alias=["T", "t"])
    assert opt_1.aliases == {"test", "T", "t"}
    assert opt == opt_1
    assert opt == Option("T|t|test")


def test_option_requires():
    opt1 = Option("foo bar test|T|t")
    assert opt1.aliases == {"test", "T", "t"}
    assert opt1.requires == ["foo", "bar"]
    opt1_1 = Option("foo bar test| T | t")
    assert opt1_1.aliases != {"test", "T", "t"}


def test_separator():
    opt2 = Option("foo", Args["bar", int], separators="|")
    assert analyse_option(opt2, "foo|123") == OptionResult(None, {"bar": 123})
    opt2_1 = Option("foo", Args["bar", int]).separate("|")
    assert opt2 == opt2_1


def test_subcommand():
    sub = Subcommand("test", Option("foo"), Option("bar"))
    assert len(sub.options) == 2
    assert analyse_subcommand(sub, "test foo") == SubcommandResult(None, {}, {"foo": OptionResult()})


def test_compact():
    opt3 = Option("-Foo", Args["bar", int], compact=True)
    assert analyse_option(opt3, "-Foo123") == OptionResult(None, {"bar": 123})


def test_add():
    assert (Option("abcd") + Args["foo", int]).nargs == 1
    assert len((Option("foo") + Option("bar") + "baz").options) == 2


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
