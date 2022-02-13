from arclet.alconna import Args
from arclet.alconna.decorate import AlconnaDecorate
from graia.broadcast import Broadcast, DispatcherInterface
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.entities.exectarget import ExecTarget
from arclet.letoderea.handler import await_exec_target
import asyncio
# @c.set_parser
# def _(func, args, l_args, loo):
#     class _D(BaseDispatcher):
#         @staticmethod
#         async def catch(interface: DispatcherInterface):
#             if interface.name in args:
#                 return args[interface.name]
#             if interface.name in l_args:
#                 return l_args[interface.name]
#
#     target = ExecTarget(callable=func)
#     loo.run_until_complete(bcc.Executor(target, [_D]))
loop = asyncio.new_event_loop()

bcc = Broadcast(loop=loop)

c = AlconnaDecorate(loop=loop)


@c.set_default_parser
def _(func, args, l_args, loo):
    loo.run_until_complete(await_exec_target(func, {**args, **l_args}))


@c.build_command()
@c.option("--count", Args["num":int], help="Test Option Count")
@c.option("--foo", Args["bar":str], help="Test Option Foo")
def hello(bar: str, num: int = 1):
    """测试DOC"""
    print(bar*num)


if __name__ == "__main__":
    hello.from_commandline()
