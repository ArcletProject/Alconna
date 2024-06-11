import re

import pytest
from nepattern import IP, URL

from arclet.alconna import (
    Alconna,
    AllParam,
    Arg,
    Args,
    CommandMeta,
    CompSession,
    Field,
    KeyWordVar,
    MultiVar,
    Option,
    Subcommand,
    namespace,
)


def test_alconna_create():
    alc = Alconna(
        ["!"],
        "core",
        Args["foo", str],
        Option("bar", Args["num", int]),
    )
    assert alc.path == "Alconna::core"
    assert alc.parse("!core abc bar 123").matched is True

    alc_1 = Alconna("core_1", Args["foo", str]["bar;!", int])
    assert alc_1.parse("core_1 abc 123").matched is False
    assert alc_1.parse("core_1 abc abc").matched is True
    query = alc_1.parse("core_1 abc abc").query[str]
    assert query("bar") == "abc"


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
        Option("--num", Args["count", int, 123], help_text="输入数字"),
        Option("-u", Args["id", int], help_text="输入需要At的用户"),
        Args["IP", IP],
        meta=CommandMeta(description="测试指令1"),
    )
    assert len(alc1.options) == 6
    assert (
        alc1.get_help()
        == """\
[/│!]core1 <IP: ip> 
测试指令1

可用的子命令有:
* 测试用例
  test <test: 'Test'> 
  该子命令内可用的选项有:
  * 输入用户名
    -u <username: str> 
可用的选项有:
* 输入数字
  --num <count: int = 123> 
* 输入需要At的用户
  -u <id: int> 
"""
    )
    res1 = alc1.parse(["/core1 -u", 123, "test Test -u AAA --num 222 127.0.0.1"])
    assert res1.matched is True
    assert res1.query("num.count") == 222
    assert res1.query("test.u.username") == "AAA"
    res2 = alc1.parse(["/core1 127.0.0.1 -u", 321])
    assert res2.IP == "127.0.0.1"
    res3 = alc1.parse("/core1 aa")
    assert res3.matched is False
    assert res3.head_matched is True

    alc1_1 = Alconna("core1_1", Subcommand("foo", Option("bar"), Subcommand("foo"), Args["qux", str]))
    assert alc1_1.parse("core1_1 foo abc").matched
    assert alc1_1.parse("core1_1 foo foo abc").matched
    assert alc1_1.parse("core1_1 foo bar abc").matched
    assert alc1_1.parse("core1_1 foo bar foo abc").matched
    assert alc1_1.parse("core1_1 foo foo bar abc").matched
    assert not alc1_1.parse("core1_1 foo abc def bar").matched

    alc1_2 = Alconna("core1_2", Option("test"), Args["foo;?", int]["bar;?", str])
    assert alc1_2.parse("core1_2 test 123").matched
    assert alc1_2.parse("core1_2 123").matched
    assert alc1_2.parse("core1_2 test").matched
    assert alc1_2.parse("core1_2").matched
    assert alc1_2.parse("core1_2 abc").matched
    assert alc1_2.parse("core1_2 123 abc").matched
    assert alc1_2.parse("core1_2 abc test").matched
    assert not alc1_2.parse("core1_2 test abc 123").matched

    alc1_3 = Alconna("core1_3", Subcommand("foo", Option("bar"), Args["qux;?", int]), Option("baz"))
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
    alc2_1 = Alconna(r"RD\{r:int\}")
    assert not alc2_1.parse("RD100").matched
    assert alc2_1.parse("RD{r:int}").matched


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
            Option("--round|-r", Args["decimal", int], help_text="保留n位小数"),
            Args["num_a", int]["num_b", int],
            help_text="除法计算",
        ),
        meta=CommandMeta(description="计算器", usage="Cal <expression>", example="Cal -sum 1 2"),
    )
    print("")
    print(alc4.get_help())
    res = alc4.parse("Cal -div 12 23 --round 2")
    assert res.query("div.args") == {"num_a": 12, "num_b": 23}


def test_alconna_chain_option():
    alc5 = (
        Alconna("点歌")
        .option("歌名", Args["song_name", str], separators="：")
        .option("歌手", Args["singer_name", str], separators="：")
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
    # 纯文字头可以塞分隔符
    alc6_1 = Alconna("core6_1", ["/", "!", "aaa "])  # 'aaa ' 的空格是分隔符
    assert alc6_1.parse("!core6_1").head_matched is True
    assert alc6_1.parse("aaa core6_1").head_matched is True
    assert alc6_1.parse("aaacore6_1").head_matched is False
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
        assert wild == "abc"
        assert text == "def"
        assert num == 123
        assert not boolean

    alc9 = Alconna("core9", Args.from_callable(test)[0])
    alc9.parse("core9 abc def 123 False").call(test)


def test_alconna_synthesise():
    from typing import List

    from nepattern import BasePattern, MatchMode

    cnt = BasePattern(r".*(\d+)张.*", MatchMode.REGEX_CONVERT, int, lambda _, x: int(x[1]))
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

    alc10_1 = Alconna("cpp", Args["match", MultiVar(int, "+")], Arg("lines", AllParam, seps="\n"))
    print("")
    print(msg := "cpp 1 2\n" "#include <iostream>\n" "int main() {...}")
    print((res := alc10_1.parse(msg)))
    print("\n".join(res.query[List[str]]("lines", [])))


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
    assert alc12.parse("core12 123 group perm del 123 test").find("group_perm_del") is True
    print("\n------------------------")
    print(alc12.get_help())


def test_wildcard():
    alc13 = Alconna("core13", Args["foo", AllParam])
    assert alc13.parse(["core13 abc def gh", 123, 5.0, "dsdf"]).foo == [
        "abc def gh",
        123,
        5.0,
        "dsdf",
    ]
    assert alc13.parse(
        """core13
import foo

def test():
    print("Hello, World!")"""
    ).foo == [
        """\
import foo

def test():
    print("Hello, World!")"""
    ]


def test_alconna_group():
    alc14 = Alconna("core14", Option("--foo"), Option("--bar", Args["num", int])) | Alconna(
        "core14", Option("--baz"), Option("--qux", Args["num", int])
    )
    assert alc14.parse("core14 --foo --bar 123").matched is True
    assert alc14.parse("core14 --baz --qux 123").matched is True
    print("\n---------------------------")
    print(alc14.get_help())


def test_fuzzy():
    from arclet.alconna import output_manager

    alc15 = Alconna("!core15", Args["foo", str], meta=CommandMeta(fuzzy_match=True))
    with output_manager.capture("!core15") as cap:
        output_manager.set_action(lambda x: x, "!core15")
        res = alc15.parse("core15 foo bar")
        assert res.matched is False
        assert cap["output"] == '无法解析 "core15"。您想要输入的是不是 "!core15" ?'
    with output_manager.capture("!core15") as cap:
        output_manager.set_action(lambda x: x, "!core15")
        res1 = alc15.parse([1, "core15", "foo", "bar"])
        assert res1.matched is False
        assert cap["output"] == '无法解析 "1 core15"。您想要输入的是不是 "!core15" ?'

    alc15_1 = Alconna(["/"], "core15_1", meta=CommandMeta(fuzzy_match=True))
    with output_manager.capture("core15_1") as cap:
        output_manager.set_action(lambda x: x, "core15_1")
        res2 = alc15_1.parse("core15_1")
        assert res2.matched is False
        assert cap["output"] == '无法解析 "core15_1"。您想要输入的是不是 "/core15_1" ?'
    with output_manager.capture("core15_1") as cap:
        output_manager.set_action(lambda x: x, "core15_1")
        res2 = alc15_1.parse("@core15_1")
        assert res2.matched is False
        assert cap["output"] == '无法解析 "@core15_1"。您想要输入的是不是 "/core15_1" ?'

    alc15_2 = Alconna([1], "core15_2", meta=CommandMeta(fuzzy_match=True))
    with output_manager.capture("core15_2") as cap:
        output_manager.set_action(lambda x: x, "core15_2")
        res4 = alc15_2.parse("/core15_2")
        assert res4.matched is False
        assert cap["output"] == '无法解析 "/core15_2"。您想要输入的是不是 "1 core15_2" ?'
    with output_manager.capture("core15_2") as cap:
        output_manager.set_action(lambda x: x, "core15_2")
        res5 = alc15_2.parse([2, "core15_2"])
        assert res5.matched is False
        assert cap["output"] == '无法解析 "2 core15_2"。您想要输入的是不是 "1 core15_2" ?'

    alc15_3 = Alconna("core15_3", Option("rank", compact=True), meta=CommandMeta(fuzzy_match=True))
    with output_manager.capture("core15_3") as cap:
        output_manager.set_action(lambda x: x, "core15_3")
        res6 = alc15_3.parse("core15_3 runk")
        assert res6.matched is False
        assert cap["output"] == '无法解析 "runk"。您想要输入的是不是 "rank" ?'


def test_shortcut():
    from arclet.alconna import output_manager

    # 原始命令
    alc16 = Alconna("core16", Args["foo", int], Option("bar", Args["baz", str]))
    assert alc16.parse("core16 123 bar abcd").matched is True
    # 构造体缩写传入；{i} 将被可能的正则匹配替换
    alc16.shortcut(r"TEST(\d+)(.+)", {"args": ["{0}", "bar {1}"]})
    res = alc16.parse("TEST123aa")
    assert res.matched is True
    assert res.foo == 123
    assert res.baz == "aa"
    # 指令缩写传入， TEST1 -> core16 321
    alc16.parse("core16 --shortcut TEST1 'core16 321'")
    res1 = alc16.parse("TEST1")
    assert res1.foo == 321
    # 指令缩写传入的允许后随参数
    alc16.parse("core16 --shortcut TEST2 core16")
    res2 = alc16.parse("TEST2 442")
    assert res2.foo == 442
    # 指令缩写也支持正则
    alc16.parse(r"core16 --shortcut TESTa4(\d+) 'core16 {0}'")
    res3 = alc16.parse("TESTa4257")
    assert res3.foo == 257
    alc16.shortcut("tTest", {})
    assert alc16.parse("tTest123").matched

    alc16_1 = Alconna("exec", Args["content", str])
    alc16_1.shortcut("echo", command="exec print({%0})")
    alc16_1.shortcut("echo1", command="exec print(\\'{*\n}\\')")
    res5 = alc16_1.parse("echo 123")
    assert res5.content == "print(123)"
    assert not alc16_1.parse("echo 123 456").matched
    res6 = alc16_1.parse(["echo1", "123", "456 789"])
    assert res6.content == "print('123\n456\n789')"
    res7 = alc16_1.parse([123])
    assert not res7.matched
    res8 = alc16_1.parse("echo \\\\'123\\\\'")
    assert res8.content == "print('123')"
    assert not alc16_1.parse("echo").matched
    assert alc16_1.parse("echo1").content == "print('')"

    alc16_2 = Alconna([1, 2, "3"], "core16_2", Args["foo", bool])
    alc16_2.shortcut("test", {"command": [1, "core16_2 True"]})  # type: ignore
    assert alc16_2.parse([1, "core16_2 True"]).matched
    res9 = alc16_2.parse("test")
    assert res9.foo is True
    assert not alc16_2.parse([2, "test"]).matched
    assert not alc16_2.parse("3test").matched

    alc16.parse("core16 --shortcut list")

    alc16_3 = Alconna(["/", "!"], "core16_3", Args["foo", bool])
    print(alc16_3.shortcut("test", {"prefix": True, "args": ["False"]}))
    assert not alc16_3.parse("test").matched
    assert alc16_3.parse("/test").foo is False

    alc16_4 = Alconna("core16_4")
    alc16_4.shortcut("test", {"fuzzy": False})
    assert alc16_4.parse("test").matched
    assert not alc16_4.parse("tes").matched
    assert not alc16_4.parse("testtt").matched
    assert not alc16_4.parse("test t").matched
    alc16_4.parse("core16_4 --shortcut test1")
    assert alc16_4.parse("test1").matched

    alc16_5 = Alconna(["*", "+"], "core16_5", Args["foo", bool])
    alc16_5.shortcut("test", {"prefix": True, "args": ["True"]})
    assert alc16_5.parse("*core16_5 False").matched
    assert alc16_5.parse("+test").foo is True

    def wrapper(slot, content):
        if content == "help":
            return "--help"
        return content

    alc16_6 = Alconna("core16_6", Args["bar", str])
    alc16_6.shortcut("test(?P<bar>.+)?", fuzzy=False, wrapper=wrapper, arguments=["{bar}"])
    assert alc16_6.parse("testabc").bar == "abc"

    with output_manager.capture("core16_6") as cap:
        output_manager.set_action(lambda x: x, "core16_6")
        alc16_6.parse("testhelp")
        assert cap["output"] == """\
core16_6 <bar: str> 
Unknown
快捷命令:
'test(?P<bar>.+)?' => core16_6 {bar}\
"""

    alc16_7 = Alconna("core16_7", Args["bar", str])
    alc16_7.shortcut("test 123", {"args": ["abc"]})
    assert alc16_7.parse("test 123").bar == "abc"

    alc16_8 = Alconna("core16_8", Args["bar", str])
    res11 = alc16_8.parse("core16_8 1234")
    assert res11.bar == "1234"
    alc16_8.parse("core16_8 --shortcut test _")
    res12 = alc16_8.parse("test")
    assert res12.bar == "1234"

    alc16_9 = Alconna("core16_9", Args["bar", str])
    alc16_9.shortcut("test(.+)?", command="core16_9 {0}")
    assert alc16_9.parse("test123").bar == "123"
    assert not alc16_9.parse("test").matched

    alc16_10 = Alconna("core16_10", Args["bar", str]["baz", int])
    alc16_10.shortcut("/qux", {"command": "core16_10"})

    assert alc16_10.parse(['/qux "abc def.zip"', 123]).bar == "abc def.zip"

    alc16_11 = Alconna("core16_11", Args["bar", str])
    pat = re.compile("test", re.I)
    alc16_11.shortcut(pat, {"command": "core16_11"})
    assert alc16_11.parse("TeSt 123").bar == "123"


def test_help():
    from arclet.alconna import output_manager
    from arclet.alconna.exceptions import SpecialOptionTriggered

    alc17 = Alconna(
        "core17",
        Option("foo", Args["bar", str], help_text="Foo bar"),
        Option("baz", Args["qux", str], help_text="Baz qux"),
        Subcommand("add", Args["bar", str], help_text="Add bar"),
        Subcommand("del", Args["bar", str], help_text="Del bar"),
    )
    with output_manager.capture("core17") as cap:
        output_manager.set_action(lambda x: x, "core17")
        res = alc17.parse("core17 --help")
        assert isinstance(res.error_info, SpecialOptionTriggered)
        assert cap["output"] == (
            "core17 \n"
            "Unknown\n"
            "\n"
            "可用的子命令有:\n"
            "* Add bar\n"
            "  add <bar: str> \n"
            "* Del bar\n"
            "  del <bar: str> \n"
            "可用的选项有:\n"
            "* Foo bar\n"
            "  foo <bar: str> \n"
            "* Baz qux\n"
            "  baz <qux: str> \n"
        )
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 --help foo")
        assert cap["output"] == "foo <bar: str> \nFoo bar"
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 foo --help")
        assert cap["output"] == "foo <bar: str> \nFoo bar"
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 --help baz")
        assert cap["output"] == "baz <qux: str> \nBaz qux"
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 baz --help")
        assert cap["output"] == "baz <qux: str> \nBaz qux"
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 add --help")
        assert cap["output"] == "add <bar: str> \nAdd bar"
    with output_manager.capture("core17") as cap:
        alc17.parse("core17 del --help")
        assert cap["output"] == "del <bar: str> \nDel bar"
    alc17_1 = Alconna(
        "core17_1",
        Option("foo bar abc baz", Args["qux", int]),
        Option("foo qux bar", Args["baz", str]),
    )
    alc17_1.parse("core17_1 --help")
    alc17_1.parse("core17_1 --help aaa")
    alc17_2 = Alconna(
        "core17_2",
        Subcommand(
            "foo",
            Args["abc", str],
            Option("bar", Args["baz", str], help_text="Foo bar"),
            help_text="sub Foo",
        ),
    )
    with output_manager.capture("core17_2") as cap:
        alc17_2.parse("core17_2 --help foo bar")
        assert cap["output"] == "bar <baz: str> \nFoo bar"
    with output_manager.capture("core17_2") as cap:
        alc17_2.parse("core17_2 --help foo")
        assert cap["output"] == "foo <abc: str> \nsub Foo\n\n可用的选项有:\n* Foo bar\n  bar <baz: str> \n"


def test_hide_annotation():
    alc18 = Alconna("core18", Args["foo", int])
    print(alc18.get_help())
    alc18_1 = Alconna("core18_1", Args["foo;/", int])
    print(alc18_1.get_help())


def test_args_notice():
    alc19 = Alconna("core19", Args["foo#A TEST;?", int]) + Option("bar", Args["baz#ANOTHER TEST", KeyWordVar(str)])
    print("")
    print(alc19.get_help())


def test_completion():
    from arclet.alconna.exceptions import SpecialOptionTriggered

    alc20 = (
        "core20"
        + Option("fool")
        + Option(
            "foo",
            Args["bar", "a|b|c", Field(completion=lambda: "choose a, b or c")],
        )
        + Option(
            "off",
            Args["baz", "aaa|aab|abc", Field(completion=lambda: ["use aaa", "use aab", "use abc"])],
        )
        + Args["test", int, Field(1, completion=lambda: "try -1")]
    )

    alc20.parse("core20 --comp")
    alc20.parse("core20 f --comp")
    alc20.parse("core20 fo --comp")
    alc20.parse("core20 foo --comp")
    alc20.parse("core20 fool --comp")
    alc20.parse("core20 off b --comp")

    alc20_1 = Alconna("core20_1", Args["foo", int], Option("bar"))
    res = alc20_1.parse("core20_1 -cp")
    assert isinstance(res.error_info, SpecialOptionTriggered)


def test_completion_interface():
    alc21 = Alconna("core21", Args["foo", int], Args["bar", str])
    assert not alc21.parse("core21").matched
    with CompSession(alc21) as comp:
        alc21.parse("core21")
    assert comp.available
    assert comp.current() == "<foo: int>"
    assert comp.tab() == "<foo: int>"
    res = comp.enter(["1"])
    assert not res.exception
    assert comp.current() == "<bar: str>"
    res1 = comp.enter(["a"])
    assert res1.result and res1.result.matched

    alc21_1 = Alconna("core21_1", Args["foo", int], Args["bar", str])
    with CompSession(alc21_1) as comp:
        alc21_1.parse("core21_1 aaa bbb")
    assert comp.available
    assert comp.current() == "<foo: int>"
    res = comp.enter(["1"])
    assert res.result and res.result.matched

    with CompSession(alc21_1) as comp:
        alc21_1.parse("core21_1 aaa")
    assert comp.available
    assert comp.current() == "<foo: int>"
    comp.enter(["1"])
    assert comp.current() == "<bar: str>"
    res = comp.enter(["a"])
    assert res.result and res.result.matched

    alc21_2 = Alconna("core21_2", Args["foo", int], Args["bar", str])
    with CompSession(alc21_2) as comp:
        alc21_2.parse(["core21_2", ..., "bbb"])
    assert comp.available
    assert comp.current() == "<foo: int>"
    res = comp.enter(["1"])
    assert res.result and res.result.matched

    with CompSession(alc21_2) as comp:
        alc21_2.parse(["core21_2 123", ...])
    assert comp.available
    assert comp.current() == "<bar: str>"
    res = comp.enter(["a"])
    assert res.result and res.result.matched

    with CompSession(alc21_2) as comp:
        alc21_2.parse(["core21_2", 123, ...])
    assert comp.available
    assert comp.current() == "<bar: str>"
    res = comp.enter(["a"])
    assert res.result and res.result.matched


def test_call():
    from dataclasses import dataclass

    alc22 = Alconna("core22", Args["foo", int], Args["bar", str])
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

    alc22_1 = Alconna("core22_1", Args["name", str])

    @alc22_1.bind()
    @dataclass
    class A:
        name: str

    alc22_1.parse("core22_1 abc")
    assert alc22_1.exec_result["A"] == A("abc")


def test_nest_subcommand():
    class A:
        pass

    alc23 = Alconna(
        "core23",
        Args["foo", int],
        Subcommand(
            "bar|baar",
            Subcommand("baz|baaz", Option("--qux"), dest="Baz", help_text="test nest subcommand; deep 2"),
            Args["abc", A],
            dest="Bar",
            help_text="test nest subcommand; deep 1",
        ),
        meta=CommandMeta("test nest subcommand"),
    )
    assert alc23.parse("core23 123").matched
    assert alc23.parse(["core23 bar baz", A(), "123"]).matched
    assert alc23.parse(["core23 bar baz --qux", A(), "123"]).matched
    assert not alc23.parse(["core23 bar baz", A(), "--qux 123"]).matched
    assert alc23.parse(["core23 bar baz --qux", A(), "123"]).query("Bar.Baz.qux.value") is Ellipsis
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
    from typing import List

    from arclet.alconna import append, append_value, count, store_true

    alc24 = Alconna("core24", Option("--yes|-y", action=store_true), Args["module", AllParam])
    res = alc24.parse("core24 -y abc def")
    assert res.query[bool]("yes.value") is True
    assert res.module == ["abc def"]

    alc24_1 = Alconna("core24", Args["yes", {"--yes": True, "-y": True}, False]["module", AllParam])
    assert alc24_1.parse("core24 -y abc def").yes
    assert not alc24_1.parse("core24 abc def").yes
    assert alc24_1.parse("core24 abc def").module == ["abc def"]

    alc24_2 = Alconna(
        "core24_2",
        Option("--i", Args["foo", int]),
        Option("--a|-A", action=append_value(1)),
        Option("--flag|-F", Args["flag", str], action=append, compact=True),
        Option("-v", action=count),
        Option("-x|--xyz", action=count),
        Option("--q", action=count, requires=["foo", "bar"]),
    )
    res = alc24_2.parse(
        "core24_2 -A --a -vvv -x -x --xyzxyz " "-Fabc -Fdef --flag xyz --i 4 --i 5 " "foo bar --q foo bar --qq"
    )
    assert res.query[int]("i.foo") == 5
    assert res.query[List[int]]("a.value") == [1, 1]
    assert res.query[List[str]]("flag.flag") == ["abc", "def", "xyz"]
    assert res.query[int]("v.value") == 3
    assert res.query[int]("xyz.value") == 4
    assert res.query[int]("foo_bar_q.value") == 3

    alc24_3 = Alconna("core24_3", Option("-t", default=False, action=append_value(True)))
    assert alc24_3.parse("core24_3 -t -t -t").query("t.value") == [True, True, True]


def test_default():
    from arclet.alconna import OptionResult, append, store_true, store_value

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
        Subcommand("test", Option("--bar", default=False, action=store_true)),
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


def test_conflict():
    core26 = Alconna(
        "core26",
        Option("--foo", Args["bar", str]),
        Option("--bar"),
        Option("--baz", Args["qux?", str]),
        Option("--qux"),
    )
    res1 = core26.parse("core26 --foo bar --bar")
    assert res1.matched
    assert res1.find("options.bar")

    res2 = core26.parse("core26 --foo --bar")
    assert res2.matched
    assert res2.query[str]("foo.bar") == "--bar"
    assert not res2.find("options.bar")

    res3 = core26.parse("core26 --foo bar --baz qux")
    assert res3.matched
    assert res3.query[str]("foo.bar") == "bar"
    assert res3.query[str]("baz.qux") == "qux"

    res4 = core26.parse("core26 --baz --qux")
    assert res4.matched
    assert res4.find("options.baz")
    assert res4.query[str]("baz.qux", "unknown") == "unknown"
    assert res4.find("options.qux")

    core26_1 = Alconna(
        "core26_1",
        Option("--foo", Args["bar", int]),
        Option("--bar"),
        Option("--baz", Args["qux?", int]),
        Option("--qux"),
    )
    res5 = core26_1.parse("core26_1 --foo 123 --bar")
    assert res5.matched
    assert res5.query[int]("foo.bar") == 123
    assert res5.find("options.bar")

    res6 = core26_1.parse("core26_1 --foo --bar")
    assert not res6.matched

    res7 = core26_1.parse("core26_1 --foo 123 --baz 321")
    assert res7.matched

    res8 = core26_1.parse("core26_1 --baz --qux")
    assert res8.matched


def test_tips():
    from typing import Literal

    core27 = Alconna(
        "core27",
        Args["arg1", Literal["1", "2"], Field(unmatch_tips=lambda x: f"参数arg必须是1或2哦，不能是{x}")],
        Args["arg2", Literal["1", "2"], Field(missing_tips=lambda: "缺少了arg参数哦")],
    )
    assert core27.parse("core27 1 1").matched
    assert str(core27.parse("core27 3 1").error_info) == "参数arg必须是1或2哦，不能是3"
    assert str(core27.parse("core27 1").error_info) == "缺少了arg参数哦"
    assert str(core27.parse("core27 1 3").error_info) in ("参数 '3' 不正确, 其应该符合 \"'1'|'2'\"", "参数 '3' 不正确, 其应该符合 \"'2'|'1'\"")
    assert str(core27.parse("core27").error_info) == "参数 arg1 丢失"


def test_disable_builtin_option():
    with namespace("test"):
        core28 = Alconna("core28")
        core28_1 = Alconna("core28_1", Args["text", MultiVar(str)])
    core28.namespace_config.disable_builtin_options.add("shortcut")

    res = core28.parse("core28 --shortcut 123 test")
    assert not res.matched
    assert str(res.error_info) == "参数 --shortcut 匹配失败"

    res1 = core28_1.parse("core28_1 --shortcut 123 test")
    assert res1.matched
    assert res1.query("text") == ("--shortcut", "123", "test")

    with namespace("test1") as ns:
        ns.disable_builtin_options.add("help")
        core28_2 = Alconna("core28_2", Option("--help"))

    res2 = core28_2.parse("core28_2 --help")
    assert res2.matched
    assert res2.find("help")


def test_extra_allow():
    core29 = Alconna("core29", Option("--foo", Args["bar", str]), meta=CommandMeta(strict=False))
    assert core29.parse("core29 --foo bar").matched
    res = core29.parse("core29 --foo --bar --baz --qux")
    assert res.matched
    assert res.query[str]("foo.bar") == "--bar"
    assert res.all_matched_args.get("$extra", []) == ["--baz", "--qux"]


if __name__ == "__main__":
    pytest.main([__file__, "-vs"])
