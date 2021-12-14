from arclet.alconna.commander.broadcast import AlconnaCommander, Positional, AdditionParam
from devtools import debug
from asyncio import sleep
from graia.broadcast import Broadcast

bcc = Broadcast()
commander = AlconnaCommander(bcc)


@commander.command("lp user {0} permission set {1} {2}")
async def user_permission_set(
        target: str = Positional(0, type=str),
        perm_node: str = Positional(1, type=str),
        perm_value: bool = Positional(2, type=bool, default=True),
        param1: bool = AdditionParam(['-p1', '--param1'], type=bool, default=False),
        param2: str = AdditionParam(['-p2 {0}', '--param2 {0}'], type=str, default="default")

):
    print("target", target)
    print("perm_node", perm_node)
    print("perm_value", perm_value)
    print("param1", param1)
    print("param2", param2)


debug(commander)


async def main():
    commander.post_message("lp user AAA permission set admin False -p2 a")
    await sleep(0.1)


commander.broadcast.loop.run_until_complete(main())