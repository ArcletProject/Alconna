from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..err import ReceivePanic, TransformPanic, ValidateRejected
from ..utils.misc import Value
from .fragment import _Fragment, assert_fragments_order

if TYPE_CHECKING:
    from ..buffer import Buffer
    from .snapshot import AnalyzeSnapshot


@dataclass
class Track:
    fragments: deque[_Fragment]
    assignes: dict[str, Any] = field(default_factory=dict)

    @property
    def satisfied(self):
        if not self.fragments:
            return True

        first = self.fragments[0]
        if first.default is not None or first.variadic:
            return True

        return False

    def apply_defaults(self):
        for frag in self.fragments:
            if frag.default is not None and frag.name not in self.assignes:
                self.assignes[frag.name] = frag.default

    def complete(self):
        self.apply_defaults()

        if self.fragments:
            first = self.fragments[-1]
            if first.variadic and first.name not in self.assignes:
                self.assignes[first.name] = []

    def _assign_getter(self, name: str):
        def getter():
            if name in self.assignes:
                return Value(self.assignes[name])

        return getter

    def _assign_setter(self, name: str, is_variadic: bool = False):
        def setter(val):
            if is_variadic:
                if name not in self.assignes:
                    target = self.assignes[name] = []
                else:
                    target = self.assignes[name]

                target.append(val)
            else:
                self.assignes[name] = val

        return setter

    def fetch(self, snapshot: AnalyzeSnapshot, frag: _Fragment, buffer: Buffer, separators: str):
        val, tail, token = frag.capture.capture(buffer, separators)

        if frag.validator is not None and not frag.validator(val):
            raise ValidateRejected

        if frag.transformer is not None:
            try:
                val = frag.transformer(val)
            except Exception as e:
                raise TransformPanic from e

        if frag.receiver is not None:
            try:
                frag.receiver.receive(self._assign_getter(frag.name), self._assign_setter(frag.name, frag.variadic), val)
            except Exception as e:
                raise ReceivePanic from e

        if tail is not None:
            buffer.ahead.append(tail.value)

        token.apply()

    def forward(self, snapshot: AnalyzeSnapshot, buffer: Buffer, separators: str):
        if not self.fragments:
            return

        first = self.fragments[0]
        self.fetch(snapshot, first, buffer, separators)

        if not first.variadic:
            self.fragments.popleft()

        return first

    @property
    def assignable(self):
        return bool(self.fragments)

    def copy(self):
        return Track(self.fragments.copy(), self.assignes.copy())


@dataclass
class Preset:
    tracks: dict[str, deque[_Fragment]] = field(default_factory=dict)

    def __post_init__(self):
        for fragments in self.tracks.values():
            assert_fragments_order(fragments)

    def new_track(self, name: str) -> Track:
        return Track(self.tracks[name].copy())

    def new_mix(self) -> Mix:
        return Mix(self)


@dataclass
class Mix:
    preset: Preset
    tracks: dict[str, Track] = field(init=False, default_factory=dict)

    def __post_init__(self):
        for name in self.preset.tracks:
            self.init_track(name)

    def init_track(self, name: str):
        self.tracks[name] = self.preset.new_track(name)

    def pop_track(self, name: str) -> Track:
        track = self.tracks.pop(name)
        self.init_track(name)
        return track

    def reset(self, name: str):
        if name not in self.tracks:
            raise KeyError  # invalid track name

        track = self.tracks[name]
        track.fragments = self.preset.tracks[name].copy()
        track.assignes.clear()

    def get(self, name: str) -> Track:
        return self.tracks[name]

    def is_satisfied(self, name: str) -> bool:
        return self.tracks[name].satisfied

    @property
    def satisfied(self) -> bool:
        for track in self.tracks.values():
            if not track.satisfied:
                return False

        return True

    def complete_track(self, name: str):
        self.tracks[name].complete()

    def complete_all(self):
        for track in self.tracks.values():
            track.complete()

    # @property
    # def result(self):
    #     return {name: track.assignes for name, track in self.tracks.items()}
