from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

import pytest
from elaina_segment import AheadToken, Buffer, SegmentToken
from elaina_segment.err import OutOfData

from arclet.alconna.sistana.analyzer import Analyzer, LoopflowExitReason
from arclet.alconna.sistana.model.fragment import _Fragment
from arclet.alconna.sistana.model.mix import Mix, Track
from arclet.alconna.sistana.model.pattern import SubcommandPattern
from arclet.alconna.sistana.model.snapshot import AnalyzeSnapshot, ProcessingState


def analyze(
    pattern: SubcommandPattern,
    buffer: Buffer,
    complete_on_determined: bool = False,
):
    snapshot = pattern.prefix_entrypoint
    analyzer = Analyzer(complete_on_determined)

    exit_reason = analyzer.loopflow(snapshot, buffer)
    return LoopflowTest(exit_reason), SnapshotTest(snapshot), BufferTest(buffer)


@dataclass
class LoopflowTest:
    exit_reason: LoopflowExitReason

    def expect(self, *expected: LoopflowExitReason):
        assert self.exit_reason in expected

    def expect_completed(self):
        self.expect(LoopflowExitReason.completed)

    def expect_uncompleted(self):
        assert self.exit_reason != LoopflowExitReason.completed

@dataclass
class SnapshotTest:
    snapshot: AnalyzeSnapshot

    @property
    def mix(self):
        return MixTest(self.snapshot.mix)

    def expect_determined(self, expected: bool = True):
        assert self.snapshot.determined == expected

    def expect_state(self, *states: ProcessingState):
        assert self.snapshot.state in (states or (ProcessingState.COMMAND,))

    def expect_endpoint(self, *expected: str):
        assert self.snapshot.endpoint == expected


@dataclass
class BufferTest:
    buffer: Buffer

    def expect_empty(self):
        with pytest.raises(OutOfData):
            self.buffer.next("")
    
    def expect_non_empty(self):
        v = None
        with suppress(OutOfData):
            v = self.buffer.next()
        
        assert v is not None

    def expect_ahead(self):
        token = self.buffer.next("")
        assert isinstance(token, AheadToken)

    def expect_non_ahead(self):
        token = self.buffer.next("")
        assert isinstance(token, SegmentToken)


@dataclass
class MixTest:
    mix: Mix

    def __init__(self, input_: AnalyzeSnapshot | Mix):
        if isinstance(input_, AnalyzeSnapshot):
            self.mix = input_.mix
        else:
            self.mix = input_

    def subcommand(self, path: tuple[str, ...]):
        return TrackTest(self.mix, self.mix.command_tracks[path])

    def subcommand1(self, *path: str):
        return self.subcommand(path)

    def option(self, owner: tuple[str, ...], name: str):
        return TrackTest(self.mix, self.mix.option_tracks[owner, name])

    def option1(self, *path: str):
        *owner, name = path
        return self.option(tuple(owner), name)

    def __getitem__(self, path: tuple[str, ...] | tuple[tuple[str, ...], str]):
        if isinstance(path[0], tuple):
            owner, name = path
            return self.option(owner, name)  # type: ignore

        return self.subcommand(path)  # type: ignore

    def expect_assignes(self, **kwargs):
        for key, value in kwargs.items():
            assert key in self.mix.assignes
            assert value == self.mix.assignes[key]


@dataclass
class TrackTest:
    mix: Mix
    track: Track

    def expect_emitted(self, expected: bool = True):
        assert self.track.emitted == expected
    
    def expect_cursor(self, expected: int):
        assert self.track.cursor == expected

    def expect_satisfied(self, expected: bool = True):
        assert self.track.satisfied == expected

    def expect_assignable(self, expected: bool = False):
        assert self.track.assignable == expected

    def get_fragment(self, name: str):
        for fragment in self.track.fragments:
            if fragment.name == name:
                return fragment

    def __getitem__(self, index: str):
        frag = self.get_fragment(index)
        if frag is None:
            raise ValueError(f"Fragment {index} not found in track {self.track}")
        return FragmentTest(self.mix, self.track, frag)

    @property
    def header(self):
        if self.track.header is None:
            raise ValueError(f"Track {self.track} has no header")

        return FragmentTest(self.mix, self.track, self.track.header)

@dataclass
class FragmentTest:
    mix: Mix
    track: Track
    fragment: _Fragment

    @property
    def assigned(self):
        return self.fragment.name in self.mix.assignes
    
    def expect_assigned(self, expected: bool = True):
        assert self.assigned == expected

    @property
    def value(self):
        return self.mix.assignes[self.fragment.name]
    
    def expect_value(self, expected):
        assert self.value == expected

    def expect_variadic(self, expected: bool = True):
        assert self.fragment.variadic == expected

    def expect_default_exists(self, expected: bool = True):
        assert self.fragment.default is not None == expected

    def expect_value_is_default(self):
        self.expect_default_exists()

        assert self.value == self.fragment.default.value  # type: ignore
