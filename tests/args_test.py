from typing import Union

from nepattern import BasePattern, MatchMode, INTEGER, combine

from arclet.alconna import ArgFlag, Args, KeyWordVar, Kw, Nargs
from devtool import analyse_args


def test_magic_create():
    arg1 = Args["round", float]["test", bool]["aaa", str]
    assert len(arg1) == 3
    arg1 <<= Args["perm", str, ...] + ["month", int]
    assert len(arg1) == 5
    arg11: Args = Args["baz", int]
    arg11.add("foo", value=int, default=1)
    assert len(arg11) == 2


def test_type_convert():
    arg2 = Args["round", float]["test", bool]
    assert analyse_args(arg2, ["1.2 False"]) != {"round": "1.2", "test": "False"}
    assert analyse_args(arg2, ["1.2 False"]) == {"round": 1.2, "test": False}
    assert analyse_args(arg2, ["a False"], raise_exception=False) != {
        "round": "a",
        "test": False,
    }


def test_regex():
    arg3 = Args["foo", "re:abc[0-9]{3}"]
    assert analyse_args(arg3, ["abc123"]) == {"foo": "abc123"}
    assert analyse_args(arg3, ["abc"], raise_exception=False) != {"foo": "abc"}


def test_string():
    arg4 = Args["foo"]["bar"]
    assert analyse_args(arg4, ["foo bar"]) == {"foo": "foo", "bar": "bar"}


def test_default():
    arg5 = Args["foo", int]["de", bool, True]
    assert analyse_args(arg5, ["123 False"]) == {"foo": 123, "de": False}
    assert analyse_args(arg5, ["123"]) == {"foo": 123, "de": True}


def test_separate():
    arg6 = Args["foo", str]["bar", int] / ";"
    assert analyse_args(arg6, ["abc;123"]) == {"foo": "abc", "bar": 123}


def test_object():
    arg7 = Args["foo", str]["bar", 123]
    assert analyse_args(arg7, ["abc", 123]) == {"foo": "abc", "bar": 123}
    assert analyse_args(arg7, ["abc", 124], raise_exception=False) != {
        "foo": "abc",
        "bar": 124,
    }


def test_multi():
    arg8 = Args().add("multi", value=Nargs(str, "+"))
    assert analyse_args(arg8, ["a b c d"]).get("multi") == ("a", "b", "c", "d")
    assert analyse_args(arg8, [], raise_exception=False) != {"multi": ()}
    arg8_1 = Args().add("kwargs", value=Nargs(Kw @ str, "+"))
    assert analyse_args(arg8_1, ["a=b c=d"]).get("kwargs") == {"a": "b", "c": "d"}
    arg8_2 = Args().add("multi", value=Nargs(int, "*"))
    assert analyse_args(arg8_2, ["1 2 3 4"]).get("multi") == (1, 2, 3, 4)
    assert analyse_args(arg8_2, []).get("multi") == ()
    arg8_3 = Args().add("multi", value=Nargs(int, 3))
    assert analyse_args(arg8_3, ["1 2 3"]).get("multi") == (1, 2, 3)
    assert analyse_args(arg8_3, ["1 2"]).get("multi") == (1, 2)
    assert analyse_args(arg8_3, ["1 2 3 4"]).get("multi") == (1, 2, 3)
    arg8_4 = Args().add("multi", value=Nargs(str, "*")).add("kwargs", value=Nargs(Kw @ str, "*"))
    assert analyse_args(arg8_4, ["1 2 3 4 a=b c=d"]).get("multi") == ("1", "2", "3", "4")
    assert analyse_args(arg8_4, ["1 2 3 4 a=b c=d"]).get("kwargs") == {
        "a": "b",
        "c": "d",
    }
    assert analyse_args(arg8_4, ["1 2 3 4"]).get("multi") == ("1", "2", "3", "4")
    assert analyse_args(arg8_4, ["a=b c=d"]).get("kwargs") == {"a": "b", "c": "d"}


def test_anti():
    arg9 = Args().add("anti", value=r"re:(.+?)/(.+?)\.py", flags=[ArgFlag.ANTI])
    assert analyse_args(arg9, ["a/b.mp3"]) == {"anti": "a/b.mp3"}
    assert analyse_args(arg9, ["a/b.py"], raise_exception=False) != {"anti": "a/b.py"}


def test_choice():
    arg10 = Args["choice", ("a", "b", "c")]
    assert analyse_args(arg10, ["a"]) == {"choice": "a"}
    assert analyse_args(arg10, ["d"], raise_exception=False) != {"choice": "d"}
    arg10_1 = Args["mapping", {"a": 1, "b": 2, "c": 3}]
    assert analyse_args(arg10_1, ["a"]) == {"mapping": 1}
    assert analyse_args(arg10_1, ["d"], raise_exception=False) != {"mapping": "d"}


def test_union():
    arg11 = Args["bar", Union[int, float]]
    assert analyse_args(arg11, ["1.2"]) == {"bar": 1.2}
    assert analyse_args(arg11, ["1"]) == {"bar": 1}
    assert analyse_args(arg11, ["abc"], raise_exception=False) != {"bar": "abc"}
    arg11_1 = Args["bar", [int, float, "abc"]]
    assert analyse_args(arg11_1, ["1.2"]) == analyse_args(arg11, ["1.2"])
    assert analyse_args(arg11_1, ["abc"]) == {"bar": "abc"}
    assert analyse_args(arg11_1, ["cba"], raise_exception=False) != {"bar": "cba"}


def test_optional():
    arg13 = Args["foo", str].add("bar", value=int, flags=["?"])
    assert analyse_args(arg13, ["abc 123"]) == {"foo": "abc", "bar": 123}
    assert analyse_args(arg13, ["abc"]) == {"foo": "abc"}
    arg13_1 = Args["foo", str]["bar?", int]
    assert analyse_args(arg13_1, ["abc 123"]) == {"foo": "abc", "bar": 123}
    assert analyse_args(arg13_1, ["abc"]) == {"foo": "abc"}
    arg13_2 = Args["foo", str]["bar;?", int]
    assert analyse_args(arg13_2, ["abc 123"]) == {"foo": "abc", "bar": 123}
    assert analyse_args(arg13_2, ["abc"]) == {"foo": "abc"}


def test_kwonly():
    arg14 = Args["foo", str].add("bar", value=Kw[int])
    assert analyse_args(arg14, ["abc bar=123"]) == {
        "foo": "abc",
        "bar": 123,
    }
    assert analyse_args(arg14, ["abc 123"], raise_exception=False) != {
        "foo": "abc",
        "bar": 123,
    }
    arg14_1 = Args["width;?", Kw[int], 1280]["height?", Kw[int], 960]
    assert analyse_args(arg14_1, ["--width=960 --height=960"]) == {
        "width": 960,
        "height": 960,
    }
    assert analyse_args(arg14_1, ["--height=480 --width=960"]) == {
        "width": 960,
        "height": 480,
    }
    arg14_2 = Args["foo", str]["bar", KeyWordVar(int, " ")]["baz", KeyWordVar(bool, ":")]
    assert analyse_args(arg14_2, ["abc -bar 123 baz:false"]) == {
        "bar": 123,
        "baz": False,
        "foo": "abc",
    }
    assert analyse_args(arg14_2, ["abc baz:false -bar 456"]) == {
        "bar": 456,
        "baz": False,
        "foo": "abc",
    }


def test_pattern():
    test_type = BasePattern("(.+?).py", MatchMode.REGEX_CONVERT, list, lambda _, x: x[1].split("/"), "test")
    arg15 = Args().add("bar", value=test_type)
    assert analyse_args(arg15, ["abc.py"]) == {"bar": ["abc"]}
    assert analyse_args(arg15, ["abc/def.py"]) == {"bar": ["abc", "def"]}
    assert analyse_args(arg15, ["abc/def.mp3"], raise_exception=False) != {"bar": ["abc", "def"]}


def test_callable():
    def test(
        a: int,
        b: bool,
        *args: str,
        c: float = 1.0,
        d: int = 1,
        e: bool = False,
        **kwargs: str,
    ):
        ...

    arg16, _ = Args.from_callable(test)
    assert len(arg16.argument) == 7
    assert analyse_args(arg16, ["1 True 2 3 4 c=5.0 d=6 -no-e f=g h=i"]) == {
        "a": 1,
        "args": ("2", "3", "4"),
        "b": True,
        "c": 5.0,
        "d": 6,
        "e": False,
        "kwargs": {"f": "g", "h": "i"},
    }
    assert analyse_args(arg16, ["1 True 2 3 4 -no-e c=7.2 f=x h=y"]) == {
        "a": 1,
        "args": ("2", "3", "4"),
        "b": True,
        "c": 7.2,
        "d": 1,
        "e": False,
        "kwargs": {"f": "x", "h": "y"},
    }


def test_func_anno():
    from datetime import datetime

    def test(time: Union[int, str]) -> datetime:
        return datetime.fromtimestamp(time) if isinstance(time, int) else datetime.fromisoformat(time)

    arg17 = Args["time", test]
    assert analyse_args(arg17, ["1145-05-14"]) == {"time": datetime.fromisoformat("1145-05-14")}


def test_annotated():
    from typing_extensions import Annotated

    arg18 = Args["foo", Annotated[int, lambda x: x > 0]]["bar", combine(INTEGER, validators=[lambda x: x < 0])]
    assert analyse_args(arg18, ["123 -123"]) == {"foo": 123, "bar": -123}
    assert analyse_args(arg18, ["0 0"], raise_exception=False) != {"foo": 0, "bar": 0}


def test_unpack():
    from dataclasses import dataclass, field

    from arclet.alconna.typing import UnpackVar

    @dataclass
    class People:
        name: str
        age: int = field(default=16)

    arg19 = Args["people", UnpackVar(People)]
    assert analyse_args(arg19, ["alice", 16]) == {"people": People("alice", 16)}
    assert analyse_args(arg19, ["bob"]) == {"people": People("bob", 16)}
    arg19_1 = Args["people", UnpackVar(People, kw_only=True)].separate("&")
    assert analyse_args(arg19_1, ["name=alice&age=16"]) == {"people": People("alice", 16)}


def test_multi_multi():
    from arclet.alconna.typing import MultiVar

    arg20 = Args["foo", MultiVar(str)]["bar", MultiVar(int)]
    assert analyse_args(arg20, ["a b -- 1 2"]) == {"foo": ("a", "b"), "bar": (1, 2)}

    arg20_1 = Args["foo", MultiVar(int)]["bar", MultiVar(str)]
    assert analyse_args(arg20_1, ["1 2 -- a b"]) == {"foo": (1, 2), "bar": ("a", "b")}
    assert analyse_args(arg20_1, ["1 2 a b"]) == {"foo": (1, 2), "bar": ("a", "b")}


def test_contextval():
    arg21 = Args["foo", str]
    assert analyse_args(arg21, ["$(bar)"], context_style="parentheses", bar="baz") == {"foo": "baz"}
    assert analyse_args(arg21, ["{bar}"], context_style="parentheses", raise_exception=False, bar="baz") != {"foo": "baz"}

    assert analyse_args(arg21, ["{bar}"], context_style="bracket", bar="baz") == {"foo": "baz"}
    assert analyse_args(arg21, ["$(bar)"], context_style="bracket", raise_exception=False, bar="baz") != {"foo": "baz"}

    class A:
        class B:
            c = "baz"
            d = {"e": "baz"}

        b = B()

    assert analyse_args(arg21, ["$(a.b.c)"], context_style="parentheses", a=A()) == {"foo": "baz"}
    assert analyse_args(arg21, ["$(a.b.d.get(e))"], context_style="parentheses", a=A()) == {"foo": "baz"}

    arg21_1 = Args["foo", int]
    assert analyse_args(arg21_1, ["$(bar)"], context_style="parentheses", bar=123) == {"foo": 123}
    assert analyse_args(arg21_1, ["$(bar)"], context_style="parentheses", bar="123") == {"foo": 123}
    assert analyse_args(arg21_1, ["$(bar)"], context_style="parentheses", raise_exception=False, bar="baz") != {"foo": 123}


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
