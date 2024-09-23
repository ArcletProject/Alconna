from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Iterable

from ..err import CaptureRejected, ReceivePanic, TransformPanic, ValidateRejected
from ..some import Value
from .fragment import _Fragment, assert_fragments_order

if TYPE_CHECKING:
    from elaina_segment import Buffer

    from .pattern import OptionPattern
    from .receiver import RxPrev, RxPut


class Track:
    __slots__ = ("fragments", "assignes")

    fragments: deque[_Fragment]
    assignes: dict[str, Any]

    def __init__(self, fragments: deque[_Fragment], assignes: dict[str, Any] | None = None):
        self.fragments = fragments
        self.assignes = assignes or {}

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

    @property
    def assignable(self):
        return bool(self.fragments)

    def copy(self):
        return Track(self.fragments.copy(), self.assignes.copy())


def _always_reject_rxfetch():
    raise CaptureRejected


class Net:
    points: dict[str, _Fragment]
    assignes: dict[str, Any]

    _required: dict[str, _Fragment]
    _optional: dict[str, _Fragment]

    def __init__(self, points: dict[str, _Fragment] | None = None):
        self.points = points or {}
        self._required = {}
        self._optional = {}
        self.assignes = {}

        if points is not None:
            for frag in points.values():
                if frag.default is None:
                    self._required[frag.name] = frag
                else:
                    self._optional[frag.name] = frag

    @classmethod
    def from_options(cls, options: Iterable[OptionPattern]):
        return cls({option.net_fragment.name: option.net_fragment for option in options if option.net_fragment is not None})

    @property
    def satisfied(self):
        return not self._required

    @property
    def assignable(self):
        return bool(self.points)

    def forward(self, key: str):
        if key not in self.points:
            return

        def _rxprev():
            if key in self.assignes:
                return Value(self.assignes[key])

        def _rxput(val):
            self.assignes[key] = val

        frag = self.points[key]

        try:
            frag.receiver.receive(_always_reject_rxfetch, _rxprev, _rxput)
        except (CaptureRejected, ValidateRejected, TransformPanic):
            raise
        except Exception as e:
            raise ReceivePanic from e

        if key in self._required:
            del self._required[key]

    def apply_defaults(self):
        for frag in self._optional.values():
            if frag.name not in self.assignes and frag.default is not None:
                self.assignes[frag.name] = frag.default.value

    def copy(self):
        return Net(self.points.copy())


class Preset:
    __slots__ = ("tracks", "net")

    tracks: dict[str, deque[_Fragment]]
    net: Net

    def __init__(self, tracks: dict[str, deque[_Fragment]] | None = None, net: Net | None = None):
        self.tracks = tracks or {}
        self.net = net or Net()

        for fragments in self.tracks.values():
            assert_fragments_order(fragments)

    def new_track(self, name: str) -> Track:
        return Track(self.tracks[name].copy())

    def new_mix(self) -> Mix:
        return Mix(self)


class Mix:
    __slots__ = ("preset", "tracks", "net")

    preset: Preset
    tracks: dict[str, Track]
    net: Net

    def __init__(self, preset: Preset):
        self.preset = preset
        self.tracks = {name: self.preset.new_track(name) for name in self.preset.tracks}
        self.net = self.preset.net.copy()

    def pop_track(self, name: str) -> Track:
        track = self.tracks.pop(name)
        self.tracks[name] = self.preset.new_track(name)
        return track

    def reset_track(self, name: str):
        if name not in self.tracks:
            raise KeyError  # invalid track name

        track = self.tracks[name]
        track.fragments = self.preset.tracks[name].copy()
        track.assignes.clear()

    def get_track(self, name: str) -> Track:
        return self.tracks[name]

    def is_track_satisfied(self, name: str) -> bool:
        return self.tracks[name].satisfied

    def forward_net(self, key: str):
        self.net.forward(key)

    @property
    def satisfied(self) -> bool:
        for track in self.tracks.values():
            if not track.satisfied:
                return False

        return self.net.satisfied

    def complete_track(self, name: str):
        self.tracks[name].complete()

    def complete_all(self):
        for track in self.tracks.values():
            track.complete()

        self.net.apply_defaults()
