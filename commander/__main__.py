from arclet.alconna import Alconna, command_manager, Args
from commander import Commands

command = Commands()


@command.on(Alconna("help", Args["page", int, 0]))
def cb():
    print(command_manager.all_command_help(True, max_length=10))


@command.on(Alconna(Args["foo", str]["bar", int, 2]))
def cb1(foo: str, bar: int):
    print("foo:", foo)
    print("bar:", bar)
    print(foo*bar)


if __name__ == '__main__':
    command.test()
