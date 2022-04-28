from typing import Optional, Dict, Any

from arclet.alconna.manager import command_manager
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.exceptions import NullTextMessage, UnexpectedElement
from arclet.alconna.util import split
from arclet.alconna.lang import lang_config
from arclet.alconna.builtin.analyser import DefaultCommandAnalyser

from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
# from graia.amnesia.message import MessageChain
# from graia.amnesia.element import Text, Unknown


class GraiaCommandAnalyser(DefaultCommandAnalyser[MessageChain]):
    """
    无序的分析器

    """

    def handle_message(self, data: MessageChain) -> Optional[Arpamar]:
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.context_token = command_manager.current_command.set(self.alconna)
        self.original_data = data
        separate = self.separator
        i, __t, exc = 0, False, None
        raw_data: Dict[int, Any] = {}
        for unit in data:
            # using graia.amnesia.message and graia.amnesia.elements
            # if isinstance(unit, Text):
            #     res = split(unit.text.lstrip(' '), separate)
            #     if not res:
            #         continue
            #     raw_data[i] = res
            #     __t = True
            # elif isinstance(unit, Unknown):
            #     if self.is_raise_exception:
            #         exc = UnexpectedElement(f"{unit.type}({unit})")
            #     continue
            # elif unit.__class__.__name__ not in self.filter_out:
            #     raw_data[i] = unit
            if isinstance(unit, Plain):
                res = split(unit.text.lstrip(' '), separate)
                if not res:
                    continue
                raw_data[i] = res
                __t = True
            elif unit.type not in self.filter_out:
                raw_data[i] = unit
            else:
                if self.is_raise_exception:
                    exc = UnexpectedElement(
                        lang_config.analyser_handle_unexpect_type.format(targer=f"{unit.type}({unit})")
                    )
                continue
            i += 1

        if __t is False:
            exp = NullTextMessage(lang_config.analyser_handle_null_message.format(target=data))
            if self.is_raise_exception:
                raise exp
            return self.create_arpamar(fail=True, exception=exp)
        # if exc:
        #     if self.is_raise_exception:
        #         raise exc
        #     return self.create_arpamar(fail=True, exception=exc)
        self.raw_data = raw_data
        self.ndata = i
        self.temp_token = self.generate_token(self.raw_data)
        return
