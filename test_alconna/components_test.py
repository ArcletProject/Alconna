from arclet.alconna import Alconna, Option, Args, Subcommand, Arpamar, ArpamarBehavior, store_value
from arclet.alconna.builtin.actions import set_default, exclusion, cool_down
from arclet.alconna.components.duplication import Duplication, generate_duplication
from arclet.alconna.components.stub import ArgsStub, OptionStub, SubcommandStub


def test_behavior():
    com = Alconna("comp", Args["bar", int]) + Option("foo")

    @com.behaviors.append
    class Test(ArpamarBehavior):
        requires = [set_default(321, option="foo")]

        @classmethod
        def operate(cls, interface: "Arpamar"):
            print('\ncom: ')
            print(interface.query("options.foo.value"))
            interface.behave_fail()

    assert com.parse("comp 123").matched is False


def test_set_defualt():
    com1 = Alconna("comp1") + \
           Option("foo", action=store_value(123)) + \
           Option("bar", Args["baz", int, 234])
    com1.behaviors.append(set_default(321, option="bar", arg="baz"))
    com1.behaviors.append(set_default(423, option="foo"))
    assert com1.parse("comp1 bar").query("foo.value") == 423
    assert com1.parse("comp1 bar").query("bar.baz") == 234
    assert com1.parse("comp1 foo").query("foo.value") == 123
    assert com1.parse("comp1 foo").query("bar.baz") == 321


def test_exclusion():
    com2 = Alconna(
        "comp2",
        options=[Option("foo"), Option("bar")],
        behaviors=[exclusion(target_path="options.foo", other_path="options.bar")]
    )
    assert com2.parse("comp2 foo").matched is True
    assert com2.parse("comp2 bar").matched is True
    assert com2.parse("comp2 foo bar").matched is False


def test_cooldown():
    import time
    com3 = Alconna("comp3", Args["bar", int], behaviors=[cool_down(0.3)])
    print('')
    for i in range(4):
        time.sleep(0.2)
        print(com3.parse(f"comp3 {i}"))


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
        options=[
            Option("--bar", Args["bar", str]),
            Subcommand("sub", options=[Option("--sub1", Args["baz", str])])
        ]
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
    assert duplication.sub.option("sub1").args.first_arg == 'xyz'
    duplication1 = com4.parse("comp4 123 --bar abc sub --sub1 xyz", duplication=Demo1)
    assert isinstance(duplication1, Demo1)
    assert isinstance(duplication1.foo, int)
    assert isinstance(duplication1.bar, str)
    assert isinstance(duplication1.baz, str)

    com4_1 = Alconna(["!", "！"], "yiyu", Args["value;OH", str])
    dup = generate_duplication(com4_1)
    dup.set_target(com4_1.parse("!yiyu"))


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
