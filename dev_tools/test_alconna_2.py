from typing import Union, Dict

from arclet.alconna.builtin.construct import AlconnaString, AlconnaFormat
from arclet.alconna.types import UnionArg, pattern
from arclet.alconna import Alconna, Args, Option
from arclet.alconna import command_manager
from graia.ariadne.message.element import At
from devtools import debug

print(command_manager)

ping = "Test" @ AlconnaString("ping <url:url>")
ping1 = AlconnaString("ping <url:url>")

Alconna.set_custom_types(digit=int)
alc = AlconnaFormat(
    "lp user {target} perm set {perm} {default}",
    {"target": str, "perm": str, "default": Args["de":bool:True]},
)
alcc = AlconnaFormat(
    "lp1 user {target}",
    {"target": str}
)

alcf = AlconnaFormat("music {artist} {title:str} singer {name:str}")
print(alcf.parse("music --help"))
debug(alc)
alc.exception_in_time = False
debug(alc.parse("lp user AAA perm set admin"))

aaa = AlconnaFormat("a {num}", {"num": int})
r = aaa.parse("a 1")
print(aaa)
print(r)
print('\n')


def test(wild, text: str, num: int, boolean: bool = False):
    print('wild:', wild)
    print('text:', text)
    print('num:', num)
    print('boolean:', boolean)


alc1 = Alconna("test5", action=test)

print(alc1)


@pattern("test_type", r"(\[.*?])")
def test_type(text: str):
    return eval(text)


alc2 = Alconna("test", help_text="测试help直接发送") + Option("foo", Args["bar":str, "bar1":int:12345, "bar2":test_type])
print(alc2.parse("test --help"))

alc4 = Alconna(
    command="test_multi",
    options=[
        Option("--foo", Args["tags;S":str:1, "str1":str]),
        Option("--bar", Args["num": int]),
    ]
)

print(alc4.parse("test_multi --foo ab --bar 1"))
alc4.shortcut("st", "test_multi --foo ab --bar 1")
result = alc4.parse("st")
print(result)
print(result.get_first_arg("foo"))

alc5 = Alconna("test_anti", "path;A:int")
print(alc5.parse("test_anti a"))

alc6 = Alconna("test_union", main_args=Args.path[UnionArg[int, float, 'abc']])
print(alc6.parse("test_union abc"))
print(alc6.parse(["test_union 123"]))

alc7 = Alconna("test_list", main_args=Args.seq[list])
print(alc7)
print(alc7.parse("test_list \"['1', '2', '3']\""))

alc8 = Alconna("test_dict", main_args=Args.map[Dict[str, int]])
print(alc8)
print(alc8.parse("test_dict {'a':1,'b':2}"))

alc9 = Alconna("test_str", main_args="foo;K:str, bar:list, baz;O:int")
print(alc9)
print(alc9.parse("test_str foo=a \"[1]\""))

alc10 = Alconna("test_bool", main_args="foo;H|O:str")
print(alc10.parse(["test_bool", 1]))
print(alc10.get_help())

alc11 = Alconna("test_header", headers=[(At(123456), "abc")])
print("alc11:", alc11.parse([At(123456), "abctest_header"]))

alc12 = Alconna("test_str1", Args["abcd", "1234"])
print("alc12:", alc12.parse("test_str1 abcd 1234"))

alc13 = Alconna("image", Args["--width;O|K":int:1920, "--height;O|K":int:1080])
print("alc13:", alc13.parse("image --height=720"))

alc14 = Alconna(main_args="foo:str", headers=['!test_fuzzy'], is_fuzzy_match=True)
print(alc14.parse("test_fuzy foo bar"))

alc15 = AlconnaString("my_string", "--foo <foo:str:'123'> [bar:bool]", "--bar &True")
print(alc15.parse("my_string --foo 123 --bar"))

alc16 = Alconna(
    "发涩图",
    Args["min":r"(\d+)张", "?max":r"(\d+)张"] / "到",
    options=[Option("从", Args["tags;3":str] / "和")],
    action=lambda x, y: (int(x), int(y))
)
print(alc16.parse("发涩图 3张到5张 从 方舟和德能和拉德"))
