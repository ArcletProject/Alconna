from arclet.alconna import Alconna, Args, Arparma, ArparmaBehavior, Option
from arclet.alconna.builtin import set_default
from arclet.alconna.model import OptionResult
from arclet.alconna.output import output_manager


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


def test_output():
    print("")
    output_manager.set_action(lambda x: {"bar": f"{x}!"}, "foo")
    output_manager.set(lambda: "123", "foo")
    assert output_manager.send("foo") == {"bar": "123!"}
    assert output_manager.send("foo", lambda: "321") == {"bar": "321!"}

    com5 = Alconna("comp5", Args["foo", int], Option("--bar", Args["bar", str]))
    output_manager.set_action(lambda x: x, "comp5")
    with output_manager.capture("comp5") as output:
        com5.parse("comp5 --help")
        assert output.get("output")
        print("")
        print(output.get("output"))
    print(output.get("output"))  # capture will clear when exit context


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
