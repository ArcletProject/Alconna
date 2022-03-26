from arclet.alconna.graia import Alconna, AlconnaDispatcher, AlconnaHelpMessage
from arclet.alconna import all_command_help, Args, Arpamar, AlconnaDuplication
from arclet.alconna import ArgsStub

from graia.broadcast import Broadcast
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.event.message import FriendMessage
from graia.ariadne.model import Friend
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
    FriendMessage, dispatchers=[
        AlconnaDispatcher(alconna=alc, help_flag='post', skip_for_unmatch=True)
    ]
)
async def test(friend: Friend, result: Arpamar):
    print("test:", result)
    print("listener:", friend)
    print(all_command_help())


@bcc.receiver(
    FriendMessage, dispatchers=[
        AlconnaDispatcher(alconna=alc1, help_flag='reply')
    ]
)
async def test(friend: Friend, sth: ArgsStub):
    print("sign:", sth.origin)
    print("listener:", friend)


@bcc.receiver(
    FriendMessage, dispatchers=[
        AlconnaDispatcher(alconna=alc1, help_flag='post')
    ]
)
async def test2(friend: Friend, result: Arpamar):
    print("sign:", result)
    print("listener:", friend)


@bcc.receiver(AlconnaHelpMessage)
async def test_event(help_string: str, app: Ariadne, message: MessageChain):
    print(help_string)
    print(app)
    print(message.__repr__())


frd = Friend.parse_obj({"id": 12345678, "nickname": "test", "remark": "none"})
msg = MessageChain.create(f"!jrrp")
ev = FriendMessage(sender=frd, messageChain=msg)


async def main():
    bcc.postEvent(ev)
    await asyncio.sleep(0.1)


loop.run_until_complete(main())
