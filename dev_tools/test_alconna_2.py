from arclet.alconna.types import AnyStr, Bool, AnyDigit, ArgPattern
from arclet.alconna import Alconna, Args, Option
from arclet.alconna.actions import store_bool, change_help_send_action
from devtools import debug

change_help_send_action(lambda x: print(x))

Alconna.set_custom_types(digit=int)
alc = Alconna.format(
    "lp user {target} perm set {perm} {default}",
    {"target": AnyStr, "perm": AnyStr, "default": Args["de":bool:True]},
)
alcc = Alconna.format(
    "lp1 user {target}",
    {"target": str}
)


debug(alc)
alc.exception_in_time = False
debug(alc.analyse_message("lp user AAA perm set admin True"))

aaa = Alconna.format("a {num}", {"num": AnyDigit})
r = aaa.analyse_message("a 1")
print(aaa)
print(r)
print('\n')


def test(wild, text: str, num: int, boolean: bool):
    print('wild:', wild)
    print('text:', text)
    print('num:', num)
    print('boolean:', boolean)


alc1 = Alconna.from_string(
    "test_type <wild> <text:str> <num:digit> <boolean:bool:False> #测试",
    "--foo <bool> #测试选项",
).set_action(store_bool(True))
print(alc1)
print(alc1.get_help())
print(alc1.analyse_message("test_type abcd 'testing a text' 123456 True --foo False"))


test_type = ArgPattern(r"(\[.*?])", need_transform=True, type_mark=list)
alc2 = Alconna(
    command="test",
    options=[
        Option("foo", Args["bar":str, "bar1":int:12345, "bar2":test_type])
    ]
).help("测试help直接发送")
print(alc2.analyse_message("test --help"))