from arclet.alconna import Alconna, Option, Args, Subcommand, Arparma, ArparmaBehavior
from arclet.alconna.builtin import set_default
from arclet.alconna.duplication import Duplication, generate_duplication
from arclet.alconna.stub import ArgsStub, OptionStub, SubcommandStub
from arclet.alconna.output import output_manager
from arclet.alconna.model import OptionResult


def test_behavior():
    com = Alconna("comp", Args["bar", int]) + Option("foo", default=321)

    class Test(ArparmaBehavior):
        requires = [set_default(factory=lambda: OptionResult(321), path="option.baz")]

        @classmethod
        def operate(cls, interface: "Arparma"):
            print('\ncom: ')
            print(interface.query("options.foo.value"))
            print(interface.query("options.baz.value"))
            interface.behave_fail()

    com.behaviors.append(Test())
    assert com.parse("comp 123").matched is False


def test_duplication():
    class Demo(Duplication):
        testArgs: ArgsStub
        bar: OptionStub
        sub: SubcommandStub

    class Demo1(Duplication):
        foo: int
        bar: str
        baz: str

    com4 = Alconna(
        "comp4", Args["foo", int],
        Option("--bar", Args["bar", str]),
        Subcommand("sub", Option("--sub1", Args["baz", str]))
    )
    res = com4.parse("comp4 123 --bar abc sub --sub1 xyz")
    assert res.matched is True
    duplication = com4.parse("comp4 123 --bar abc sub --sub1 xyz", duplication=Demo)
    assert isinstance(duplication, Demo)
    assert duplication.testArgs.available is True
    assert duplication.testArgs.foo == 123
    assert duplication.bar.available is True
    assert duplication.bar.args.bar == 'abc'
    assert duplication.sub.available is True
    assert duplication.sub.option("sub1").args.first == 'xyz'
    duplication1 = com4.parse("comp4 123 --bar abc sub --sub1 xyz", duplication=Demo1)
    assert isinstance(duplication1, Demo1)
    assert isinstance(duplication1.foo, int)
    assert isinstance(duplication1.bar, str)
    assert isinstance(duplication1.baz, str)

    com4_1 = Alconna(["!", "！"], "yiyu", Args["value;OH", str])
    res = com4_1.parse("!yiyu")
    dup = generate_duplication(res)

def test_output():
    print("")
    output_manager.set_action(lambda x: {'bar': f'{x}!'}, "foo")
    output_manager.set(lambda: "123", "foo")
    assert output_manager.send("foo") == {"bar": "123!"}
    assert output_manager.send("foo", lambda: "321") == {"bar": "321!"}



    com5 = Alconna("comp5", Args["foo", int], Option("--bar", Args["bar", str]))
    output_manager.set_action(lambda x: x, "comp5")
    with output_manager.capture("comp5") as output:
        res = com5.parse("comp5 --help")
        assert res.matched is False
        assert output.get("output")
        print("")
        print(output.get("output"))
    print(output.get("output"))  # capture will clear when exit context

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
