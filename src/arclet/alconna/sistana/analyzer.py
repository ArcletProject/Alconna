from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from elaina_segment import Buffer
from elaina_segment.err import OutOfData

from .err import ParsePanic, Rejected
from .model.snapshot import AnalyzeSnapshot, ProcessingState

T = TypeVar("T")


class LoopflowExitReason(str, Enum):
    completed = "completed"

    unsatisfied = "continuation@process#unsatisfied"
    out_of_data_subcommand = "continuation@subcommand#out-of-data"
    out_of_data_option = "continuation@subcommand#out-of-data"
    previous_unsatisfied = "continuation@option-switch#previous-unsatisfied"
    unsatisfied_switch_option = "continuation@option-switch#unsatisfied"
    unsatisfied_switch_subcommand = "continuation@subcommand-switch#unsatisfied"

    prefix_expect_str = "panic@prefix-match#expect-str"
    prefix_mismatch = "panic@prefix-match#mismatch"
    header_expect_str = "panic@header-match#expect-str"
    header_mismatch = "panic@header-match#mismatch"
    unexpected_segment = "panic@subcommand-process#unexpected-segment"
    option_duplicated_prohibited = "panic@option-process#duplicated"

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<loopflow(::) => {self.value}>"


@dataclass
class Analyzer(Generic[T]):
    complete_on_determined: bool = False

    def loopflow(self, snapshot: AnalyzeSnapshot, buffer: Buffer[T]) -> LoopflowExitReason:
        mix = snapshot.mix

        while True:
            state = snapshot.state
            context = snapshot.context

            try:
                token = buffer.next(context.separators)
            except OutOfData:
                if mix.satisfied:
                    mix.complete()
                    snapshot.determine()
                    return LoopflowExitReason.completed

                # 这里如果没有 satisfied，如果是 option 的 track，则需要 reset
                # 从 Buffer 吃掉的东西？我才不还。
                if state is ProcessingState.OPTION:
                    mix.option_tracks[snapshot.option].reset()  # type: ignore

                return LoopflowExitReason.unsatisfied

            if state is ProcessingState.PREFIX:
                if context.prefixes is not None:
                    if not isinstance(token.val, str):
                        return LoopflowExitReason.prefix_expect_str

                    if context.prefixes is not None:
                        prefix = context.prefixes.longest_prefix(buffer.first()).key  # type: ignore
                        if prefix is None:
                            return LoopflowExitReason.prefix_mismatch

                        token.apply()
                        buffer.pushleft(token.val[len(prefix) :])

                snapshot.state = ProcessingState.HEADER
            elif state is ProcessingState.HEADER:
                if not isinstance(token.val, str):
                    return LoopflowExitReason.header_expect_str

                token.apply()

                if token.val == context.header:
                    pass  # do nothing
                elif context.compact_header and token.val.startswith(context.header):
                    v = token.val[len(context.header) :]
                    if v:
                        buffer.pushleft(v)

                else:
                    return LoopflowExitReason.header_mismatch

                track = mix.command_tracks[tuple(snapshot.command)]
                track.emit_header(mix, token.val)

                snapshot.state = ProcessingState.COMMAND
            else:
                if isinstance(token.val, str):
                    if (subcommand_info := snapshot.get_subcommand(context, token.val)) is not None:
                        subcommand, tail = subcommand_info
                        enter_forward = False

                        if state is ProcessingState.OPTION:
                            owner, keyword = snapshot.option  # type: ignore
                            current_track = mix.option_tracks[owner, keyword]

                            if not current_track.satisfied:
                                if not subcommand.soft_keyword:
                                    mix.option_tracks[owner, keyword].reset()
                                    return LoopflowExitReason.unsatisfied_switch_option
                                else:
                                    enter_forward = True
                            else:
                                current_track.complete(mix)

                        if not enter_forward and snapshot.stage_satisfied or not subcommand.enter_instantly:
                            token.apply()
                            mix.complete()

                            if tail is not None:
                                buffer.pushleft(tail)

                            snapshot.enter_subcommand(token.val, subcommand)
                            continue
                        elif not subcommand.soft_keyword:
                            return LoopflowExitReason.unsatisfied_switch_subcommand

                    elif (option_info := snapshot.get_option(token.val)) is not None:
                        target_option, target_owner, tail = option_info
                        enter_forward = False

                        if state is ProcessingState.OPTION:
                            owner, keyword = snapshot.option  # type: ignore
                            current_track = mix.option_tracks[owner, keyword]

                            if not current_track.satisfied:
                                if not target_option.soft_keyword:
                                    mix.option_tracks[target_owner, target_option.keyword].reset()
                                    return LoopflowExitReason.previous_unsatisfied
                                else:
                                    enter_forward = True
                            else:
                                current_track.complete(mix)
                                snapshot.state = ProcessingState.COMMAND

                        if not enter_forward and (not target_option.soft_keyword or snapshot.stage_satisfied):
                            if not snapshot.enter_option(token.val, target_owner, target_option.keyword, target_option):
                                return LoopflowExitReason.option_duplicated_prohibited

                            token.apply()

                            if tail is not None:
                                buffer.pushleft(tail)

                            continue

                if state is ProcessingState.COMMAND:
                    track = mix.command_tracks[tuple(snapshot.command)]

                    try:
                        response = track.forward(mix, buffer, context.separators)
                    except OutOfData:
                        # 称不上是 context switch，continuation 不改变 context。
                        return LoopflowExitReason.out_of_data_subcommand
                    except (Rejected, ParsePanic):
                        raise
                    except Exception as e:
                        raise ParsePanic from e
                    else:
                        if response is None:
                            if self.complete_on_determined and mix.satisfied:
                                mix.complete()
                                snapshot.determine()
                                return LoopflowExitReason.completed

                            # track 上没有 fragments 可供分配了，此时又没有再流转到其他 traverse
                            return LoopflowExitReason.unexpected_segment
                else:
                    track = mix.option_tracks[snapshot.option]  # type: ignore
                    opt = snapshot._ref_cache_option[snapshot.option]  # type: ignore

                    try:
                        response = track.forward(mix, buffer, opt.separators)
                    except OutOfData:
                        mix.option_tracks[snapshot.option].reset()  # type: ignore
                        return LoopflowExitReason.out_of_data_option
                    except (Rejected, ParsePanic):
                        raise
                    except Exception as e:
                        raise ParsePanic from e
                    else:
                        if response is None:
                            snapshot.state = ProcessingState.COMMAND
