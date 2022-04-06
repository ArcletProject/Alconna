from arclet.alconna.graia import Alconna, AlconnaDispatcher, AlconnaHelpMessage
from arclet.alconna import all_command_help, Args, Arpamar, AlconnaDuplication
from arclet.alconna import ArgsStub

from graia.broadcast import Broadcast
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.model import Member, Group
from graia.ariadne.app import Ariadne
from graia.ariadne.adapter import MiraiSession
from graia.ariadne.context import ariadne_ctx
import asyncio

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop)

bot = Ariadne(loop=loop, broadcast=bcc,
              use_loguru_traceback=False,
              connect_info=MiraiSession(host="http://localhost:8080", verify_key="1234567890abcdef", account=123456789))

alc = Alconna(
    command="!test",
    is_raise_exception=True,
    help_text="test_dispatch"
)

alc1 = Alconna(
    command="!jrrp",
    main_args=Args["sth":str:1123]
)


ariadne_ctx.set(bot)


@bcc.receiver(
    GroupMessage, dispatchers=[
        AlconnaDispatcher(alconna=alc, help_flag='post', skip_for_unmatch=True)
    ]
)
async def test(group: Group, result: Arpamar):
    print("test:", result)
    print("listener:", group)
    print(all_command_help())


# @bcc.receiver(
#     FriendMessage, dispatchers=[
#         AlconnaDispatcher(alconna=alc1, help_flag='stay')
#     ]
# )
# async def test(friend: Friend, sth: ArgsStub):
#     print("sign:", sth.origin)
#     print("listener:", friend)


@bcc.receiver(
    GroupMessage, dispatchers=[
        AlconnaDispatcher(alconna=alc1, help_flag='post')
    ]
)
async def test2(group: Group, result: Arpamar):
    print("sign:", result)
    print("listener:", group)


@bcc.receiver(AlconnaHelpMessage)
async def test_event(help_string: str, app: Ariadne, event: GroupMessage):
    print(help_string)
    print(app)
    print(event.sender.group)


m1 = Member(id=12345678, memberName="test1", permission="MEMBER", group=Group(id=987654321, name="test", permission="OWNER"))
m2 = Member(id=54322411, memberName="test2", permission="MEMBER", group=Group(id=123456789, name="test", permission="OWNER"))
m3 = Member(id=42425665, memberName="test3", permission="MEMBER", group=Group(id=987654321, name="test", permission="OWNER"))
#frd = Friend.parse_obj({"id": 12345678, "nickname": "test", "remark": "none"})
#frd1 = Friend.parse_obj({"id": 54322411, "nickname": "test1", "remark": "none1"})
msg = MessageChain.create(f"!test --help")
msg1 = MessageChain.create(f"!jrrp --help")
ev = GroupMessage(sender=m1, messageChain=msg)
ev1 = GroupMessage(sender=m2, messageChain=msg1)
ev2 = GroupMessage(sender=m3, messageChain=msg)


async def main():
    bcc.postEvent(ev)
    await asyncio.sleep(0.1)
    bcc.postEvent(ev1)
    await asyncio.sleep(0.1)
    bcc.postEvent(ev2)
    await asyncio.sleep(0.1)


loop.run_until_complete(main())
