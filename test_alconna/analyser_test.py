from typing import Union
from nepattern import set_unit
from arclet.alconna.builtin.analyser import DefaultCommandAnalyser
from arclet.alconna import Alconna, Args


def test_filter_out():
    DefaultCommandAnalyser.filter_out.append("int")
    ana = Alconna("ana", Args["foo", str])
    assert ana.parse(["ana", 123, "bar"]).matched is True
    assert ana.parse("ana bar").matched is True
    DefaultCommandAnalyser.filter_out.remove("int")
    assert ana.parse(["ana", 123, "bar"]).matched is False


def test_preprocessor():
    DefaultCommandAnalyser.preprocessors["float"] = lambda x: int(x)
    ana1 = Alconna("ana1", Args["bar", int])
    assert ana1.parse(["ana1", 123.06]).matched is True
    assert ana1.parse(["ana1", 123.06]).bar == 123
    del DefaultCommandAnalyser.preprocessors["float"]
    assert ana1.parse(["ana1", 123.06]).matched is False


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

    DefaultCommandAnalyser.text_sign = "plain"
    DefaultCommandAnalyser.preprocessors['Segment'] = lambda x: str(x) if x.type == "text" else None

    face = set_unit(Segment, lambda x: x.type == "face")
    at = set_unit(Segment, lambda x: x.type == "at")

    ana2 = Alconna("ana2", Args["foo", at]["bar", face])
    res = ana2.parse([Segment.text("ana2"), Segment.at(123456), Segment.face(103)])
    assert res.matched is True
    assert res.foo.data['qq'] == '123456'

    DefaultCommandAnalyser.text_sign = 'text'
    del DefaultCommandAnalyser.preprocessors['Segment']


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
