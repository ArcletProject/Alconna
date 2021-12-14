from commander.letoderea import AlconnaCommander, Positional
from devtools import debug
from asyncio import sleep
from arclet.letoderea import EventSystem

es = EventSystem()
commander = AlconnaCommander(es)


@commander.command("lp user {0} permission set {1} {2}")
async def user_permission_set(
        target: str = Positional(0, type=str),
        perm_node: str = Positional(1, type=str),
        perm_value: bool = Positional(2, type=bool, default=True),

):
    print("target", target)
    print("perm_node", perm_node)
    print("perm_value", perm_value)


debug(commander)


async def main():
    commander.post_message("lp user AAA permission set admin")
    await sleep(0.1)


commander.broadcast.loop.run_until_complete(main())
