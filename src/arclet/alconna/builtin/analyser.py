from typing import Union

from arclet.alconna.base import Option, Subcommand
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.types import MultiArg, ArgPattern, AntiArg, UnionArg, ObjectPattern, SequenceArg, \
    MappingArg, DataCollection
from arclet.alconna.visitor import AlconnaNodeVisitor
from arclet.alconna.analysis.analyser import Analyser
from arclet.alconna.manager import command_manager
from arclet.alconna.analysis.arg_handlers import (
    multi_arg_handler, common_arg_handler, anti_arg_handler
)
from arclet.alconna.analysis.parts import analyse_args, analyse_option, analyse_subcommand, analyse_header
from arclet.alconna.exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess
from arclet.alconna.util import levenshtein_norm
from arclet.alconna.lang import lang_config
from arclet.alconna.help import help_send


class DefaultCommandAnalyser(Analyser):
    """
    内建的默认分析器

    """

    filter_out = ["Source", "File", "Quote"]

    def analyse(self, message: Union[str, DataCollection, None] = None) -> Arpamar:
        if command_manager.is_disable(self.alconna):
            return self.create_arpamar(fail=True)

        if self.ndata == 0 and not self.temporary_data.get('fail'):
            if not message:
                raise ValueError(lang_config.analyser_handle_null_message.format(target=message))
            self.process_message(message)
        if self.temporary_data.get('fail'):
            self.reset()
            return self.create_arpamar(fail=True, exception=self.temporary_data.get('exception'))
        if (res := command_manager.get_record(self.temp_token)) and self.temp_token in self.used_tokens:
            self.reset()
            return res[2]
        try:
            self.header = analyse_header(self)
        except ParamsUnmatched as e:
            self.current_index = 0
            self.content_index = 0
            try:
                _res = command_manager.find_shortcut(
                    self.next_data(self.alconna.separator, pop=False)[0], self.alconna
                )
                self.reset()
                if isinstance(_res, Arpamar):
                    return _res
                self.process_message(_res)
                return self.analyse()
            except ValueError:
                return self.create_arpamar(fail=True, exception=e)
        except FuzzyMatchSuccess as Fuzzy:
            help_send(self.alconna.name, lambda: str(Fuzzy)).handle({}, is_raise_exception=self.is_raise_exception)
            return self.create_arpamar(fail=True)

        for _ in self.part_len:
            _text, _str = self.next_data(self.separator, pop=False)
            if not (_param := self.command_params.get(_text, None) if _str else Ellipsis) and _text != "":
                for p in self.command_params:
                    _p = self.command_params[p]
                    if _p.is_compact:
                        for name in getattr(_p, 'aliases', [p]):
                            if _text.startswith(name):
                                _param = _p
                                break
                    else:
                        _may_param = _text.split(_p.separator)[0]
                        if _may_param in getattr(_p, 'aliases', [p]):
                            _param = _p
                            break
                        if self.alconna.is_fuzzy_match and levenshtein_norm(_may_param, p) >= 0.6:
                            help_send(
                                self.alconna.name,
                                lambda: lang_config.common_fuzzy_matched.format(source=_may_param, target=p)
                            ).handle({}, is_raise_exception=self.is_raise_exception)
                            return self.create_arpamar(fail=True)
            try:
                if not _param or _param is Ellipsis:
                    if not self.main_args:
                        self.main_args = analyse_args(self, self.self_args, self.alconna.nargs, self.alconna.action)
                elif isinstance(_param, Option):
                    if _param.name == "--help":
                        _help_param = self.recover_raw_data()
                        _help_param[0] = _help_param[0].replace("--help", "", 1).replace("-h", "", 1).lstrip()

                        def _get_help():
                            visitor = AlconnaNodeVisitor(self.alconna)
                            return visitor.format_node(self.alconna.formatter, visitor.require(_help_param))

                        help_send(self.alconna.name, _get_help).handle({}, is_raise_exception=self.is_raise_exception)
                        return self.create_arpamar(fail=True)

                    if _param.name == "--shortcut":
                        def _shortcut(sct: str, command: str, expiration: int, delete: bool):
                            return self.alconna.shortcut(
                                sct, None if command == "_" else self.converter(command), delete, expiration
                            )
                        _, opt_v = analyse_option(self, _param)
                        try:
                            msg = _shortcut(
                                opt_v['name'], opt_v['command'],
                                opt_v['expiration'], True if opt_v.get('delete') else False
                            )
                            help_send(
                                self.alconna.name, lambda: msg
                            ).handle({}, is_raise_exception=self.is_raise_exception)
                        except Exception as e:
                            help_send(self.alconna.name, lambda: str(e)).handle(
                                {}, is_raise_exception=self.is_raise_exception
                            )
                        return self.create_arpamar(fail=True)

                    opt_n, opt_v = analyse_option(self, _param)
                    if not self.options.get(opt_n, None):
                        self.options[opt_n] = opt_v
                    elif isinstance(self.options[opt_n], dict):
                        self.options[opt_n] = [self.options[opt_n], opt_v]
                    else:
                        self.options[opt_n].append(opt_v)

                elif isinstance(_param, Subcommand):
                    sub_n, sub_v = analyse_subcommand(self, _param)
                    self.subcommands[sub_n] = sub_v
            except FuzzyMatchSuccess as Fuzzy:
                help_send(
                    self.alconna.name, lambda: str(Fuzzy)
                ).handle({}, is_raise_exception=self.is_raise_exception)
                return self.create_arpamar(fail=True)
            except (ParamsUnmatched, ArgumentMissing):
                if self.is_raise_exception:
                    raise
                return self.create_arpamar(fail=True)
            if self.current_index == self.ndata:
                break

        # 防止主参数的默认值被忽略
        if self.default_main_only and not self.main_args:
            self.main_args = analyse_args(
                self, self.self_args,
                self.alconna.nargs, self.alconna.action
            )

        if self.current_index == self.ndata and (not self.need_main_args or (self.need_main_args and self.main_args)):
            return self.create_arpamar()

        data_len = self.rest_count(self.separator)
        if data_len > 0:
            exc = ParamsUnmatched(
                lang_config.analyser_param_unmatched.format(target=self.next_data(self.separator, pop=False)[0])
            )
        else:
            exc = ArgumentMissing(lang_config.analyser_param_missing)
        if self.is_raise_exception:
            raise exc
        return self.create_arpamar(fail=True, exception=exc)


DefaultCommandAnalyser.add_arg_handler(MultiArg, multi_arg_handler)
DefaultCommandAnalyser.add_arg_handler(AntiArg, anti_arg_handler)
DefaultCommandAnalyser.add_arg_handler(UnionArg, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(ArgPattern, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(ObjectPattern, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(SequenceArg, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(MappingArg, common_arg_handler)
