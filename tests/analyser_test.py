from dataclasses import dataclass, field
from typing import Union
from collections import UserList

import pytest
from nepattern import Pattern

from arclet.alconna import Alconna, Args, Option
from arclet.alconna.ingedia._argv import argv_config, reset_argv_config


@dataclass
class Segment:
    type: str
    data: dict = field(default_factory=dict)

    def __str__(self):
        data = self.data.copy()
        if self.type == "text":
            return data.get("text", "")
        return f"[{self.type}:{self.data}]"

    @staticmethod
    def text(content: str):
        return Segment("text", {"text": content})

    @staticmethod
    def face(id_: int, content: str = ""):
        return Segment("face", {"id": id_, "content": content})

    @staticmethod
    def at(user_id: Union[int, str]):
        return Segment("at", {"qq": str(user_id)})


def gen_unit(type_: str):
    return Pattern(Segment, type_).convert(lambda _, seg: seg if seg.type == type_ else None)


Face = gen_unit("face")
At = gen_unit("at")


# def test_filter_out():
#     argv_config(filter_out=[int])
#     ana = Alconna("ana", Args.foo(str))
#     assert ana.parse(["ana", 123, "bar"]).matched is True
#     assert ana.parse("ana bar").matched is True
#     reset_argv_config()
#     ana_1 = Alconna("ana", Args.foo(str))
#     assert ana_1.parse(["ana", 123, "bar"]).matched is False


def test_preprocessor():
    argv_config(preprocessors={list: len})
    ana1 = Alconna("ana1", Args.bar(int))
    assert ana1.parse(["ana1", [1, 2, 3]]).matched is True
    assert ana1.parse(["ana1", [1, 2, 3]])["bar"] == 3
    reset_argv_config()
    ana1_1 = Alconna("ana1", Args.bar(int))
    assert ana1_1.parse(["ana1", [1, 2, 3]]).matched is False


def test_with_set_unit():
    argv_config(preprocessors={Segment: lambda x: str(x) if x.type == "text" else None})

    ana2 = Alconna("ana2", Args.foo(At).bar(Face))
    res = ana2.parse([Segment.text("ana2"), Segment.at(123456), Segment.face(103)])
    assert res.matched is True
    assert res["foo"].data["qq"] == "123456"
    assert not ana2.parse([Segment.text("ana2"), Segment.face(103), Segment.at(123456)]).matched
    reset_argv_config()


def test_unhashable_unit():
    argv_config(preprocessors={Segment: lambda x: str(x) if x.type == "text" else None})

    ana3 = Alconna("ana3", Args.foo(At))
    assert ana3.parse(["ana3", Segment.at(123)]).matched
    assert ana3.parse(["ana3", Segment.face(123)]).matched is False

    ana3_1 = Alconna("ana3_1", Option("--foo", Args.bar(int)))
    assert ana3_1.parse(["ana3_1 --foo 123"]).matched
    assert ana3_1.parse(["ana3_1", Segment.face(123)]).matched is False
    assert ana3_1.parse(["ana3_1", "--foo", "--comp", Segment.at(123)]).output
    assert ana3_1.parse(["ana3_1", "--comp", Segment.at(123)]).output

    reset_argv_config()


def test_checker():
    argv_config(checker=lambda x: isinstance(x, UserList))
    ana4 = Alconna("ana4", Args.foo(int))
    assert ana4.parse(UserList(["ana4", "123"]))

    with pytest.raises(TypeError):
        ana4.parse("ana4 123")

    reset_argv_config()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
