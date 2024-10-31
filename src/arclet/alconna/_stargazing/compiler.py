from __future__ import annotations

from typing import Sequence, Any

from arclet.alconna.base import Subcommand, Option, HeadResult, SPECIAL_OPTIONS
from arclet.alconna.exceptions import InvalidArgs, InvalidParam, ParamsUnmatched, UnexpectedElement, ArgumentMissing, \
    NullMessage
from arclet.alconna.core import Alconna
from arclet.alconna.args import _Args
from arclet.alconna.arparma import Arparma

from arclet.alconna.sistana import Analyzer, LoopflowExitReason
from arclet.alconna.sistana.some import Value
from arclet.alconna.sistana.fragment import Fragment
from arclet.alconna.sistana.model.snapshot import AnalyzeSnapshot
from arclet.alconna.sistana.model.receiver import ConstRx, AccumRx, CountRx
from arclet.alconna.sistana.model.pattern import SubcommandPattern, OptionPattern

from elaina_segment import Buffer

from .flywheel import build_runes


def _alc_args_to_fragments(args: _Args) -> list[Fragment]:
    fragments = []
    for ag in args.data:
        if ag.field.no_default:
            default = None
        else:
            default = Value(ag.field.get_default())

        frag = Fragment(
            name=ag.name,
            variadic=bool(ag.field.multiple),
            default=default,
            separators=ag.separators,
        )
        frag.apply_nepattern(ag.type_)
        fragments.append(frag)

    return fragments


def step(node: Subcommand | Option, upper: SubcommandPattern, _global_bind: tuple[dict, dict]):
    if isinstance(node, Subcommand):
        pat = upper.subcommand(
            node.name,
            *_alc_args_to_fragments(node.args),
            aliases=node.aliases,
            soft_keyword=node.soft_keyword,
            separators=node.separators,
        )
        pat._options_bind.maps.append(_global_bind[0])
        pat._subcommands_bind.maps.append(_global_bind[1])
        for option in node.options:
            step(option, pat, _global_bind)
        return pat
    else:
        header_fragment = None
        if node.action.type == 0 and node.action.value is not ...:
            header_fragment = Fragment(
                name=node.name,
                receiver=ConstRx(node.action.value),
            )
        elif node.action.type == 1:
            header_fragment = Fragment(
                name=node.name,
                receiver=AccumRx(),
            )
        elif node.action.type == 2:
            header_fragment = Fragment(
                name=node.name,
                receiver=CountRx(),
            )
        return upper.option(
            node.name,
            *_alc_args_to_fragments(node.args),
            aliases=node.aliases,
            soft_keyword=node.soft_keyword,
            separators=node.separators,
            allow_duplicate=node.action.type != 0,
            compact_header=node.compact,
            header_fragment=header_fragment,
        )


def into_sistana(cmd: Alconna):
    pat = SubcommandPattern.build(
        cmd.command,
        *_alc_args_to_fragments(cmd.args),
        prefixes=cmd.prefixes,
        compact_header=bool(cmd.config.compact),
        separators=cmd.separators,
    )
    for option in cmd.options:
        if isinstance(option, SPECIAL_OPTIONS):
            pat.subcommand(
                option.name,
                *_alc_args_to_fragments(option.args),
                aliases=option.aliases,
                soft_keyword=False,
                separators=option.separators,
                enter_instantly=True,
            )
        else:
            step(option, pat, (pat._options_bind.maps[0], pat._subcommands_bind.maps[0]))  # type: ignore
    return pat


def _reason_raise_alc_exception(reason: LoopflowExitReason):
    if reason == LoopflowExitReason.completed:
        return

    if reason in {
        # LoopflowExitReason.unsatisfied,
        # LoopflowExitReason.previous_unsatisfied,
        LoopflowExitReason.unsatisfied_switch_option,
        LoopflowExitReason.unsatisfied_switch_subcommand,
    }:
        raise ParamsUnmatched(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.out_of_data_subcommand,
        LoopflowExitReason.out_of_data_option,
    }:
        raise ArgumentMissing(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.prefix_expect_str,
        LoopflowExitReason.header_expect_str,
    }:
        raise InvalidParam(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.prefix_mismatch,
        LoopflowExitReason.header_mismatch,
    }:
        raise InvalidArgs(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowExitReason.unexpected_segment:
        raise UnexpectedElement(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowExitReason.option_duplicated_prohibited:
        raise NullMessage(f"LoopflowDescription: {reason.value}")


def dump_arparma(
    alc: Alconna,
    snapshot: AnalyzeSnapshot,
    message: Sequence[Any],
    matched: bool = True,
    head_matched: bool = True
) -> Arparma:
    args_result = {}
    value_result = {}
    for path, track in snapshot.mix.command_tracks.items():
        path = path[1:]
        if track.header and track.header.name in snapshot.mix.assignes:
            value_result[path] = snapshot.mix.assignes[track.header.name]
        elif track.emitted:
            value_result[path] = ...
        args_result[path] = {frg.name: snapshot.mix.assignes[frg.name] for frg in track.fragments if frg.name in snapshot.mix.assignes}
    for (prefixes, dest), track in snapshot.mix.option_tracks.items():
        path = prefixes + (dest,)
        path = path[1:]
        if track.header and track.header.name in snapshot.mix.assignes:
            value_result[path] = snapshot.mix.assignes[track.header.name]
        elif track.emitted:
            value_result[path] = ...
        args_result[path] = {frg.name: snapshot.mix.assignes[frg.name] for frg in track.fragments if frg.name in snapshot.mix.assignes}
    arp = Arparma(
        _id=alc._hash,
        origin=message,
        matched=matched,
        header_match=HeadResult(head_matched),
        args_result=args_result,
        value_result=value_result,
    )
    arp.buffer = snapshot.command  # type: ignore
    return arp


def _parse(self: Alconna, message: Sequence[Any], _) -> Arparma:
    if hasattr(self, "_sistana_pattern"):
        pattern = self._sistana_pattern  # type: ignore
    else:
        pattern = into_sistana(self)
        self._sistana_pattern = pattern  # type: ignore
    if isinstance(message, str):
        message = [message]

    analyzer = Analyzer()
    buffer = Buffer(build_runes(message), runes=False)
    snapshot = pattern.prefix_entrypoint

    reason = analyzer.loopflow(snapshot, buffer)
    head_matched = reason not in {LoopflowExitReason.prefix_mismatch, LoopflowExitReason.header_mismatch}
    _reason_raise_alc_exception(reason)
    return dump_arparma(self, snapshot, message, True, head_matched)


_OLD_PARSE = Alconna._parse


def patch_alconna(alc: Alconna | None = None):
    if alc is None:
        Alconna._parse = _parse  # type: ignore

        def dispose():
            Alconna._parse = _OLD_PARSE

        return dispose
    else:
        alc._parse = _parse.__get__(alc)  # type: ignore

        def dispose():
            alc._parse = _OLD_PARSE.__get__(alc)

        return dispose


def _sistana_debug(alc: Alconna, message):
    pat = into_sistana(alc)

    print(f"{pat=}, {message=}")
    analyzer = Analyzer()
    snapshot = pat.prefix_entrypoint
    buffer = Buffer(build_runes(message), runes=False)
    res = analyzer.loopflow(snapshot, buffer)
    print(
        res,
        snapshot.mix,
        dump_arparma(
            alc,
            snapshot,
            message,
            res == LoopflowExitReason.completed,
            res in {LoopflowExitReason.prefix_mismatch, LoopflowExitReason.header_mismatch},
        ),
    )


def patch_global(debug: bool = False):
    if debug:
        Alconna._sistana_debug = _sistana_debug  # type: ignore
    return patch_alconna()
