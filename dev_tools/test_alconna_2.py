from arclet.alconna.types import AnyStr, Bool, AnyDigit, ArgPattern
from arclet.alconna import Alconna, Args, Option
from arclet.alconna.actions import store_bool
from devtools import debug

Alconna.set_custom_types(digit=int)
alc = Alconna.format(
    "lp user {0} perm set {1} {2}",
    [AnyStr, AnyStr, Args["de":bool:True]],
    {"0": "target", "1": "perm"}
)
alcc = Alconna.format(
    "lp user {target}",
    {"target": str}
)

debug(alc)
alc.exception_in_time = False
debug(alc.analyse_message("lp user AAA perm set admin True"))

aaa = Alconna.format("a {num}", {"num": AnyDigit})
r = aaa.analyse_message("a 1")
print(aaa)
print(r)


def test(wild, text: str, num: int, boolean: bool):
    print('wild:', wild)
    print('text:', text)
    print('num:', num)
    print('boolean:', boolean)


alc1 = Alconna.from_string(
    "test_type <wild> <text:str> <num:digit> <boolean:bool=True>",
    "--foo <bool>",
).set_action(store_bool(True))
print(alc1)
print(alc1.analyse_message("test_type abcd 'testing a text' 123456 True --foo False"))

test_type = ArgPattern(
    r"(.+\.?.*?)",
    need_transform=True,
    type_mark=list,
    transform_action=lambda x: x.split(".")
)
alc2 = Alconna(
    command="test",
    options=[
        Option("foo", Args["bar":str, "bar1":int:12345, "bar2":test_type])
    ]
)
print(test_type)
print(alc2.analyse_message("test foo bar database.read").bar2)
