from arclet.alconna import Alconna
from arclet.alconna.component import Arpamar
from arclet.letoderea.entities.decorator import EventDecorator
from arclet.letoderea.utils import ArgumentPackage
from arclet.alconna.types import MessageChain


class AlconnaParser(EventDecorator):
    """
    Alconna的装饰器形式
    """

    def __init__(self, *, alconna: Alconna):
        super().__init__(target_type=MessageChain)
        self.alconna = alconna

    def supply(self, target_argument: ArgumentPackage) -> Arpamar:
        if target_argument.annotation == MessageChain:
            return self.alconna.analyse_message(target_argument.value)
