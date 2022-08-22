from arclet.alconna.typing import DataCollection
from arclet.alconna.builtin.pattern import ObjectPattern


def test_collection():
    """测试数据集合协议, 要求__str__、__iter__和__len__"""
    assert isinstance("abcdefg", DataCollection)
    assert isinstance(["abcd", "efg"], DataCollection)
    assert isinstance({"a": 1}, DataCollection)
    assert isinstance([123, 456, 7.0, {"a": 1}], DataCollection)
    assert issubclass(list, DataCollection)


def test_object_pattern():
    class A:
        def __init__(self, username: str, userid: int):
            self.name = username
            self.id = userid

    pat11 = ObjectPattern(A, flag='urlget')

    assert pat11.validate("username=abcd&userid=123").success


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, "-vs"])
