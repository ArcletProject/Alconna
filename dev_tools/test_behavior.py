from arclet.alconna import Alconna, Args, Option
from arclet.alconna.arpamar import ArpamarBehavior, ArpamarBehaviorInterface
from arclet.alconna.builtin.actions import set_default, exclusion, cool_down
import time


class Test(ArpamarBehavior):
    def operate(self, interface: "ArpamarBehaviorInterface"):
        print(interface.require("options.foo"))
        interface.change_const("matched", False)


alc = Alconna(
    "command",
    options=[
        Option("foo"),
    ],
    main_args=Args["bar":int],
    behaviors=[set_default(321, option="foo"), Test()],
)
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
    behaviors=[cool_down(0.2)]
)
for i in range(4):
    time.sleep(0.1)
    print(alc2.parse("test_cool_down {}".format(i)))
