from arclet.alconna.exceptions import NullTextMessage
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

    @staticmethod
    def converter(command: str):
        return MessageChain.create(command)

    def process_message(self, data: MessageChain) -> 'GraiaCommandAnalyser':
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.original_data = data
        separate = self.separator
        i, __t, exc = 0, False, None
        raw_data = []
        for unit in data:
            # using graia.amnesia.message and graia.amnesia.elements
            # if isinstance(unit, Text):
            #     res = split(unit.text.lstrip(' '), separate)
            #     if not res:
            #         continue
            #     raw_data.append(res)
            #     __t = True
            # elif isinstance(unit, Unknown):
            #     if self.is_raise_exception:
            #         exc = UnexpectedElement(f"{unit.type}({unit})")
            #     continue
            # elif unit.__class__.__name__ not in self.filter_out:
            #     raw_data.append(unit.text)
            if isinstance(unit, Plain):
                res = split(unit.text.lstrip(' '), separate)
                if not res:
                    continue
                raw_data.append(res)
                __t = True
            elif unit.type not in self.filter_out:
                raw_data.append(unit)
            else:
                continue
            i += 1

        if __t is False:
            exp = NullTextMessage(lang_config.analyser_handle_null_message.format(target=data))
            if self.is_raise_exception:
                raise exp
            self.temporary_data["fail"] = exp
        else:
            self.raw_data = raw_data
            self.ndata = i
            self.temp_token = self.generate_token(raw_data)
        return self
