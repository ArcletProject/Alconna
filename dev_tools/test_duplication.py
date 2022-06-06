from arclet.alconna import Alconna, Args, Option, Subcommand
from arclet.alconna.components.duplication import AlconnaDuplication
from arclet.alconna.components.stub import ArgsStub, OptionStub, SubcommandStub


class Demo(AlconnaDuplication):
    testArgs: ArgsStub
    bar: OptionStub
    sub: SubcommandStub


alc = Alconna(
    "test",
    Args["foo", int],
    options=[
        Option("--bar", Args["bar", str]),
        Subcommand("sub", options=[Option("--sub1", Args["baz", str])])
    ]
)
result = alc.parse("test 123 --bar abc sub --sub1 xyz")
print(result)
duplication = alc.parse("test 123 --bar abc sub --sub1 xyz", duplication=Demo)
print(duplication)
print(duplication.testArgs.get('foo'))
print(duplication.bar.available)
print(duplication.bar.args[0])
print(duplication.subcommand("sub").available)
print(duplication.subcommand("sub").option("sub1").args.first_arg)
