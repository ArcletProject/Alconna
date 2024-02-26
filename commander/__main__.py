from arclet.alconna import Alconna, Args, command_manager
from commander import Commands

command = Commands()


@command.on(Alconna("help", Args["page", int, 0]))
def cb(commander: Commands):
    print(commander.executors)
    print(command_manager.all_command_help(True, max_length=10))


@command.on(Alconna(Args["foo", str]["bar", int, 2]))
async def cb1(foo: str, bar: int):
    print("foo:", foo)
    print("bar:", bar)
    print(foo*bar)


if __name__ == '__main__':
    import asyncio

    async def main():
        await command.broadcast()

    asyncio.run(main())
