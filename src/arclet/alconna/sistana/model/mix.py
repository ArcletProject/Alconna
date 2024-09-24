from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Iterable

from ..err import CaptureRejected, ReceivePanic, TransformPanic, ValidateRejected
from ..some import Value
from .fragment import _Fragment, assert_fragments_order

if TYPE_CHECKING:
    from elaina_segment import Buffer

    from .receiver import RxPrev, RxPut


def _reject_rxfetch():
    raise CaptureRejected


class Track:
    __slots__ = ("fragments", "assignes", "header")

    header: _Fragment | None
    fragments: deque[_Fragment]
    assignes: dict[str, Any]

    def __init__(self, fragments: Iterable[_Fragment], assignes: dict[str, Any] | None = None, header: _Fragment | None = None):
        self.fragments = deque(fragments)
        self.assignes = assignes or {}
        self.header = header

    @property
    def satisfied(self):
        if not self.fragments:
            return True

        first = self.fragments[0]
        return first.default is not None or first.variadic

    def apply_defaults(self):
        for frag in self.fragments:
            if frag.name not in self.assignes and frag.default is not None:
                self.assignes[frag.name] = frag.default.value
        
        if self.header is not None and self.header.name not in self.assignes and self.header.default is not None:
            self.assignes[self.header.name] = self.header.default.value

    def complete(self):
        self.apply_defaults()

        if self.fragments:
            first = self.fragments[-1]
            if first.variadic and first.name not in self.assignes:
                self.assignes[first.name] = []

    def fetch(
        self,
        frag: _Fragment,
        buffer: Buffer,
        upper_separators: str,
        rxprev: RxPrev[Any] | None = None,  # type: ignore
        rxput: RxPut[Any] | None = None,  # type: ignore
    ):
        tail = None
        token = None

        def rxfetch():
            nonlocal tail, token

            if frag.separators is not None:
                if frag.hybrid_separators:
                    separators = frag.separators + upper_separators
                else:
                    separators = frag.separators
            else:
                separators = upper_separators

            val, tail, token = frag.capture.capture(buffer, separators)

            if frag.validator is not None and not frag.validator(val):
                raise ValidateRejected

            if frag.transformer is not None:
                try:
                    val = frag.transformer(val)
                except Exception as e:
                    raise TransformPanic from e

            return val

        if rxprev is None:

            def rxprev():
                if frag.name in self.assignes:
                    return Value(self.assignes[frag.name])

        if rxput is None:
            if frag.variadic:

                def rxput(val):
                    if frag.name not in self.assignes:
                        self.assignes[frag.name] = []

                    self.assignes[frag.name].append(val)
            else:

                def rxput(val):
                    self.assignes[frag.name] = val

        try:
            frag.receiver.receive(rxfetch, rxprev, rxput)
        except (CaptureRejected, ValidateRejected, TransformPanic):
            raise
        except Exception as e:
            raise ReceivePanic from e

        if tail is not None:
            buffer.add_to_ahead(tail.value)

        if token is not None:
            token.apply()

    def forward(
        self,
        buffer: Buffer,
        separators: str,
        rxprev: RxPrev[Any] | None = None,
        rxput: RxPut[Any] | None = None,
    ):
        if not self.fragments:
            return

        first = self.fragments[0]
        self.fetch(first, buffer, separators, rxprev, rxput)

        if not first.variadic:
            self.fragments.popleft()

        return first

    def emit_header(self):
        if self.header is None:
            return

        header = self.header

        def rxprev():
            if header.name in self.assignes:
                return Value(self.assignes[header.name])

        def rxput(val):
            self.assignes[header.name] = val

        try:
            header.receiver.receive(
                _reject_rxfetch,
                rxprev,
                rxput,
            )
        except (CaptureRejected, ValidateRejected, TransformPanic):
            raise
        except Exception as e:
            raise ReceivePanic from e

    @property
    def assignable(self):
        return bool(self.fragments)

    def copy(self):
        return Track(fragments=self.fragments.copy(), assignes=self.assignes.copy(), header=self.header)

    def copy_spec(self):
        return Track(fragments=self.fragments.copy(), header=self.header)


class Preset:
    __slots__ = ("tracks", "net")

    tracks: dict[str, Track]

    def __init__(self, tracks: dict[str, Track] | None = None):
        self.tracks = tracks or {}

        for track in self.tracks.values():
            assert_fragments_order(track.fragments)

    def new_track(self, name: str) -> Track:
        return self.tracks[name].copy_spec()

    def new_mix(self) -> Mix:
        return Mix(self)


class Mix:
    __slots__ = ("preset", "tracks", "net")

    preset: Preset
    tracks: dict[str, Track]

    def __init__(self, preset: Preset):
        self.preset = preset
        self.tracks = {name: self.preset.new_track(name) for name in self.preset.tracks}

    def pop_track(self, name: str, keep_assignes: bool = False) -> Track:
        track = self.tracks.pop(name)
        self.tracks[name] = self.preset.new_track(name)
    
        if keep_assignes:
            self.tracks[name].assignes.update(track.assignes)

        return track

    def reset_track(self, name: str):
        if name not in self.tracks:
            raise KeyError  # invalid track name

        track = self.tracks[name]
        track.fragments = self.preset.tracks[name].fragments.copy()
        track.assignes.clear()

    def get_track(self, name: str) -> Track:
        return self.tracks[name]

    def is_track_satisfied(self, name: str) -> bool:
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
