from typing import Union

from arclet.alconna import Args
from arclet.alconna.analysis.base import analyse_args
from arclet.alconna.typing import BasePattern, PatternModel, Bind


def test_kwargs_create():
    arg = Args(pak=str, upgrade=str)
    assert arg == Args.pak[str]["upgrade", str]
    assert analyse_args(arg, "arclet-alconna bar") == {"pak": "arclet-alconna", "upgrade": 'bar'}


def test_magic_create():
    arg1 = Args.round[float]["test", bool]["aaa", str]
    assert len(arg1) == 3
    arg1 = arg1 << Args.perm[str, ...] + ["month", int]
    assert len(arg1) == 5
    arg1["foo"] = ["bar", ...]
    assert len(arg1) == 6
    arg11: Args = Args.baz[int]
    arg11.add_argument("foo", value=int, default=1)
    assert len(arg11) == 2


def test_type_convert():
    arg2 = Args.round[float]["test", bool]
    assert analyse_args(arg2, "1.2 False") != {'round': '1.2', 'test': 'False'}
    assert analyse_args(arg2, "1.2 False") == {'round': 1.2, 'test': False}
    assert analyse_args(arg2, "a False", raise_exception=False) != {'round': 'a', 'test': False}


def test_regex():
    arg3 = Args.foo["abc[0-9]{3}"]
    assert analyse_args(arg3, "abc123") == {"foo": "abc123"}
    assert analyse_args(arg3, "abc", raise_exception=False) != {"foo": "abc"}


def test_string():
    arg4 = Args["foo"]["bar"]
    assert analyse_args(arg4, "foo bar") == {"foo": "foo", "bar": "bar"}


def test_default():
    arg5 = Args.foo[int]["de", bool, True]
    assert analyse_args(arg5, "123 False") == {"foo": 123, "de": False}
    assert analyse_args(arg5, "123") == {"foo": 123, "de": True}


def test_separate():
    arg6 = Args.foo[str]["bar", int] / ";"
    assert analyse_args(arg6, 'abc;123') == {'foo': 'abc', 'bar': 123}


def test_object():
    arg7 = Args.foo[str]["bar", 123]
    assert analyse_args(arg7, ['abc', 123]) == {'foo': 'abc', 'bar': 123}
    assert analyse_args(arg7, ['abc', 124], raise_exception=False) != {'foo': 'abc', 'bar': 124}


def test_multi():
    arg8 = Args().add_argument("multi", value=str, flags="S")
    assert analyse_args(arg8, "a b c d").get('multi') == ("a", "b", "c", "d")
    arg8_1 = Args().add_argument("kwargs", value=str, flags="W")
    assert analyse_args(arg8_1, "a=b c=d").get('kwargs') == {"a": "b", "c": "d"}


def test_anti():
    arg9 = Args().add_argument("anti", value=r"(.+?)/(.+?)\.py", flags="A")
    assert analyse_args(arg9, "a/b.mp3") == {"anti": "a/b.mp3"}
    assert analyse_args(arg9, "a/b.py", raise_exception=False) != {"anti": "a/b.py"}


def test_choice():
    arg10 = Args.choice[("a", "b", "c")]
    assert analyse_args(arg10, "a") == {"choice": "a"}
    assert analyse_args(arg10, "d", raise_exception=False) != {"choice": "d"}
    arg10_1 = Args.mapping[{"a": 1, "b": 2, "c": 3}]
    assert analyse_args(arg10_1, "a") == {"mapping": 1}
    assert analyse_args(arg10_1, "d", raise_exception=False) != {"mapping": "d"}


def test_union():
    arg11 = Args.bar[Union[int, float]]
    assert analyse_args(arg11, "1.2") == {"bar": 1.2}
    assert analyse_args(arg11, "1") == {"bar": 1}
    assert analyse_args(arg11, "abc", raise_exception=False) != {"bar": "abc"}
    arg11_1 = Args.bar[[int, float, "abc"]]
    assert analyse_args(arg11_1, "1.2") == analyse_args(arg11, "1.2")
    assert analyse_args(arg11_1, "abc") == {"bar": "abc"}
    assert analyse_args(arg11_1, "cba", raise_exception=False) != {"bar": "cba"}


def test_force():
    arg12 = Args.foo[str].add_argument("bar", value=bool, flags="F")
    assert analyse_args(arg12, ['123', True]) == {'bar': True, 'foo': '123'}
    assert analyse_args(arg12, ['123', 'True'], raise_exception=False) != {'bar': True, 'foo': '123'}


def test_optional():
    arg13 = Args.foo[str].add_argument("bar", value=int, flags="O")
    assert analyse_args(arg13, 'abc 123') == {'foo': 'abc', 'bar': 123}
    assert analyse_args(arg13, 'abc') == {'foo': 'abc'}


def test_kwonly():
    arg14 = Args.foo[str].add_argument("bar", value=int, flags="K")
    assert analyse_args(arg14, 'abc bar=123') == {'foo': 'abc', 'bar': 123}
    assert analyse_args(arg14, 'abc 123', raise_exception=False) != {'foo': 'abc', 'bar': 123}


def test_pattern():
    test_type = BasePattern("(.+?).py", PatternModel.REGEX_CONVERT, list, lambda x: x.split("/"), "test")
    arg15 = Args().add_argument("bar", value=test_type)
    assert analyse_args(arg15, 'abc.py') == {'bar': ['abc']}
    assert analyse_args(arg15, 'abc/def.py') == {'bar': ['abc', 'def']}
    assert analyse_args(arg15, 'abc/def.mp3', raise_exception=False) != {'bar': ['abc', 'def']}


def test_callable():
    def test(foo: str, bar: int, baz: bool = False):
        ...

    arg16, _ = Args.from_callable(test)
    assert len(arg16.argument) == 3
    assert analyse_args(arg16, "abc 123 True") == {"foo": "abc", "bar": 123, "baz": True}


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
