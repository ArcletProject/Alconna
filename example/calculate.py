import operator

from nepattern import NUMBER, SwitchPattern

from arclet.alconna import Alconna, Arg

alc = Alconna(
    "calc",
    Arg("a", NUMBER),
    Arg(
        "action",
        SwitchPattern(
            {
                "add": operator.add,
                "sub": operator.sub,
                "mul": operator.mul,
                "div": operator.truediv,
                "mod": operator.mod,
                "+": operator.add,
                "-": operator.sub,
                "*": operator.mul,
                "/": operator.truediv,
                "%": operator.mod,
                ...: operator.add

            }
        )
    ),
    Arg("b", NUMBER),
)

@alc.bind()
def calc(a, action, b):
    print(action(a, b))

alc.parse("calc 123 + 456")
alc.parse("calc 4.56 mul 8")
