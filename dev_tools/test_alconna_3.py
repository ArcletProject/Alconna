from arclet.alconna import Args
from arclet.alconna.builtin.construct import AlconnaDecorate
from graia.broadcast import Broadcast, DispatcherInterface
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.entities.exectarget import ExecTarget
from arclet.letoderea.handler import await_exec_target
from arclet.letoderea.entities.event import TemplateEvent
import asyncio


loop = asyncio.new_event_loop()

c1 = AlconnaDecorate(loop=loop)
c2 = AlconnaDecorate(loop=loop)


@c1.set_default_parser
def _(func, args, l_args, loo):
    class _D(BaseDispatcher):
        async def catch(self, interface: DispatcherInterface):
            if interface.name in args:
                return args[interface.name]
            if interface.name in l_args:
                return l_args[interface.name]
            if interface.default:
                return interface.default

    target = ExecTarget(callable=func)
    loo.run_until_complete(bcc.Executor(target, [_D()]))


bcc = Broadcast(loop=loop)


@c2.set_default_parser
def _(func, args, l_args, loo):
    loo.run_until_complete(
        await_exec_target(
            func,
            TemplateEvent.param_export(**{**args, **l_args})
        )
    )


@c1.build_command()
@c1.option("--count", Args["num":int], help="Test Option Count")
@c1.option("--foo", Args["bar":str], help="Test Option Foo")
def hello(bar: str, num: int = 1):
    """测试DOC"""
    print(bar * num)


@c2.build_command("halo")
@c2.option("--count", Args["num":int], help="Test Option Count")
@c2.option("--foo", Args["bar":str], help="Test Option Foo")
def halo(bar: str, num: int = 1):
    """测试DOC"""
    print(bar * num)


if __name__ == "__main__":
    hello("hello --foo John")
