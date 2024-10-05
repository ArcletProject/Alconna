from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from elaina_segment import Buffer
from elaina_segment.err import OutOfData

from .err import ParsePanic, Rejected
from .model.pointer import PointerRole
from .model.snapshot import AnalyzeSnapshot

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
    complete_on_determined: bool = True

    def loopflow(self, snapshot: AnalyzeSnapshot, buffer: Buffer[T]) -> LoopflowExitReason:
        while True:
            if self.complete_on_determined and snapshot.endpoint is not None and snapshot.stage_satisfied:
                return LoopflowExitReason.completed

            main_ref = snapshot.main_ref
            current = snapshot._alter_ref or main_ref
            context = snapshot.traverses[main_ref.data]
            mix = snapshot.mix
            pointer_type = current.data[-1][0]

            try:
                token = buffer.next(context.separators)
            except OutOfData:
                if mix.satisfied:
                    mix.complete()
                    snapshot.unset_alter()
                    snapshot.determine()
                    return LoopflowExitReason.completed

                # 这里如果没有 satisfied，如果是 option 的 track，则需要 reset
                # 从 Buffer 吃掉的东西？我才不还。
                if pointer_type is PointerRole.OPTION:
                    mix.reset_track(current)

                return LoopflowExitReason.unsatisfied

            if pointer_type is PointerRole.PREFIX:
                if context.prefixes is not None:
                    if not isinstance(token.val, str):
                        return LoopflowExitReason.header_expect_str

                    if context.prefixes is not None:
                        prefix = context.prefixes.get_closest_prefix(buffer.first())  # type: ignore
                        if prefix == "":
                            return LoopflowExitReason.prefix_mismatch

                        token.apply()
                        buffer.pushleft(token.val[len(prefix) :])

                snapshot.set_alter(main_ref.header())
            elif pointer_type is PointerRole.HEADER:
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

                track = mix.tracks[main_ref.data]
                track.emit_header(mix, token.val)

                snapshot.unset_alter()
            else:
                if isinstance(token.val, str):
                    if pointer_type is PointerRole.SUBCOMMAND:
                        if token.val in context._subcommands_bind:
                            subcommand = context._subcommands_bind[token.val]

                            if snapshot.stage_satisfied or not subcommand.satisfy_previous:
                                token.apply()
                                snapshot.complete()

                                snapshot.enter_subcommand(token.val, subcommand)
                                continue
                            elif not subcommand.soft_keyword:
                                return LoopflowExitReason.unsatisfied_switch_subcommand
                        elif (option_info := snapshot.get_option(token.val)) is not None:
                            owned_subcommand_ref, option_keyword = option_info
                            owned_subcommand = snapshot.traverses[owned_subcommand_ref.data]
                            target_option = owned_subcommand._options_bind[option_keyword]

                            if not target_option.soft_keyword or snapshot.stage_satisfied:
                                if not snapshot.enter_option(token.val, owned_subcommand_ref.option(option_keyword), target_option):
                                    return LoopflowExitReason.option_duplicated_prohibited

                                token.apply()
                                continue

                        # else: 进了 track process.
                    elif pointer_type is PointerRole.OPTION:
                        current_track = mix.tracks[current.data]

                        if token.val in context._subcommands_bind:
                            subcommand = context._subcommands_bind[token.val]

                            if not current_track.satisfied:
                                if not subcommand.soft_keyword:
                                    mix.reset_track(current)
                                    return LoopflowExitReason.switch_unsatisfied_option
                            else:
                                current_track.complete(mix)
                                snapshot.unset_alter()

                                if snapshot.stage_satisfied:
                                    token.apply()
                                    snapshot.complete()

                                    snapshot.enter_subcommand(token.val, subcommand)
                                    continue
                                elif not subcommand.soft_keyword:  # and not snapshot.stage_satisfied
                                    return LoopflowExitReason.unsatisfied_switch_subcommand

                        elif (option_info := snapshot.get_option(token.val)) is not None:
                            owned_subcommand_ref, option_name = option_info
                            owned_subcommand = snapshot.traverses[owned_subcommand_ref.data]
                            target_option = owned_subcommand._options_bind[option_name]

                            if not current_track.satisfied:
                                if not target_option.soft_keyword:
                                    mix.reset_track(current)
                                    return LoopflowExitReason.previous_unsatisfied
                            else:
                                current_track.complete(mix)
                                snapshot.unset_alter()

                                if not target_option.soft_keyword or snapshot.stage_satisfied:
                                    # 这里的逻辑基本上和上面的一致。
                                    if not snapshot.enter_option(token.val, owned_subcommand_ref.option(option_name), target_option):
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
                    #             track = mix.tracks[current.option(opt.keyword).data]

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

                track = mix.tracks[current.data]
                if pointer_type is PointerRole.SUBCOMMAND:
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
                        # else: next loop，因为没有 OutOfData。
                        # 即使有，上面也已经给你处理了。
                elif pointer_type is PointerRole.OPTION:
                    # option fragments 的处理是原子性的，整段成功才会 apply changes，否则会被 reset。
                    opt = snapshot._ref_cache_option[current.data]

                    try:
                        response = track.forward(mix, buffer, opt.separators)
                    except OutOfData:
                        mix.reset_track(current)
                        return LoopflowExitReason.out_of_data_option
                    except (Rejected, ParsePanic):
                        raise
                    except Exception as e:
                        raise ParsePanic from e
                    else:
                        if response is None:
                            # track 上没有 fragments 可供分配了。
                            # 这里没必要 complete：track.complete 只是补全 assignes。
                            snapshot.unset_alter()

                            if opt.allow_duplicate:
                                track.reset()
                            # else: 如果不允许 duplicate，就没必要 pop （幂等操作嘛）
                        # else: 还是 enter next loop
                    # 无论如何似乎都不会到这里来，除非 track process 里有个组件惊世智慧的拿到 snapshot 并改了 traverse.ref。
