from arclet.alconna.core import AlconnaGroup
from arclet.alconna import (
    Alconna,
    Args,
    ArgField,
    Option,
    Subcommand,
    ArgParserTextFormatter,
    AllParam,
    CommandMeta,
)


def test_alconna_create():
    alc = Alconna(
        "core",
        Args["foo", str],
        headers=["!"],
        options=[Option("bar", Args["num", int])],
    )
    assert alc.path == "Alconna.core"
    assert alc.parse("!core abc bar 123").matched is True


def test_alconna_multi_match():
    alc1 = Alconna(
        headers=["/", "!"],
        command="core1",
        options=[
            Subcommand(
                "test",
                [Option("-u", Args["username", str], help_text="输入用户名")],
                args=Args["test", "Test"],
                help_text="测试用例",
            ),
            Option("-n|--num", Args["count", int, 123], help_text="输入数字"),
            Option("-u", Args(id=int), help_text="输入需要At的用户"),
        ],
        main_args=Args["IP", "ip"],
        meta=CommandMeta(description="测试指令1")
    )
    assert len(alc1.options) == 6
    print("")
    print(repr(alc1.get_help()))
    res1 = alc1.parse(["/core1 -u", 123, "test Test -u AAA -n 222 127.0.0.1"])
    assert res1.matched is True
    assert res1.query("num.count") == 222
    assert res1.query("test.u.username") == "AAA"
    res2 = alc1.parse(["/core1 127.0.0.1 -u", 321])
    assert res2.IP == "127.0.0.1"
    res3 = alc1.parse("/core1 aa")
    assert res3.matched is False
    assert res3.head_matched is True


def test_special_header():
    alc2 = Alconna("RD{r:int}?=={e:int}")
    res = alc2.parse("RD100==36")
    assert res.matched is True
    assert res.header["r"] == "100"
    assert res.header["e"] == "36"


def test_formatter():
    alc3 = Alconna(
        command="/pip",
        options=[
            Subcommand(
                "install",
                [
                    Option("--upgrade", help_text="升级包"),
                    Option("-i|--index-url", Args["url", "url"]),
                ],
                Args["pak", str],
                help_text="安装一个包",
            ),
            Option("--retries", Args["retries", int], help_text="设置尝试次数"),
            Option("-t|--timeout", Args["sec", int], help_text="设置超时时间"),
            Option("--exists-action", Args["action", str], help_text="添加行为"),
            Option("--trusted-host", Args["host", str], help_text="选择可信赖地址"),
        ],
        meta=CommandMeta(description="简单的pip指令"),
        formatter_type=ArgParserTextFormatter,
    )
    print("")
    print(alc3.get_help())
    res = alc3.parse(
        "/pip install alconna --upgrade -i https://pypi.douban.com/simple -t 6 --trusted-host pypi.douban.com"
    )
    assert res.matched is True
    assert res.all_matched_args["sec"] == 6
    assert res.all_matched_args["pak"] == "alconna"
    assert res.all_matched_args["url"] == "https://pypi.douban.com/simple"
    assert res.all_matched_args["host"] == "pypi.douban.com"


def test_alconna_special_help():
    alc4 = Alconna(
        "Cal",
        meta=CommandMeta(description="计算器", usage="Cal <expression>", example="Cal -sum 1 2"),
        options=[
            Subcommand(
                "-div",
                options=[Option("--round|-r", Args.decimal[int], help_text="保留n位小数")],
                args=Args(num_a=int, num_b=int),
                help_text="除法计算",
            )
        ],
    )
    print("")
    print(alc4.get_help())
    res = alc4.parse("Cal -div 12 23 --round 2")
    assert res.query("div.args") == {"num_a": 12, "num_b": 23}


def test_alconna_chain_option():
    alc5 = (
        Alconna("点歌")
            .add("歌名", sep="：", args=Args(song_name=str))
            .add("歌手", sep="：", args=Args(singer_name=str))
    )
    res = alc5.parse("点歌 歌名：Freejia")
    assert res.song_name == "Freejia"


def test_alconna_multi_header():
    class A:
        pass

    a, b = A(), A()
    alc6 = Alconna("core6", headers=["/", "!", "."])
    assert alc6.parse("!core6").head_matched is True
    assert alc6.parse("#core6").head_matched is False
    assert alc6.parse([a]).head_matched is False
    alc6_1 = Alconna("core6_1", headers=["/", a])
    assert alc6_1.parse("/core6_1").head_matched is True
    assert alc6_1.parse([a, "core6_1"]).head_matched is True
    assert alc6_1.parse([b, "core6_1"]).head_matched is False
    alc6_2 = Alconna("core6_2", headers=[(a, "/")])
    assert alc6_2.parse([a, "/core6_2"]).head_matched is True
    assert alc6_2.parse([a, "core6_2"]).head_matched is False
    assert alc6_2.parse("/core6_2").head_matched is False
    alc6_3 = Alconna(A)
    assert alc6_3.parse([a]).head_matched is True
    assert alc6_3.parse([b]).head_matched is True
    assert alc6_3.parse("a").head_matched is False
    alc6_4 = Alconna(A, headers=["/", b])
    assert alc6_4.parse(["/", a]).head_matched is True
    assert alc6_4.parse([b, b]).head_matched is True
    assert alc6_4.parse([b, a]).head_matched is True
    assert alc6_4.parse([b]).head_matched is False
    assert alc6_4.parse([b, "abc"]).head_matched is False
    alc6_5 = Alconna(headers=["/dd", "!cd"])
    assert alc6_5.parse("/dd").head_matched is True
    assert alc6_5.parse("/dd !cd").matched is False
    alc6_6 = Alconna(1234)  # type: ignore
    assert alc6_6.parse([1234]).head_matched is True
    assert alc6_6.parse([4321]).head_matched is False


def test_alconna_namespace():
    alc7 = Alconna("core7", namespace="Test")
    assert alc7.path == "Test.core7"
    alc7_1 = Alconna("core7_1").reset_namespace("Test")
    assert alc7_1.path == "Test.core7_1"
    alc7_2 = "Test" / Alconna("core7_2")
    assert alc7_2.path == "Test.core7_2"


def test_alconna_add_option():
    alc8 = Alconna("core8") + Option("foo", Args["foo", str]) >> Option("bar")
    assert len(alc8.options) == 5
    alc8_1 = Alconna("core8_1") + "foo/bar:str" >> "baz"
    assert len(alc8_1.options) == 5


def test_alconna_action():
    def test(wild, text: str, num: int, boolean: bool = False):
        print("wild:", wild)
        print("text:", text)
        print("num:", num)
        print("boolean:", boolean)

    alc9 = Alconna("core9", action=test)
    print("")
    print("alc9: -----------------------------")
    alc9.parse("core9 abc def 123 False")
    print("alc9: -----------------------------")


def test_alconna_synthesise():
    alc10 = Alconna(
        main_args=Args["min", r"(\d+)张"]["max;O", r"(\d+)张"] / "到",
        headers=["发涩图", "来点涩图", "来点好康的"],
        options=[Option("从", Args["tags;5", str] / ("和", "与"), separators="")],
        action=lambda x, y: (int(x), int(y)),
    )
    res = alc10.parse("来点涩图 3张到6张 从女仆和能天使与德克萨斯和拉普兰德与莫斯提马")
    assert res.matched is True
    assert res.min == 3
    assert res.tags == ("女仆", "能天使", "德克萨斯", "拉普兰德", "莫斯提马")


def test_simple_override():
    alc11 = Alconna("core11") + Option("foo", Args["bar", str]) + Option("foo")
    res = alc11.parse("core11 foo abc")
    res1 = alc11.parse("core11 foo")
    assert res.matched is True
    assert res1.matched is True


def test_requires():
    alc12 = Alconna(
        "core12",
        Args["target", int],
        options=[
            Option("user perm set", Args["foo", str], help_text="set user permission"),
            Option("user perm del", Args["foo", str], help_text="del user permission"),
            Option(
                "group perm set", Args["foo", str], help_text="set group permission"
            ),
            Option(
                "group perm del", Args["foo", str], help_text="del group permission"
            ),
            Option("test"),
        ],
    )

    assert alc12.parse("core12 123 user perm set 123").find("user_perm_set") is True
    assert alc12.parse("core12 123 user perm del 123").find("user_perm_del") is True
    assert alc12.parse("core12 123 group perm set 123").find("group_perm_set") is True
    assert (
            alc12.parse("core12 123 group perm del 123 test").find("group_perm_del") is True
    )
    print("\n------------------------")
    print(alc12.get_help())


def test_wildcard():
    alc13 = Alconna("core13", Args["foo", AllParam])
    assert alc13.parse(["core13 abc def gh", 123, 5.0, "dsdf"]).foo == [
        "abc",
        "def",
        "gh",
        123,
        5.0,
        "dsdf",
    ]


def test_alconna_group():
    alc14 = AlconnaGroup(
        "core14",
        Alconna("core14", options=[Option("--foo"), Option("--bar", Args["num", int])]),
        Alconna("core14", options=[Option("--baz"), Option("--qux", Args["num", int])]),
    )
    assert alc14.parse("core14 --foo --bar 123").matched is True
    assert alc14.parse("core14 --baz --qux 123").matched is True
    print("\n---------------------------")
    print(alc14.get_help())


def test_fuzzy():
    alc15 = Alconna(main_args="foo:str", headers=["!core15"], meta=CommandMeta(fuzzy_match=True))
    assert alc15.parse("core15 foo bar").matched is False


def test_shortcut():
    alc16 = Alconna("core16", Args["foo", int], options=[Option("bar")])
    assert alc16.parse("core16 123 bar").matched is True
    alc16.shortcut("TEST", "core16 432 bar")
    res = alc16.parse("TEST")
    assert res.matched is True
    assert res.foo == 432


def test_help():
    alc17 = Alconna("core17") + Option("foo", Args["bar", str])
    alc17.parse("core17 --help")
    alc17.parse("core17 --help foo")
    alc17_1 = Alconna(
        "core17_1",
        options=[
            Option("foo bar abc baz", Args["qux", int]),
            Option("foo qux bar", Args["baz", str]),
        ],
    )
    alc17_1.parse("core17_1 --help")
    alc17_1.parse("core17_1 --help aaa")


def test_hide_annotation():
    alc18 = Alconna("core18", Args["foo", int])
    print(alc18.get_help())
    alc18_1 = Alconna("core18_1", Args["foo;H", int])
    print(alc18_1.get_help())


def test_args_notice():
    alc19 = Alconna("core19", Args["foo#A TEST;O", int]) + Option(
        "bar", Args["baz#ANOTHER TEST;K", str]
    )
    print("")
    print(alc19.get_help())


def test_completion():
    alc20 = Alconna("core20") + Option(
        "foo", Args[
            "bar",
            "a|b|c",
            ArgField(completion=lambda: "test completion; choose a, b or c")
        ]
    ) + Option("fool")
    print("")
    print(alc20.parse("core20 --comp"))
    print(alc20.parse("core20 foo").error_info)
    alc20.parse("core20 foo --comp")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
