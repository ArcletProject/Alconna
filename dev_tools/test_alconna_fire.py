from typing import Optional

from arclet.alconna import Args, Option, Subcommand

from arclet.alconna.builtin.construct import AlconnaFire, delegate


class Test:
    """测试从类中构建对象"""

    def __init__(self, sender: Optional[str]):
        """Constructor"""
        self.sender = sender

    def talk(self, name="world"):
        """Test Function"""
        print(f"Hello {name} from {self.sender}")

    class MySub:
        """Sub Class"""

        def __init__(self):
            """Constructor"""
            self.sender = "sub_command"

        def set(self, name="hello"):
            """Test Function"""
            print(f"SUBCOMMAND {name} from {self.sender}")

        class SubConfig:
            command = "subcmd"

    class Config:
        headers = ["!"]
        command = "test_fire"
        get_subcommand = True


alc = AlconnaFire(Test)
alc.parse("!test_fire alc talk")
alc.parse("!test_fire --help")
alc.parse("!test_fire talk ALC subcmd set")


def test_function(name="world"):
    """测试从函数中构建对象"""
    print(f"Hello {name}!")


alc1 = AlconnaFire(test_function)
alc1.parse("test_function --help")


class Test1:
    def __init__(self):
        ...

    def calculator(self, a, b, c, *nums: int, **kwargs: str):
        """calculator"""
        print(a, b, c)
        print(nums, kwargs)
        print(sum(nums))


alc = AlconnaFire(Test1)
alc.parse("Test1 --help")
alc.parse("Test1 calculator 1 2 3 4 5 d=4 f=5")


@delegate
class Test:
    args = Args["foo":int, "bar":str]
    opt1 = Option("--opt", alias=["-o"])
    sub1 = Subcommand("sub1", args=Args["baz":int])


print(Test.parse("Test --opt sub1 1 123 abc"))
