from arclet.alconna.types import ObjectPattern, set_converter, ArgPattern, PatternToken
from arclet.alconna import AlconnaFire
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain, Image, At, MusicShare
from graia.ariadne.app import Ariadne, MiraiSession

bot = Ariadne(connect_info=MiraiSession(host="http://localhost:8080", verify_key="1234567890abcdef", account=123456789))

set_converter(ArgPattern("ariadne", PatternToken.REGEX_TRANSFORM, Ariadne, lambda x: bot, 'app'))
ObjectPattern(Plain, limit=("text",))
ObjectPattern(Image, limit=("url",))
ObjectPattern(At, limit=("target",))
ObjectPattern(MusicShare, flag="json")


async def test(app: Ariadne, text: Plain, img: Image, at: At, music: MusicShare):
    print(locals())
    msg = MessageChain.create([at, text, img])
    print(repr(msg))
    print(await app.sendGroupMessage(at.target, msg))


alc = AlconnaFire(test)
alc.parse("test ariadne 'hello world!' https://www.baidu.com/img/bd_logo1.png 123456 \"{'kind':'QQMusic','title':'音乐标题','summary':'音乐摘要','jumpUrl':'http://www.baidu.com','pictureUrl':'http://www.baidu.com/img/bd_logo1.png','musicUrl':'http://www.baidu.com/audio/bd.mp3','brief':'简介'}\"")
