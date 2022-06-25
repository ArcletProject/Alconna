from typing import Union, Any

from arclet.alconna.base import Subcommand, Sentence
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.typing import DataCollection
from arclet.alconna.manager import command_manager
from arclet.alconna.analysis.analyser import Analyser
from arclet.alconna.analysis.special import handle_help, handle_shortcut
from arclet.alconna.analysis.parts import analyse_args, analyse_option, analyse_subcommand, analyse_header, \
    analyse_unmatch_params
from arclet.alconna.exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess
from arclet.alconna.config import config
from arclet.alconna.components.output import output_manager


class DefaultCommandAnalyser(Analyser):
    """
    内建的默认分析器
    """

    filter_out = ["Source", "File", "Quote"]

    def analyse(self, message: Union[DataCollection[Union[str, Any]], None] = None) -> Arpamar:
        if command_manager.is_disable(self.alconna):
            return self.export(fail=True)

        if self.ndata == 0 and not self.temporary_data.get('fail'):
            if not message:
                raise ValueError(config.lang.analyser_handle_null_message.format(target=message))
            self.process(message)
        if self.temporary_data.get('fail'):
            return self.export(fail=True, exception=self.temporary_data.get('exception'))
        if (res := command_manager.get_record(self.temp_token)) and self.temp_token in self.used_tokens:
            self.reset()
            return res
        try:
            self.header = analyse_header(self)
            self.head_pos = self.current_index, self.content_index
        except ParamsUnmatched as e:
            self.current_index = 0
            self.content_index = 0
            try:
                _res = command_manager.find_shortcut(self.popitem(move=False)[0], self.alconna)
                self.reset()
                if isinstance(_res, Arpamar):
                    return _res
                return self.process(_res).analyse()
            except ValueError:
                return self.export(fail=True, exception=e)
        except FuzzyMatchSuccess as Fuzzy:
            output_manager.get(self.alconna.name, lambda: str(Fuzzy)).handle(is_raise_exception=self.is_raise_exception)
            return self.export(fail=True)

        for _ in self.part_len:
            try:
                _text, _str = self.popitem(move=False)
                _param = _param if (_param := (self.command_params.get(_text) if _str and _text else Ellipsis)) else (
                    None if self.default_separate else analyse_unmatch_params(
                        self.command_params.values(), _text, self.alconna.is_fuzzy_match
                    )
                )
                if (not _param or _param is Ellipsis) and not self.main_args:
                    self.main_args = analyse_args(self, self.self_args, self.alconna.nargs)
                elif isinstance(_param, list):
                    for opt in _param:
                        if opt.name == "--help":
                            return handle_help(self)
                        if opt.name == "--shortcut":
                            return handle_shortcut(self)
                        _current_index, _content_index = self.current_index, self.content_index
                        try:
                            opt_n, opt_v = analyse_option(self, opt)
                            self.options[opt_n] = opt_v
                            break
                        except Exception as e:
                            exc = e
                            self.current_index, self.content_index = _current_index, _content_index
                            continue
                    else:
                        raise exc  # noqa
                elif isinstance(_param, Subcommand):
                    self.subcommands.setdefault(*analyse_subcommand(self, _param))
                elif isinstance(_param, Sentence):
                    self.sentences.append(self.popitem()[0])
            except FuzzyMatchSuccess as e:
                output_manager.get(self.alconna.name, lambda: str(e)).handle(is_raise_exception=self.is_raise_exception)
                return self.export(fail=True)
            except (ParamsUnmatched, ArgumentMissing):
                if self.release()[-1] in ("--help", "-h"):
                    return handle_help(self)
                if self.is_raise_exception:
                    raise
                return self.export(fail=True)
            if self.current_index == self.ndata:
                break

        # 防止主参数的默认值被忽略
        if self.default_main_only and not self.main_args:
            self.main_args = analyse_args(self, self.self_args, self.alconna.nargs)

        if self.current_index == self.ndata and (not self.need_main_args or self.main_args):
            return self.export()

        data_len = len(self.release())
        if data_len > 0:
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if self.is_raise_exception:
            raise exc
        return self.export(fail=True, exception=exc)
