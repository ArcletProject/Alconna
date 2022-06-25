from arclet.alconna.typing import DataCollection, BasePattern, PatternModel, args_type_parser
from arclet.alconna.builtin.pattern import ObjectPattern


def test_collection():
    """测试数据集合协议, 要求__str__、__iter__和__len__"""
    assert isinstance("abcdefg", DataCollection)
    assert isinstance(["abcd", "efg"], DataCollection)
    assert isinstance({"a": 1}, DataCollection)
    assert isinstance([123, 456, 7.0, {"a": 1}], DataCollection)
    assert issubclass(list, DataCollection)


def test_pattern_of():
    """测试 BasePattern 的快速创建方法之一, 对类有效"""
    pat = BasePattern.of(int)
    assert pat.origin == int
    assert pat.validate(123)[0] == 123
    assert pat.validate('abc')[1] == 'E'


def test_pattern_on():
    """测试 BasePattern 的快速创建方法之一, 对对象有效"""
    pat1 = BasePattern.on(123)
    assert pat1.origin == int
    assert pat1.validate(123)[0] == 123
    assert pat1.validate(124)[1] == 'E'


def test_pattern_keep():
    """测试 BasePattern 的保持模式, 不会进行匹配或者类型转换"""
    pat2 = BasePattern(model=PatternModel.KEEP)
    assert pat2.validate(123)[0] == 123
    assert pat2.validate("abc")[0] == "abc"


def test_pattern_regex():
    """测试 BasePattern 的正则匹配模式, 仅正则匹配"""
    pat3 = BasePattern("abc[A-Z]+123", PatternModel.REGEX_MATCH)
    assert pat3.validate("abcABC123")[0] == "abcABC123"
    assert pat3.validate("abcAbc123")[1] == "E"


def test_pattern_regex_convert():
    """测试 BasePattern 的正则转换模式, 正则匹配成功后再进行类型转换"""
    pat4 = BasePattern(r"\[at:(\d+)\]", PatternModel.REGEX_CONVERT, int, lambda x: int(x))
    assert pat4.validate("[at:123456]")[0] == 123456
    assert pat4.validate("[at:abcdef]")[1] == "E"
    assert pat4.validate(123456)[0] == 123456


def test_pattern_type_convert():
    """测试 BasePattern 的类型转换模式, 仅将传入对象变为另一类型的新对象"""
    pat5 = BasePattern(model=PatternModel.TYPE_CONVERT, origin=str, converter=lambda x: str(x))
    assert pat5.validate(123)[0] == "123"
    assert pat5.validate([4, 5, 6])[0] == "[4, 5, 6]"


def test_pattern_accepts():
    """测试 BasePattern 的输入类型筛选, 不在范围内的类型视为非法"""
    pat6 = BasePattern(model=PatternModel.TYPE_CONVERT, origin=str, converter=lambda x: x.decode(), accepts=[bytes])
    assert pat6.validate(b'123')[0] == "123"
    assert pat6.validate(123)[1] == 'E'
    pat6_1 = BasePattern(model=PatternModel.KEEP, accepts=[int, float])
    assert pat6_1.validate(123)[0] == 123
    assert pat6_1.validate('123')[1] == 'E'


def test_pattern_previous():
    """测试 BasePattern 的前置表达式, 在传入的对象类型不正确时会尝试用前置表达式进行预处理"""

    class A:
        def __repr__(self):
            return '123'

    pat7 = BasePattern(model=PatternModel.TYPE_CONVERT, origin=str, converter=lambda x: f"abc[{x}]")
    pat7_1 = BasePattern(
        r"abc\[(\d+)\]", model=PatternModel.REGEX_CONVERT, origin=int, converter=lambda x: int(x), previous=pat7
    )
    assert pat7_1.validate("abc[123]")[0] == 123
    assert pat7_1.validate(A())[0] == 123


def test_pattern_anti():
    """测试 BasePattern 的反向验证功能"""
    pat8 = BasePattern.of(int)
    assert pat8.validate(123)[1] == 'V'
    assert pat8.invalidate(123)[1] == 'E'


def test_pattern_validator():
    """测试 BasePattern 的匹配后验证器, 会对匹配结果进行验证"""
    pat9 = BasePattern(model=PatternModel.KEEP, origin=int, validators=[lambda x: x > 0])
    assert pat9.validate(23)[0] == 23
    assert pat9.validate(-23)[1] == 'E'


def test_args_parser():
    pat10 = args_type_parser(int)
    assert pat10.validate(-321)[1] == 'V'
    pat10_1 = args_type_parser(123)
    assert pat10_1 == BasePattern.on(123)


def test_object_pattern():
    class A:
        def __init__(self, username: str, userid: int):
            self.name = username
            self.id = userid

    pat11 = ObjectPattern(A, flag='urlget')

    assert pat11.validate("username=abcd&userid=123")[1] == 'V'


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, "-vs"])
