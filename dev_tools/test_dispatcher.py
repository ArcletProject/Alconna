from graia.ariadne.message.chain import MessageChain

from alconna_dispatcher import AlconnaDispatcher, Alconna, Arpamar, AlconnaHelpMessage
from arclet.alconna import all_command_help, Args
from graia.broadcast import Broadcast
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


@bcc.receiver(FriendMessage, dispatchers=[AlconnaDispatcher(alconna=alc, reply_help=True, skip_for_unmatch=True)])
async def test(friend: Friend, result: Arpamar, foo: dict):
    print("test:", result)
    print("listener:", friend)
    print(foo)
    print(all_command_help())


@bcc.receiver(FriendMessage, dispatchers=[AlconnaDispatcher(alconna=alc1, reply_help=True)])
async def test(friend: Friend, result: Arpamar, foo: dict):
    print("sign:", result)
    print("listener:", friend)
    print(foo)


@bcc.receiver(AlconnaHelpMessage)
async def test_event(help_string: str, app: Ariadne, message: MessageChain):
    print(help_string)
    print(app)
    print(message.__repr__())

frd = Friend(id=12345678, nickname="test", remark="none")
msg = MessageChain.create("!test --help")
ev = FriendMessage(sender=frd, messageChain=msg)

bcc.postEvent(ev)


async def main():
    await asyncio.sleep(0.1)


loop.run_until_complete(main())
