from arclet.alconna.typing import DataCollection


def test_collection():
    """测试数据集合协议, 要求__str__、__iter__和__len__"""
    assert isinstance("abcdefg", DataCollection)
    assert isinstance(["abcd", "efg"], DataCollection)
    assert isinstance({"a": 1}, DataCollection)
    assert isinstance([123, 456, 7.0, {"a": 1}], DataCollection)
    assert issubclass(list, DataCollection)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
