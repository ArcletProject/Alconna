from dataclasses import dataclass, field
from typing import Any, Union

from nepattern import BasePattern, MatchMode

from arclet.alconna import Alconna, Args, Option, Argv, set_default_argv_type
from arclet.alconna.argv import argv_config


class DummyArgv(Argv):
    ...


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
    return BasePattern(
        mode=MatchMode.TYPE_CONVERT, origin=Any, converter=lambda _, seg: seg if seg.type == type_ else None, alias=type_, accepts=Segment
    )


Face = gen_unit("face")
At = gen_unit("at")


def test_with_set_unit():
    argv_config(DummyArgv, to_text=lambda x: x if x.__class__ is str else str(x) if x.type == "text" else None)
    set_default_argv_type(DummyArgv)

    ana2 = Alconna("ana2", Args["foo", At]["bar", Face])
    res = ana2.parse([Segment.text("ana2"), Segment.at(123456), Segment.face(103)])
    assert res.matched is True
    assert res.foo.data["qq"] == "123456"
    assert not ana2.parse([Segment.text("ana2"), Segment.face(103), Segment.at(123456)]).matched

    set_default_argv_type(Argv)


def test_unhashable_unit():
    argv_config(DummyArgv, to_text=lambda x: x if x.__class__ is str else str(x) if x.type == "text" else None)
    set_default_argv_type(DummyArgv)

    ana3 = Alconna("ana3", Args["foo", At])
    print(ana3.parse(["ana3", Segment.at(123)]))
    print(ana3.parse(["ana3", Segment.face(123)]))

    ana3_1 = Alconna("ana3_1", Option("--foo", Args["bar", int]))
    print(ana3_1.parse(["ana3_1 --foo 123"]))
    print(ana3_1.parse(["ana3_1", Segment.face(123)]))
    print(ana3_1.parse(["ana3_1", "--foo", "--comp", Segment.at(123)]))
    print(ana3_1.parse(["ana3_1", "--comp", Segment.at(123)]))

    set_default_argv_type(Argv)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
