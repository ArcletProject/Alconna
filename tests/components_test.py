from arclet.alconna import Alconna, Args, Arparma, ArparmaBehavior, Option, Subcommand
from arclet.alconna.builtin import conflict, set_default
from arclet.alconna.base import OptionResult


def test_behavior():
    com = Alconna("comp", Args["bar", int]) + Option("foo", default=321)

    class Test(ArparmaBehavior):
        requires = [set_default(factory=lambda: OptionResult(321), path="option.baz")]

        @classmethod
        def operate(cls, interface: "Arparma"):
            print("\ncom: ")
            print(interface.query("options.foo.value"))
            print(interface.query("options.baz.value"))
            interface.behave_fail()

    com.behaviors.append(Test())
    assert com.parse("comp 123").matched is False

    com1 = Alconna("comp1", Option("--foo", Args["bar", int]), Option("--baz", Args["qux", int]))
    com1.behaviors.append(conflict("foo", "baz"))

    assert com1.parse("comp1 --foo 1").matched
    assert com1.parse("comp1 --baz 2").matched
    assert com1.parse("comp1 --foo 1 --baz 2").matched is False

    com1.behaviors.clear()
    com1.behaviors.append(
        conflict("foo.bar", "baz.qux", source_limiter=lambda x: x == 2, target_limiter=lambda x: x == 1)
    )

    assert com1.parse("comp1 --foo 1").matched
    assert com1.parse("comp1 --baz 2").matched
    assert com1.parse("comp1 --foo 1 --baz 2").matched
    assert com1.parse("comp1 --foo 2 --baz 1").matched is False

    com1.behaviors.clear()
    com1.behaviors.append(conflict("foo", "baz.qux", target_limiter=lambda x: x == 1))

    assert com1.parse("comp1 --foo 1").matched
    assert com1.parse("comp1 --baz 2").matched
    assert com1.parse("comp1 --foo 1 --baz 2").matched
    assert com1.parse("comp1 --foo 1 --baz 1").matched is False

    com1_1 = Alconna("comp1_1", Option("-1", dest="one"), Option("-2", dest="two"), Option("-3", dest="three"))
    com1_1.behaviors.append(conflict("one", "two"))
    com1_1.behaviors.append(conflict("two", "three"))

    assert com1_1.parse("comp1_1 -1 -2").matched is False
    assert com1_1.parse("comp1_1 -2 -3").matched is False
    assert com1_1.parse("comp1_1 -1 -3").matched


# def test_output():
#     print("")
#     output_manager.set_action(lambda x: {"bar": f"{x}!"}, "foo")
#     output_manager.set(lambda: "123", "foo")
#     assert output_manager.send("foo") == {"bar": "123!"}
#     assert output_manager.send("foo", lambda: "321") == {"bar": "321!"}
#
#     com5 = Alconna("comp5", Args["foo", int], Option("--bar", Args["bar", str]))
#     output_manager.set_action(lambda x: x, "comp5")
#     with output_manager.capture("comp5") as output:
#         com5.parse("comp5 --help")
#         assert output.get("output")
#         print("")
#         print(output.get("output"))
#     print(output.get("output"))  # capture will clear when exit context


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
