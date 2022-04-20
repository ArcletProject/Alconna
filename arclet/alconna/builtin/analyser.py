from typing import Union, Optional
import traceback

from arclet.alconna.component import Option, Subcommand
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.types import (
    DataCollection, MultiArg, ArgPattern, AntiArg, UnionArg, ObjectPattern, SequenceArg, MappingArg
)
from arclet.alconna.visitor import AlconnaNodeVisitor
from arclet.alconna.analysis.analyser import Analyser
from arclet.alconna.manager import command_manager
from arclet.alconna.analysis.arg_handlers import (
    multi_arg_handler, common_arg_handler, anti_arg_handler
)
from arclet.alconna.analysis.parts import analyse_args, analyse_option, analyse_subcommand, analyse_header
from arclet.alconna.exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess
from arclet.alconna.util import levenshtein_norm
from arclet.alconna.lang_config import lang_config

from .actions import help_send


class DefaultCommandAnalyser(Analyser):
    """
    内建的默认分析器

    """

    filter_out = ["Source", "File", "Quote"]

    def add_param(self, opt: Union[Option, Subcommand]):
        if isinstance(opt, Subcommand):
            for sub_opts in opt.options:
                opt.sub_params.setdefault(sub_opts.name, sub_opts)
        self.command_params[opt.name] = opt

    def analyse(self, message: Union[str, DataCollection, None] = None) -> Arpamar:
        if command_manager.is_disable(self.alconna):
            return self.create_arpamar(fail=True)
        if self.ndata == 0:
            if not message:
                raise ValueError(lang_config.analyser_handle_null_message.format(target=message))
            if r := self.handle_message(message):
                return r
        try:
            self.header = analyse_header(self)
        except ParamsUnmatched as e:
            self.current_index = 0
            self.content_index = 0
            try:
                _, cmd, reserve = command_manager.find_shortcut(
                    self.alconna, self.next_data(self.alconna.separator, pop=False)[0]
                )
                if reserve:
                    data = self.recover_raw_data()
                    data[0] = cmd
                    self.reset()
                    return self.analyse(data)  # type: ignore
                self.reset()
                return self.analyse(cmd)
            except ValueError:
                return self.create_arpamar(fail=True, exception=e)
        except FuzzyMatchSuccess as Fuzzy:
            help_send(
                self.alconna.name, lambda: str(Fuzzy)
            ).handle({}, is_raise_exception=self.is_raise_exception)
            return self.create_arpamar(fail=True)

        for _ in self.part_len:
            _text, _str = self.next_data(self.separator, pop=False)
            if not (_param := self.command_params.get(_text, None) if _str else Ellipsis) and _text != "":
                for p in self.command_params:
                    _may_param = _text.split(self.command_params[p].separator)[0]
                    if _may_param in getattr(self.command_params[p], 'aliases', [p]):
                        _param = self.command_params[p]
                        break
                    if self.alconna.is_fuzzy_match and levenshtein_norm(_may_param, p) >= 0.7:
                        help_send(
                            self.alconna.name,
                            lambda: lang_config.common_fuzzy_matched.format(source=_may_param, target=p)
                        ).handle({}, is_raise_exception=self.is_raise_exception)
                        return self.create_arpamar(fail=True)
            try:
                if not _param or _param is Ellipsis:
                    if not self.main_args:
                        self.main_args = analyse_args(
                            self, self.self_args, self.alconna.nargs, self.alconna.action
                        )
                elif isinstance(_param, Option):
                    if _param.name == "--help":
                        _help_param = self.recover_raw_data()
                        _help_param[0] = _help_param[0].replace("--help", "", 1).replace("-h", "", 1).lstrip()

                        def _get_help():
                            visitor = AlconnaNodeVisitor(self.alconna)
                            return visitor.format_node(
                                self.alconna.formatter,
                                visitor.require(_help_param)
                            )

                        help_send(
                            self.alconna.name, _get_help
                        ).handle({}, is_raise_exception=self.is_raise_exception)
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

    def create_arpamar(self, exception: Optional[BaseException] = None, fail: bool = False):
        result = Arpamar()
        result.head_matched = self.head_matched
        if fail:
            tb = traceback.format_exc(limit=1)
            result.error_info = repr(exception) or repr(tb)
            result.error_data = self.recover_raw_data()
            result.matched = False
        else:
            result.matched = True
            result.encapsulate_result(self.header, self.main_args, self.options, self.subcommands)
        self.reset()
        return result


DefaultCommandAnalyser.add_arg_handler(MultiArg, multi_arg_handler)
DefaultCommandAnalyser.add_arg_handler(AntiArg, anti_arg_handler)
DefaultCommandAnalyser.add_arg_handler(UnionArg, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(ArgPattern, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(ObjectPattern, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(SequenceArg, common_arg_handler)
DefaultCommandAnalyser.add_arg_handler(MappingArg, common_arg_handler)
