from arclet.alconna.typing import DataCollection
from arclet.alconna.util import split_once, split


def test_split_once():
    """测试单次分割函数, 能以引号扩起空格, 并允许保留引号"""
    text1 = "rrr b bbbb"
    text2 = "\'rrr b\' bbbb"
    text3 = "\\\'rrr b\\\' bbbb"
    text4 = "\\\'rrr \\b\\\' bbbb"
    assert split_once(text1, ' ') == ('rrr', 'b bbbb')
    assert split_once(text2, ' ') == ("rrr b", 'bbbb')
    assert split_once(text3, ' ') == ("'rrr b'", 'bbbb')
    assert split_once(text4, ' ') == ("'rrr \\b'", 'bbbb')  # 不消除其他转义字符斜杠


def test_split():
    """测试分割函数, 能以引号扩起空格, 并允许保留引号"""
    text1 = "rrr b bbbb"
    text2 = "\'rrr b\' bbbb"
    text3 = "\\\'rrr b\\\' bbbb"
    assert split(text1) == ["rrr", "b", "bbbb"]
    assert split(text2) == ["rrr b", "bbbb"]
    assert split(text3) == ["'rrr b'", "bbbb"]
    assert split("") == []
    assert split("  ") == []



def test_collection():
    """测试数据集合协议, 要求__str__、__iter__和__len__"""
    assert isinstance("abcdefg", DataCollection)
    assert isinstance(["abcd", "efg"], DataCollection)
    assert isinstance({"a": 1}, DataCollection)
    assert isinstance([123, 456, 7.0, {"a": 1}], DataCollection)
    assert issubclass(list, DataCollection)


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, "-vs"])
