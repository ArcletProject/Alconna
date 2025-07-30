from arclet.alconna.base import ArgsBase, arg_field
from arclet.alconna import Alconna


class Foo(ArgsBase):
    foo: str
    bar: int = arg_field(42)


alc = Alconna("test", Foo)


@alc.bind()
def cb(args: Foo):
    print(args.foo, args.bar)


print(alc.parse("test abc 123"))


class Bar(ArgsBase):
    foo: tuple[str, ...] = arg_field(multiple=True)


alc2 = Alconna("test2", Bar)
print(alc2.parse("test2 abc def ghi"))
