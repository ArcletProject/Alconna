"""
Alconna 对于 Graia 系列的支持

注意：
    现阶段仍使用 graia.ariadne 的 MessageChain;

    后续将会更新为 graia.amnesia 的 MessageChain
"""
from arclet.alconna import Alconna
from .analyser import GraiaCommandAnalyser
from .dispatcher import AlconnaDispatcher, AlconnaHelpMessage

Alconna.default_analyser = GraiaCommandAnalyser
