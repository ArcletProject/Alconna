from arclet.cesloi.event.messages import MessageChain
from arclet.cesloi.message.alconna import AlconnaParser
from arclet.alconna import Alconna, Option, Args, Arpamar, AnyStr, AnyParam
from arclet.letoderea import EventSystem
from arclet.cesloi.event.messages import FriendMessage
from arclet.cesloi.model.relation import Friend
import asyncio

es = EventSystem()


alc = Alconna(
    command="test",
    options=[
        Option("name", Args["pak":str]),
        Option("foo", Args["bar":bool:True])
    ]
)

# alc1 = Alconna(
#     command="商店",
#     options=[
#         Option("有", Args["good":str], actions=lambda x:x.split("和"))
#     ]
# ).separate("里")
alc1 = Alconna(
    command=f"{AnyStr}今天",
    main_args=Args["good":AnyParam],
    actions=lambda x: x.split("和")
).separate('吃')


@es.register(FriendMessage, decorators=[AlconnaParser(alconna=alc1)])
async def test_action(frd: Friend, result: Arpamar):
    print(frd)
    print(result.header)
    print(result.good)


friend = Friend(id=3165388245, nickname="RF")
msg = MessageChain.create("test name ces foo False")
fri_msg = FriendMessage(messageChain=msg, sender=friend)
msg1 = MessageChain.create("test name les foo True")
fri_msg1 = FriendMessage(messageChain=msg1, sender=friend)

msg2 = MessageChain.create("嘉然今天吃鱼和薯条")

fri_msg2 = FriendMessage(messageChain=msg2, sender=friend)


async def main(msg):
    es.event_spread(msg)
    await asyncio.sleep(0.1)

es.loop.run_until_complete(main(fri_msg2))
