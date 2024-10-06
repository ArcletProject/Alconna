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
    switch_unsatisfied_option = "continuation@option-switch#unsatisfied"
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
            if self.complete_on_determined and snapshot.endpoint is not None and snapshot.stage_satisfied:
                return LoopflowExitReason.completed

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
                        return LoopflowExitReason.header_expect_str

                    if context.prefixes is not None:
                        prefix = context.prefixes.get_closest_prefix(buffer.first())  # type: ignore
                        if prefix == "":
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
                    if state is ProcessingState.COMMAND:
                        if token.val in context._subcommands_bind:
                            subcommand = context._subcommands_bind[token.val]

                            if snapshot.stage_satisfied or not subcommand.satisfy_previous:
                                token.apply()
                                mix.complete()

                                snapshot.enter_subcommand(token.val, subcommand)
                                continue
                            elif not subcommand.soft_keyword:
                                return LoopflowExitReason.unsatisfied_switch_subcommand
                        elif (option_info := snapshot.get_option(token.val)) is not None:
                            target_option, target_owner = option_info

                            # = !(!stage_satisfied and soft_keyword)
                            # 我们希望当 !stage_satisfied 时，如果是 soft_keyword，则不进入 option enter；只有这种情况才需要进入 track process。
                            if not target_option.soft_keyword or snapshot.stage_satisfied:
                                if not snapshot.enter_option(token.val, target_owner, target_option.keyword, target_option):
                                    return LoopflowExitReason.option_duplicated_prohibited
                                token.apply()
                                continue

                        # else: 进了 track process.
                    elif state is ProcessingState.OPTION:
                        owner, keyword = snapshot.option  # type: ignore
                        current_track = mix.option_tracks[snapshot.option]  # type: ignore

                        if token.val in context._subcommands_bind:
                            subcommand = context._subcommands_bind[token.val]

                            if not current_track.satisfied:
                                if not subcommand.soft_keyword:
                                    mix.option_tracks[owner, keyword].reset()
                                    return LoopflowExitReason.switch_unsatisfied_option
                            else:
                                current_track.complete(mix)

                                if snapshot.stage_satisfied or not subcommand.satisfy_previous:
                                    token.apply()
                                    mix.complete()

                                    snapshot.enter_subcommand(token.val, subcommand)
                                    continue
                                elif not subcommand.soft_keyword:  # and not snapshot.stage_satisfied
                                    return LoopflowExitReason.unsatisfied_switch_subcommand

                        elif (option_info := snapshot.get_option(token.val)) is not None:
                            target_option, target_owner = option_info

                            if not current_track.satisfied:
                                if not target_option.soft_keyword:
                                    mix.option_tracks[target_owner, target_option.keyword].reset()
                                    return LoopflowExitReason.previous_unsatisfied
                            else:
                                current_track.complete(mix)
                                snapshot.state = ProcessingState.COMMAND

                                if not target_option.soft_keyword or snapshot.stage_satisfied:
                                    # 这里的逻辑基本上和上面的一致。
                                    if not snapshot.enter_option(token.val, target_owner, target_option.keyword, target_option):
                                        return LoopflowExitReason.option_duplicated_prohibited

                                    token.apply()
                                    continue
                        # else: 进了 track process.

                    # if context.separator_optbind is not None:
                    #     # TODO: separator_optbind in snapshot-level

                    #     opt_matched = False

                    #     for opt_keyword, separators in context.separator_optbind.items():
                    #         opt = context._options_bind[opt_keyword]

                    #         keyword_part, *tail = token.val.split(separators, 1)
                    #         if keyword_part == opt_keyword or keyword_part in opt.aliases:
                    #             opt_matched = True
                    #             token.apply()
                    #             buffer.add_to_ahead(keyword_part)
                    #             if tail:
                    #                 buffer.pushleft(tail[0])

                    #             break

                    #     if opt_matched:
                    #         continue

                    # if context._compact_keywords is not None:
                    #     # TODO: compact in snapshot-level

                    #     prefix = context._compact_keywords.get_closest_prefix(token.val)
                    #     if prefix:
                    #         redirect = False

                    #         if prefix in context._subcommands_bind:
                    #             # 老样子，需要 satisfied 才能进 subcommand，不然就进 track forward 流程。
                    #             redirect = snapshot.stage_satisfied or not context._subcommands_bind[prefix].satisfy_previous
                    #         elif pointer_type is PointerRole.SUBCOMMAND and prefix in context._options_bind:
                    #             # NOTE: 这里其实有个有趣的点需要提及：pattern 中的 subcommands, options 和这里的 compacts 都是多对一的关系，
                    #             # 所以如果要取 track 之类的，就需要先绕个路，因为数据结构上的主索引总是采用的 node 上的单个 keyword。
                    #             opt = context._options_bind[prefix]
                    #             track = mix.tracks[current.option(opt.keyword)]

                    #             redirect = track.assignable or opt.allow_duplicate
                    #             # 这也排除了没有 fragments 设定的情况，因为这里 token.val 是形如 "-xxx11112222"，已经传了一个 fragment 进去。
                    #             # 但这里有个有趣的例子，比如说我们有 `-v -vv`，这里 v 是一个 duplicate，而 duplicate 仍然可以重入并继续分配，而其 assignable 则成为无关变量。
                    #             # 还有一个有趣的例子：如果一个 duplicate 的 option，他具备有几个 default=Value(...) 的 fragment，则多次触发会怎么样？

                    #         # else: 你是不是手动构造了 TrieHard？
                    #         # 由于默认 redirect 是 False，所以这里不会准许跳转。

                    #         if redirect:
                    #             token.apply()
                    #             prefix_len = len(prefix)
                    #             buffer.add_to_ahead(token.val[:prefix_len])
                    #             buffer.pushleft(token.val[prefix_len:])
                    #             continue
                    #         # else: 进了 track process.

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
