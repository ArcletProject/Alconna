from arclet.alconna import Alconna, Args, Option, Arpamar
from arclet.alconna.components.behavior import ArpamarBehavior
from arclet.alconna.builtin.actions import set_default, exclusion, cool_down
import time

alc = Alconna("command", Args["bar":int]) + Option("foo")


@alc.behaviors.append
class Test(ArpamarBehavior):
    requires = [set_default(321, option="foo")]

    @classmethod
    def operate(cls, interface: "Arpamar"):
        print(interface.query("options.foo.value"))
        interface.matched = False


print(alc.parse(["command", "123"]))

alc1 = Alconna(
    "test_exclusion",
    options=[
        Option("foo"),
        Option("bar"),
    ],
    behaviors=[exclusion(target_path="options.foo", other_path="options.bar")]
)
print(alc1.parse("test_exclusion\nfoo"))

alc2 = Alconna(
    "test_cool_down",
    main_args=Args["bar":int],
    behaviors=[cool_down(0.3)]
)
for i in range(4):
    time.sleep(0.2)
    print(alc2.parse("test_cool_down {}".format(i)))
