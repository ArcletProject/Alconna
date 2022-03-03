from typing import Optional
from arclet.alconna.builtin.construct import AlconnaFire


class Test:
    """测试从类中构建对象"""

    def __init__(self, sender: Optional[str]):
        """Constructor"""
        self.sender = sender

    def talk(self, name="world"):
        """Test Function"""
        print(f"Hello {name} from {self.sender}")


alc = AlconnaFire(Test("alc"))
alc.parse("Test talk")
alc.parse("Test --help")
alc.parse("Test talk")


def test_function(name="world"):
    """测试从函数中构建对象"""
    print("Hello {}!".format(name))


alc1 = AlconnaFire(test_function)
alc1.parse("test_function --help")
