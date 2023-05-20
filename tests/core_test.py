from arclet.alconna import (
    Alconna,
    Args,
    Field,
    Option,
    Subcommand,
    AllParam,
    CommandMeta,
    MultiVar,
    KeyWordVar,
    Arg,
    CompSession,
)
from nepattern import IP, URL
import pytest

def test_alconna_create():
    alc = Alconna(
        ["!"],
        "core",
        Args["foo", str],
        Option("bar", Args["num", int]),
    )
    assert alc.path == "Alconna::core"
    assert alc.parse("!core abc bar 123").matched is True

    alc_1 = Alconna(
        "core_1",
        Args["foo", str]["bar;!", int]
    )
    assert alc_1.parse("core_1 abc 123").matched is False
    assert alc_1.parse("core_1 abc abc").matched is True


def test_alconna_multi_match():
    alc1 = Alconna(
        ["/", "!"],
        "core1",
        Subcommand(
            "test",
            Option("-u", Args["username", str], help_text="输入用户名"),
            Args["test", "Test"],
            help_text="测试用例",
        ),
        Option("-n|--num", Args["count", int, 123], help_text="输入数字"),
        Option("-u", Args(id=int), help_text="输入需要At的用户"),
        Args["IP", IP],
        meta=CommandMeta(description="测试指令1"),
    )
    assert len(alc1.options) == 6
    print("")
    print("Help Repr:", repr(alc1.get_help()))
    res1 = alc1.parse(["/core1 -u", 123, "test Test -u AAA -n 222 127.0.0.1"])
    assert res1.matched is True
    assert res1.query("num.count") == 222
    assert res1.query("test.u.username") == "AAA"
    res2 = alc1.parse(["/core1 127.0.0.1 -u", 321])
    assert res2.IP == "127.0.0.1"
    res3 = alc1.parse("/core1 aa")
    assert res3.matched is False
    assert res3.head_matched is True

    alc1_1 = Alconna(
        "core1_1", Subcommand("foo", Option("bar"), Subcommand("foo"), Args["qux", str])
    )
    assert alc1_1.parse("core1_1 foo abc").matched
    assert alc1_1.parse("core1_1 foo foo abc").matched
    assert alc1_1.parse("core1_1 foo bar abc").matched
    assert alc1_1.parse("core1_1 foo bar foo abc").matched
    assert alc1_1.parse("core1_1 foo foo bar abc").matched
    assert not alc1_1.parse("core1_1 foo abc def bar").matched

    alc1_2 = Alconna(
        "core1_2", Option("test"), Args["foo;?", int]["bar;?", str]
    )
    assert alc1_2.parse("core1_2 test 123").matched
    assert alc1_2.parse("core1_2 123").matched
    assert alc1_2.parse("core1_2 test").matched
    assert alc1_2.parse("core1_2").matched
    assert alc1_2.parse("core1_2 abc").matched
    assert alc1_2.parse("core1_2 123 abc").matched
    assert alc1_2.parse("core1_2 abc test").matched
    assert not alc1_2.parse("core1_2 test abc 123").matched

    alc1_3 = Alconna(
        "core1_3", Subcommand(
            "foo", Option("bar"), Args["qux;?", int]
        ),
        Option("baz")
    )
    assert alc1_3.parse("core1_3 foo bar 123").matched
    assert alc1_3.parse("core1_3 foo 123").matched
    assert alc1_3.parse("core1_3 foo bar").matched
    assert alc1_3.parse("core1_3 foo").matched
    assert alc1_3.parse("core1_3 baz").matched
    assert alc1_3.parse("core1_3 foo baz").matched
    assert alc1_3.parse("core1_3 foo bar baz").matched
    assert alc1_3.parse("core1_3 foo bar 123 baz").matched
    assert not alc1_3.parse("core1_3 foo bar baz 123").matched


def test_bracket_header():
    alc2 = Alconna("RD{r:int}?=={e:int}")
    res = alc2.parse("RD100==36")
    assert res.matched is True
    assert res.header["r"] == 100
    assert res.header["e"] == 36


def test_formatter():
    from tarina import lang
    alc3 = Alconna(
        "/pip",
        Subcommand(
            "install",
            Option("--upgrade", help_text="升级包"),
            Option("-i|--index-url", Args["url", URL]),
            Args["pak", str],
            help_text="安装一个包",
        ),
        Option("--retries", Args["retries", int], help_text="设置尝试次数"),
        Option("-t|--timeout", Args["sec", int], help_text="设置超时时间"),
        Option("--exists-action", Args["action", str], help_text="添加行为"),
        Option("--trusted-host", Args["host", str], help_text="选择可信赖地址"),
        meta=CommandMeta(description="简单的pip指令"),
    )
    print("")
    print(alc3.get_help())
    lang.select("en-US")
    print(alc3.get_help())
    lang.select("zh-CN")
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
        Subcommand(
            "-div",
            Option("--round|-r", Args.decimal[int], help_text="保留n位小数"),
            Args(num_a=int, num_b=int),
            help_text="除法计算",
        ),
        meta=CommandMeta(
            description="计算器", usage="Cal <expression>", example="Cal -sum 1 2"
        ),
    )
    print("")
    print(alc4.get_help())
    res = alc4.parse("Cal -div 12 23 --round 2")
    assert res.query("div.args") == {"num_a": 12, "num_b": 23}


def test_alconna_chain_option():
    alc5 = (
        Alconna("点歌")
        .option("歌名", Args(song_name=str), separators="：")
        .option("歌手", Args(singer_name=str), separators="：")
    ).add(Subcommand("foo").add(Option("bar")))

    res = alc5.parse("点歌 歌名：Freejia")
    assert res.song_name == "Freejia"


def test_alconna_multi_header():
    from nepattern import NUMBER

    class A:
        pass

    a, b = A(), A()
    # 纯文字头
    alc6 = Alconna("core6", ["/", "!", "."])
    assert alc6.parse("!core6").head_matched is True
    assert alc6.parse("#core6").head_matched is False
    assert alc6.parse("! core6").head_matched is False
    assert alc6.parse([a]).head_matched is False
    # 对头
    alc6_2 = Alconna("core6_2", [(a, "/"), (A, "!"), ("c", "."), (NUMBER, "d")])
    assert alc6_2.parse([a, "/core6_2"]).head_matched is True
    assert alc6_2.parse([a, "core6_2"]).head_matched is False
    assert alc6_2.parse([b, "/core6_2"]).head_matched is False
    assert alc6_2.parse([b, "!core6_2"]).head_matched is True
    assert alc6_2.parse([a, "!core6_2"]).head_matched is True
    assert alc6_2.parse([A, "!core6_2"]).head_matched is False
    assert alc6_2.parse(["c", ".core6_2"]).head_matched is True
    assert alc6_2.parse(["c", "core6_2"]).head_matched is False
    assert alc6_2.parse("c.core6_2").head_matched is False
    assert alc6_2.parse([123, "dcore6_2"]).head_matched is True
    assert alc6_2.parse(["123.0", "dcore6_2"]).head_matched is True
    assert alc6_2.parse(["aaa", "dcore6_2"]).head_matched is False
    assert alc6_2.parse("123dcore6_2").head_matched is False
    assert alc6_2.parse("/core6_2").head_matched is False
    # 只有纯元素类头
    alc6_3 = Alconna(A)
    assert alc6_3.parse([a]).head_matched is True
    assert alc6_3.parse([b]).head_matched is True
    assert alc6_3.parse("a").head_matched is False
    # 只有纯文字头
    alc6_4 = Alconna(["/dd", "!cd"], Args["a;?", int])
    assert alc6_4.parse("/dd").head_matched is True
    assert alc6_4.parse("/dd 123").head_matched is True
    assert alc6_4.parse("!cd 123").head_matched is True
    assert alc6_4.parse("/dd !cd").matched is False
    assert alc6_4.parse("/dd !cd 123").matched is False
    # 只有纯元素头
    alc6_5 = Alconna(a)
    assert alc6_5.parse([a]).head_matched is True
    assert alc6_5.parse([b]).head_matched is False
    # 元素类头
    alc6_6 = Alconna("core6_6", [A])
    assert alc6_6.parse([a, "core6_6"]).head_matched is True
    assert alc6_6.parse([b, "core6_6"]).head_matched is True
    assert alc6_6.parse([A, "core6_6"]).head_matched is False
    assert alc6_6.parse("core6_6").head_matched is False
    # 表达式头
    alc6_7 = Alconna("core6_7", [NUMBER])
    assert alc6_7.parse([123, "core6_7"]).head_matched is True
    assert alc6_7.parse("123core6_7").head_matched is False
    # 混合头
    alc6_8 = Alconna("core6_8", [A, "/"])
    assert alc6_8.parse([a, "core6_8"]).head_matched is True
    assert alc6_8.parse([b, "core6_8"]).head_matched is True
    assert alc6_8.parse("/core6_8").head_matched is True
    assert alc6_8.parse([A, "core6_8"]).head_matched is False
    assert alc6_8.parse(["/", "core6_8"]).head_matched is True
    assert alc6_8.parse("core6_8").head_matched is False
    alc6_9 = Alconna("core6_9", ["/", a])
    assert alc6_9.parse("/core6_9").head_matched is True
    assert alc6_9.parse([a, "core6_9"]).head_matched is True
    assert alc6_9.parse([b, "core6_9"]).head_matched is False
    assert alc6_9.parse([A, "core6_9"]).head_matched is False
    alc6_10 = Alconna(a, ["/", b])
    assert alc6_10.parse(["/", a]).head_matched is True
    assert alc6_10.parse([b, b]).head_matched is False
    assert alc6_10.parse([b, a]).head_matched is True
    assert alc6_10.parse([b]).head_matched is False
    assert alc6_10.parse([b, "abc"]).head_matched is False
    alc6_11 = Alconna(A, ["/", b])
    assert alc6_11.parse(["/", a]).head_matched is True
    assert alc6_11.parse([b, b]).head_matched is True
    assert alc6_11.parse([b, a]).head_matched is True
    assert alc6_11.parse([b]).head_matched is False
    assert alc6_11.parse([b, "abc"]).head_matched is False
    # 开启 compact 后
    alc6_12 = Alconna("core6_12", Args["foo", str], meta=CommandMeta(compact=True))
    assert alc6_12.parse("core6_12 abc").matched is True
    assert alc6_12.parse("core6_12abc").matched is True
    assert alc6_12.parse("core6_1abc").matched is False
    alc6_13 = Alconna("core6_13", ["/", "?"], Args["foo", str], meta=CommandMeta(compact=True))
    assert alc6_13.parse("/core6_13 abc").matched is True
    assert alc6_13.parse("/core6_13abc").matched is True
    alc6_14 = Alconna("core6_14", ["/", A], Args["foo", str], meta=CommandMeta(compact=True))
    assert alc6_14.parse("/core6_14 abc").matched is True
    assert alc6_14.parse([a, "core6_14abc"]).matched is True


def test_alconna_namespace():
    alc7 = Alconna("core7", namespace="Test")
    assert alc7.path == "Test::core7"
    alc7_1 = Alconna("core7_1").reset_namespace("Test")
    assert alc7_1.path == "Test::core7_1"
    alc7_2 = "Test" / Alconna("core7_2")
    assert alc7_2.path == "Test::core7_2"


def test_alconna_add_option():
    alc8 = "core8" + Option("foo", Args["foo", str]) + Option("bar")
    assert len(alc8.options) == 5
    alc8_1 = Alconna("core8_1") + "foo/bar:str" + "baz"
    assert len(alc8_1.options) == 5
    alc8_2 = "core8_2" + Option("baz")
    assert len(alc8_2.options) == 4


def test_from_callable():
    def test(wild, text: str, num: int, boolean: bool = False):
        print("wild:", wild)
        print("text:", text)
        print("num:", num)
        print("boolean:", boolean)

    alc9 = Alconna("core9", Args.from_callable(test)[0])
    print("")
    print("alc9: -----------------------------")
    alc9.parse("core9 abc def 123 False").call(test)
    print("alc9: -----------------------------")


def test_alconna_synthesise():
    from typing import List
    from nepattern import BasePattern, MatchMode

    cnt = BasePattern(r".*(\d+)张.*", MatchMode.REGEX_CONVERT, int, lambda _, x: int(x))
    alc10 = Alconna(
        Arg("min", cnt, seps="到"),
        Arg("max;?", cnt),
        ["发涩图", "来点涩图", "来点好康的"],
        Option("从", Args["tags", MultiVar(str, 5)] / ("和", "与"), compact=True),
    )
    res = alc10.parse("来点涩图 3张到6张 从女仆和能天使与德克萨斯和拉普兰德与莫斯提马")
    assert res.matched is True
    assert res.min == 3
    assert res.tags == ("女仆", "能天使", "德克萨斯", "拉普兰德", "莫斯提马")

    alc10_1 = Alconna(
        "cpp", Args["match", MultiVar(int, "+")], Arg("lines", AllParam, seps="\n")
    )
    print("")
    print(msg := ("cpp 1 2\n" "#include <iostream>\n" "int main() {...}"))
    print((res := alc10_1.parse(msg)))
    print("\n".join(res.query_with(List[str], "lines", [])))


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
        Option("user perm set", Args["foo", str], help_text="set user permission"),
        Option("user perm del", Args["foo", str], help_text="del user permission"),
        Option("group perm set", Args["foo", str], help_text="set group permission"),
        Option("group perm del", Args["foo", str], help_text="del group permission"),
        Option("test"),
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
    alc14 = Alconna(
        "core14", Option("--foo"), Option("--bar", Args["num", int])
    ) | Alconna("core14", Option("--baz"), Option("--qux", Args["num", int]))
    assert alc14.parse("core14 --foo --bar 123").matched is True
    assert alc14.parse("core14 --baz --qux 123").matched is True
    print("\n---------------------------")
    print(alc14.get_help())


def test_fuzzy():
    alc15 = Alconna("!core15", Args["foo", str], meta=CommandMeta(fuzzy_match=True))
    assert alc15.parse("core15 foo bar").matched is False
    assert alc15.parse([1, "core15", "foo", "bar"]).matched is False


def test_shortcut():
    # 原始命令
    alc16 = Alconna("core16", Args["foo", int], Option("bar", Args["baz", str]))
    assert alc16.parse("core16 123 bar abcd").matched is True
    # 构造体缩写传入；{i} 将被可能的正则匹配替换
    alc16.shortcut("TEST(\d+)(.+)", {"args": ["{0}", "bar {1}"]})
    res = alc16.parse("TEST123aa")
    assert res.matched is True
    assert res.foo == 123
    assert res.baz == "aa"
    # 指令缩写传入， TEST2 -> core16 321
    alc16.parse("core16 --shortcut TEST2 'core16 321'")
    res1 = alc16.parse("TEST2")
    assert res1.foo == 321
    # 缩写命令的构造顺序： 1.新指令 2.传入指令的额外参数 3.构造体参数
    alc16.parse("core16 --shortcut TEST3 core16")
    res2 = alc16.parse("TEST3 442")
    assert res2.foo == 442
    # 指令缩写也支持正则
    alc16.parse("core16 --shortcut TESTa4(\d+) 'core16 {0}'")
    res3 = alc16.parse("TESTa4257")
    assert res3.foo == 257
    alc16.parse("core16 --shortcut TESTac 'core16 2{%0}'")
    res4 = alc16.parse("TESTac 456")
    assert res4.foo == 2456

    alc16_1 = Alconna("exec", Args["content", str])
    alc16_1.shortcut("echo", {"command": "exec print({%0})"})
    alc16_1.shortcut("echo1", {"command": "exec print(\\'{*\n}\\')"})
    res5 = alc16_1.parse("echo 123")
    assert res5.content == "print(123)"
    assert not alc16_1.parse("echo 123 456").matched
    res6 = alc16_1.parse(["echo1", "123", "456 789"])
    assert res6.content == "print('123\n456\n789')"
    res7 = alc16_1.parse([123])
    assert not res7.matched

    alc16_2 = Alconna([1, 2, '3'], "core16_2", Args["foo", bool])
    alc16_2.shortcut("test", {"command": [1, "core16_2 True"]})
    assert alc16_2.parse([1, "core16_2 True"]).matched
    res8 = alc16_2.parse("test")
    assert res8.foo is True
    res9 = alc16_2.parse([2, "test"])
    assert res9.foo is True
    assert not alc16_2.parse("3test").matched


def test_help():
    from arclet.alconna.exceptions import SpecialOptionTriggered

    alc17 = Alconna("core17") + Option("foo", Args["bar", str])
    res = alc17.parse("core17 --help")
    assert isinstance(res.error_info, SpecialOptionTriggered)
    alc17.parse("core17 --help foo")
    alc17_1 = Alconna(
        "core17_1",
        Option("foo bar abc baz", Args["qux", int]),
        Option("foo qux bar", Args["baz", str]),
    )
    alc17_1.parse("core17_1 --help")
    alc17_1.parse("core17_1 --help aaa")


def test_hide_annotation():
    alc18 = Alconna("core18", Args["foo", int])
    print(alc18.get_help())
    alc18_1 = Alconna("core18_1", Args["foo;/", int])
    print(alc18_1.get_help())


def test_args_notice():
    alc19 = Alconna("core19", Args["foo#A TEST;?", int]) + Option(
        "bar", Args["baz#ANOTHER TEST", KeyWordVar(str)]
    )
    print("")
    print(alc19.get_help())


def test_completion():
    from arclet.alconna.exceptions import SpecialOptionTriggered

    alc20 = (
        "core20"
        + Option("fool")
        + Option(
            "foo",
            Args.bar[
                "a|b|c", Field(completion=lambda: "test completion; choose a, b or c")
            ],
        )
        + Option(
            "off",
            Args.baz["aaa|aab|abc", Field(completion=lambda: ["aaa", "aab", "abc"])],
        )
        + Args["test", int, Field(1, completion=lambda: "try -1 ?")]
    )

    alc20.parse("core20 --comp")
    alc20.parse("core20 f --comp")
    alc20.parse("core20 fo --comp")
    alc20.parse("core20 foo --comp")
    alc20.parse("core20 fool --comp")
    alc20.parse("core20 off c --comp")

    alc20_1 = Alconna("core20_1", Args.foo[int], Option("bar"))
    res = alc20_1.parse("core20_1 -cp")
    assert isinstance(res.error_info, SpecialOptionTriggered)


def test_completion_interface():
    alc21 = Alconna("core21", Args.foo[int], Args.bar[str])
    print("\n", "no interface [failed]:", alc21.parse("core21"))
    print("\n", "interface [pending]:")
    with CompSession(alc21) as comp:
        alc21.parse("core21")
    if comp.available:
        print("\n", "current completion:", comp.current())
        print("\n", "next completion:", comp.tab())
        with comp:
            comp.enter(["1"])
        print("\n", "current completion:", comp.current())
        assert comp.enter(["a"]).matched

    with CompSession(alc21) as comp:
        alc21.parse("core21 1 a --comp")
    if comp.available:
        print(comp)
        comp.tab()
        print(comp)
        assert not comp.enter(["-h"]).matched


def test_call():

    alc22 = Alconna("core22", Args.foo[int], Args.bar[str])
    alc22("core22 123 abc")

    @alc22.bind(False)
    def cb(foo: int, bar: str):
        print("")
        print("core22: ")
        print(foo, bar)
        return 2 * foo

    assert cb.result == 246
    alc22.parse("core22 321 abc")
    assert cb.result == 642


def test_nest_subcommand():
    class A:
        pass
    alc23 = Alconna(
        "core23",
        Args.foo[int],
        Subcommand(
            "bar",
            Subcommand(
                "baz", Option("--qux"), help_text="test nest subcommand; deep 2"
            ),
            Args["abc", A],
            help_text="test nest subcommand; deep 1",
        ),
        meta=CommandMeta("test nest subcommand"),
    )
    assert alc23.parse("core23 123").matched
    assert alc23.parse(["core23 bar baz", A(), "123"]).matched
    assert alc23.parse(["core23 bar baz --qux", A(), "123"]).matched
    assert not alc23.parse(["core23 bar baz", A(), "--qux 123"]).matched
    assert (
        alc23.parse(["core23 bar baz --qux", A(), "123"]).query("bar.baz.qux.value") is Ellipsis
    )
    print("")
    # alc23.parse("core23 --help")
    alc23.parse("core23 bar baz --help")

    alc23_1 = Alconna(
        "core23_1",
        Subcommand(
            "bar",
            [Subcommand("qux", Args["def", bool]), Option("baz", Args["abc", str])],
        ),
    )
    assert alc23_1.parse("core23_1 bar baz abc qux True").matched
    assert not alc23_1.parse("core23_1 bar qux True 1 baz abc").matched
    assert alc23_1.parse("core23_1 bar qux false baz hhh").query("bar.qux.def") is False


def test_action():
    from arclet.alconna import append, append_value, count, store_true

    alc24 = Alconna(
        "core24", Option("--yes|-y", action=store_true), Args["module", AllParam]
    )
    res = alc24.parse("core24 -y abc def")
    assert res.query("yes.value") is True
    assert res.module == ["abc", "def"]

    alc24_1 = Alconna(
        "core24", Args["yes", {"--yes": True, "-y": True}, False]["module", AllParam]
    )
    assert alc24_1.parse("core24 -y abc def").yes
    assert not alc24_1.parse("core24 abc def").yes
    assert alc24_1.parse("core24 abc def").module == ["abc", "def"]

    alc24_2 = Alconna(
        "core24_2",
        Option("--i", Args["foo", int]),
        Option("--a|-A", action=append_value(1)),
        Option("--flag|-F", Args["flag", str], action=append, compact=True),
        Option("-v", action=count),
        Option("-x|--xyz", action=count),
        Option("--q", action=count, requires=["foo", "bar"])
    )
    res = alc24_2.parse(
        "core24_2 -A --a -vvv -x -x --xyzxyz "
        "-Fabc -Fdef --flag xyz --i 4 --i 5 "
        "foo bar --q foo bar --qq"
    )
    assert res.query("i.foo") == 5
    assert res.query("a.value") == [1, 1]
    assert res.query("flag.flag") == ["abc", "def", "xyz"]
    assert res.query("v.value") == 3
    assert res.query("xyz.value") == 4
    assert res.query("foo_bar_q.value") == 3


def test_defualt():
    from arclet.alconna import store_value, OptionResult, append, store_true

    alc25 = Alconna(
        "core25",
        Option("--foo", action=store_value(123), default=423),
        Option("bar", Args["baz;?", int]["qux", float, 1.0], default=OptionResult(args={"baz": 321})),
    )

    res1 = alc25.parse("core25")
    assert res1.query("foo.value") == 423
    assert res1.query("baz") == 321

    res2 = alc25.parse("core25 bar")
    assert res2.query("foo.value") == 423
    assert res2.query("bar.baz") == 321
    assert res2.query("bar.qux") == 1.0

    res3 = alc25.parse("core25 --foo")
    assert res3.query("foo.value") == 123
    assert res3.query("bar.baz") == 321

    res4 = alc25.parse("core25 bar 234 2.0")
    assert res4.query("foo.value") == 423
    assert res4.query("bar.baz") == 234
    assert res4.query("bar.qux") == 2.0

    alc25_1 = Alconna(
        "core25_1",
        Option("--foo", action=append, default=423),
        Subcommand("test", Option("--bar", default=False, action=store_true))
    )

    res5 = alc25_1.parse("core25_1")
    assert res5.query("foo.value") == [423]
    assert res5.query("test.bar.value") is None

    res6 = alc25_1.parse("core25_1 --foo test")
    assert res6.query("foo.value") == [423]
    assert res6.query("test.bar.value") is False

    res7 = alc25_1.parse("core25_1 --foo --foo test --bar")
    assert res7.query("foo.value") == [423, 423]
    assert res7.query("test.bar.value") is True


if __name__ == "__main__":

    pytest.main([__file__, "-vs"])
