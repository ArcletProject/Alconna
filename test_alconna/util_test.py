from arclet.alconna.util import split_once, split, LruCache
from arclet.alconna.builtin.checker import simple_type


def test_split_once():
    """测试单次分割函数, 能以引号扩起空格"""
    text1 = "rrr b bbbb"
    text2 = "\'rrr b\' bbbb"
    assert split_once(text1, ' ') == ('rrr', 'b bbbb')
    assert split_once(text2, ' ') == ("'rrr b'", 'bbbb')


def test_split():
    """测试分割函数, 能以引号扩起空格, 并允许保留引号"""
    text1 = "rrr b bbbb"
    text2 = "\'rrr b\' bbbb"
    text3 = "\\\'rrr b\\\' bbbb"
    assert split(text1) == ["rrr", "b", "bbbb"]
    assert split(text2) == ["rrr b", "bbbb"]
    assert split(text3) == ["'rrr b'", "bbbb"]


def test_lru():
    """测试 LRU缓存"""
    cache: LruCache[str, str] = LruCache(3)
    cache.set("a", "a")
    cache.set("b", "b")
    cache.set("c", "c")
    assert cache.recent == "c"
    _ = cache.get("a")
    print(f"\n{cache}")
    assert cache.recent == "a"
    cache.set("d", "d")
    assert cache.get("b", Ellipsis) == Ellipsis


def test_checker():
    @simple_type()
    def hello(num: int):
        return num

    assert hello(123) == 123
    assert hello("123") == 123  # type: ignore

    @simple_type()
    def test(foo: 'bar'):  # type: ignore
        return foo

    assert test("bar") == "bar"
    assert test("foo") is None


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
