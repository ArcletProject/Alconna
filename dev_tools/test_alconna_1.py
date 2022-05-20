from typing import Union, Any

from arclet.alconna import Alconna, Args, AlconnaString, Subcommand, Option
from graia.ariadne.message.chain import MessageChain
from arclet.alconna.builtin.formatter import ArgParserTextFormatter

from graia.ariadne.message.element import At

ar = Args["test":bool:True]["aaa":str:"bbb"] << Args["perm":str:...] + ["month", int]
a = "bbb"
b = str
c = "fff"
ar1 = Args[a:b:c]
ar["foo"] = ["bar", ...]
print(ar)
print(ar1)

ping = Alconna(
    headers=["/", "!"],
    command="ping",
    options=[
        Subcommand(
            "test", [Option("-u", Args["username":str], help_text="输入用户名")], args=Args["test":"Test"],
            help_text="测试用例"
        ),
        Option("-n|--num", Args["count":int:123], help_text="输入数字"),
        Option("-u", Args(At=At), help_text="输入需要At的用户")
    ],
    main_args=Args["IP":"ip"],
    help_text="简单的ping指令"
)
print(ping.get_help())
msg = MessageChain.create("/ping -u", At(123), "test Test -u AAA -n 222 127.0.0.1")
print(msg)
print(ping.parse(msg))

msg1 = MessageChain.create("/ping 127.0.0.1 -u", At(123))
print(msg1)
print(ping.parse(msg1).all_matched_args)

msg2 = MessageChain.create("/ping a")
print(msg2)
result = ping.parse(msg2)
print(result.header)
print(result.head_matched)

pip = Alconna(
    command="/pip",
    options=[
        Subcommand("install", [Option("--upgrade", help_text="升级包")], Args["pak":str], help_text="安装一个包"),
        Option("--retries", Args["retries":int], help_text="设置尝试次数"),
        Option("-t| --timeout", Args["sec":int], help_text="设置超时时间"),
        Option("--exists-action", Args["action":str], help_text="添加行为"),
        Option("--trusted-host", Args["host_name":"url"], help_text="选择可信赖地址")
    ],
    help_text="简单的pip指令",
    formatter=ArgParserTextFormatter()
)
print(pip.get_help())
msg = "/pip install ces --upgrade -t 6 --trusted-host http://pypi.douban.com/simple"
print(msg)
print(pip.parse(msg).all_matched_args)

aaa = Alconna(headers=[".", "!"], command="摸一摸", main_args=Args["At":At])
msg = MessageChain.create(".摸一摸", At(123))
print(msg)
print(aaa.parse(msg).matched)

ccc = Alconna(
    headers=[""],
    command="4help",
    main_args=Args["aaa":str],
)
msg = "4help 'what he say?'"
print(msg)
result = ccc.parse(msg)
print(result.main_args)

eee = Alconna("RD{r:int}?=={e:int}")
msg = "RD100==36"
result = eee.parse(msg)
print(result.header)

weather = Alconna(
    headers=['渊白', 'cmd.', '/bot '],
    command="{city}天气",
    options=[
        Option("时间", "days:str").separate('='),
    ],
)
msg = MessageChain.create('渊白桂林天气 时间=明天')
result = weather.parse(msg)
print(result)
print(result.header)

msg = MessageChain.create('渊白桂林天气 aaa bbb')
result = weather.parse(msg)
print(result)

msg = MessageChain.create(At(123))
result = weather.parse(msg)
print(result)

ddd = Alconna(
    command="Cal",
    options=[
        Subcommand(
            "-div",
            options=[
                Option(
                    "--round| -r",
                    args=Args(decimal=int),
                    action=lambda x: f"{x}a",
                    help_text="保留n位小数",
                )
            ],
            args=Args(num_a=int, num_b=int),
            help_text="除法计算",
        )
    ],
)

msg = "Cal -div 12 23 --round 2"
print(msg)
print(ddd.get_help())
result = ddd.parse(msg)
print(result.div)

ddd = Alconna(
    "点歌"
).add_option(
    "歌名", sep="：", args=Args(song_name=str)
).add_option(
    "歌手", sep="：", args=Args(singer_name=str)
)
msg = "点歌 歌名：Freejia"
print(msg)
result = ddd.parse(msg, static=False)
print(result.all_matched_args)

give = AlconnaString("give <sb:int:...> <sth:int:...>")
print(give)
print(give.parse("give"))


def test_act(content):
    print(content)
    return content


wild = Alconna(
    headers=[At(12345)],
    command="丢漂流瓶",
    main_args=Args["wild":Any],
    action=test_act,
    help_text="丢漂流瓶"
)
# print(wild.parse("丢漂流瓶 aaa bbb ccc").all_matched_args)
msg = MessageChain.create(At(12345), " 丢漂流瓶 aa\t\nvv")
print(wild.parse(msg))

get_ap = Alconna(
    command="AP",
    main_args=Args(type=str, text=str)
)

test = Alconna(
    command="test",
    main_args=Args(t=int)
).reset_namespace("TEST")
print(test)
print(test.parse([get_ap.parse("AP Plain test"), get_ap.parse("AP At 123")]))

# print(command_manager.commands)

double_default = Alconna(
    command="double",
    main_args=Args(num=int).default(num=22),
    options=[
        Option("--d", Args(num1=int).default(num1=22))
    ]
)

result = double_default.parse("double --d")
print(result)

choice = Alconna(
    command="choice",
    main_args=Args["part":["a", "b", "c"]],
    help_text="选择一个部分"
)
print(choice.parse("choice d"))
print(choice.get_help())

sub = Alconna(
    command="test_sub_main",
    options=[
        Subcommand(
            "sub",
            options=[Option("--subOption", Args["subOption":Union[At, int]])],
            args=Args.foo[str]
        )
    ]
)
print(sub.get_help())
res = sub.parse("test_sub_main sub --subOption 123 a")
print(res)
print(res.query('sub.foo'))


