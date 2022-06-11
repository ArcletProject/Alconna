from typing import Optional

import pytest
from arclet.alconna import AlconnaString, AlconnaFormat, AlconnaFire, AlconnaDecorate, delegate, Args


def test_koishi_like():
    con = AlconnaString("con <url:url>")
    assert con.parse("con https://www.example.com").matched is True
    con_1 = AlconnaString("con_1", "--foo <foo:str:123> [bar:bool]", "--bar &True")
    assert con_1.parse("con_1 --bar").query("bar.value") is True
    assert con_1.parse("con_1 --foo").query("foo.args") == {"foo": "123"}
    con_2 = AlconnaString("[!con_2|/con_2] <foo:str> <...bar>")
    assert con_2.parse("!con_2 112 334").matched is True
    assert con_2.parse("con_2 112 334").matched is False


def test_format_like():
    con1 = AlconnaFormat("con1 {artist} {title:str} singer {name:str}")
    print('')
    print(repr(con1.get_help()))
    assert con1.parse("con1 Nameless MadWorld").artist == "Nameless"
    con1_1 = AlconnaFormat("con1_1 user {target}", {"target": str})
    assert con1_1.parse("con1_1 user Nameless").query("user.target") == "Nameless"
    con1_2 = AlconnaFormat(
        "con1_2 user {target} perm set {perm} {default}",
        {"target": str, "perm": str, "default": Args["default", bool, True]},
    )
    print(repr(con1_2.get_help()))
    assert con1_2.parse("con1_2 user Nameless perm set Admin.set True").query("perm_set.default") is True


def test_fire_like_class():
    class Test:
        """测试从类中构建对象"""

        def __init__(self, sender: Optional[str]):
            """Constructor"""
            self.sender = sender

        def talk(self, name="world"):
            """Test Function"""
            print(f"Hello {name} from {self.sender}")

        class Repo:
            def set(self, name):
                print(f"set {name}")

            class SubConfig:
                description = "sub-test"

        class Config:
            command = "con2"
            description = "测试"
            extra = "reject"
            get_subcommand = True

    con2 = AlconnaFire(Test)
    assert con2.parse("con2 Alc talk Repo set hhh").matched is True
    assert con2.parse("con2 talk Friend").query("talk.name") == "Friend"
    print('')
    print(repr(con2.get_help()))
    print(con2.instance)


def test_fire_like_object():
    class Test:
        def __init__(self, action=sum):
            self.action = action

        def calculator(self, a, b, c, *nums: int, **kwargs: str):
            """calculator"""
            print(a, b, c)
            print(nums, kwargs)
            print(self.action(nums))

        class Config:
            command = "con3"

    con3 = AlconnaFire(Test(sum))
    print('')
    print(con3.get_help())
    assert con3.parse("con3 calculator 1 2 3 4 5 d=6 f=7")


def test_fire_like_func():
    def test_function(name="world"):
        """测试从函数中构建对象"""

        class Config:
            command = "con4"
            description = "测试"

        print("Hello {}!".format(name))

    con4 = AlconnaFire(test_function)
    assert con4.parse("con4 talk Friend").matched is True


def test_delegate():
    @delegate
    class con5:
        """hello"""
        prefix = "!"

    print(repr(con5.get_help()))


def test_click_like():
    con6 = AlconnaDecorate()

    @con6.build_command("con6")
    @con6.option("--count", Args["num", int], help="Test Option Count")
    @con6.option("--foo", Args["bar", str], help="Test Option Foo")
    def hello(bar: str, num: int = 1):
        """测试DOC"""
        print(bar * num)

    assert hello("con6 --foo John --count 2").matched is True


if __name__ == '__main__':
    pytest.main([__file__, "-vs"])
