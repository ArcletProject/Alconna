from typing import Union
from nepattern import BasePattern, PatternModel
from arclet.alconna.analysis.analyser import Analyser
from arclet.alconna import Alconna, Args


def test_filter_out():
    Analyser.config(filter_out=["int"])
    ana = Alconna("ana", Args["foo", str])
    assert ana.parse(["ana", 123, "bar"]).matched is True
    assert ana.parse("ana bar").matched is True
    Analyser.config(filter_out=[])
    ana_1 = Alconna("ana", Args["foo", str])
    assert ana_1.parse(["ana", 123, "bar"]).matched is False


def test_preprocessor():
    Analyser.config(processors={"float": lambda x: int(x)})
    ana1 = Alconna("ana1", Args["bar", int])
    assert ana1.parse(["ana1", 123.06]).matched is True
    assert ana1.parse(["ana1", 123.06]).bar == 123
    Analyser.config(processors={})
    ana1_1 = Alconna("ana1", Args["bar", int])
    assert ana1_1.parse(["ana1", 123.06]).matched is False


def test_with_set_unit():
    class Segment:
        type: str
        data: dict

        def __init__(self, type_: str, **data):
            self.type = type_
            self.data = data
            self.data.setdefault("type", type_)

        def __repr__(self):
            data = self.data.copy()
            if self.type == "text":
                return data.get("text", "")
            return f"[{self.type}:{self.data}]"

        @staticmethod
        def text(content: str):
            return Segment("text", text=content)

        @staticmethod
        def face(id_: int, content: str = ''):
            return Segment("face", id=id_, content=content)

        @staticmethod
        def at(user_id: Union[int, str]):
            return Segment("at", qq=str(user_id))

    Analyser.config(
        text_sign="plain",
        processors={"Segment": lambda x: str(x) if x.type == "text" else None}
    )

    def gen_unit(type_: str):
        return BasePattern(
            type_, PatternModel.TYPE_CONVERT, Segment,
            lambda _, seg: seg if seg.type == type_ else None,
            type_, accepts=[Segment]
        )

    Face = gen_unit("face")
    At = gen_unit("at")

    ana2 = Alconna("ana2", Args["foo", At]["bar", Face])
    res = ana2.parse([Segment.text("ana2"), Segment.at(123456), Segment.face(103)])
    assert res.matched is True
    assert res.foo.data['qq'] == '123456'
    Analyser.config()


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
