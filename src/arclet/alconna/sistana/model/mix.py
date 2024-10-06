from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..err import CaptureRejected, ReceivePanic, TransformPanic, ValidateRejected
from ..some import Value
from .fragment import _Fragment, assert_fragments_order

if TYPE_CHECKING:
    from elaina_segment import Buffer


class Track:
    __slots__ = ("fragments", "header", "cursor", "max_length", "emitted")

    header: _Fragment | None
    fragments: tuple[_Fragment, ...]
    cursor: int
    max_length: int
    emitted: bool

    def __init__(self, fragments: tuple[_Fragment, ...], header: _Fragment | None = None):
        self.fragments = fragments
        self.header = header
        self.cursor = 0
        self.max_length = len(self.fragments)
        self.emitted = False

    @property
    def satisfied(self):
        return self.cursor >= self.max_length or self.fragments[0].default is not None or self.fragments[0].variadic

    def complete(self, mix: Mix):
        if self.cursor >= self.max_length:
            return

        for frag in self.fragments[self.cursor :]:
            if frag.name not in mix.assignes and frag.default is not None:
                mix.assignes[frag.name] = frag.default.value

        if self.header is not None and self.header.name not in mix.assignes and self.header.default is not None:
            mix.assignes[self.header.name] = self.header.default.value

        first = self.fragments[-1]
        if first.variadic and first.name not in mix.assignes:
            mix.assignes[first.name] = []

    def fetch(
        self,
        mix: Mix,
        frag: _Fragment,
        buffer: Buffer,
        upper_separators: str,
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

        def rxprev():
            if frag.name in mix.assignes:
                return Value(mix.assignes[frag.name])

        if frag.variadic:

            def rxput(val):
                if frag.name not in mix.assignes:
                    mix.assignes[frag.name] = []

                mix.assignes[frag.name].append(val)
        else:

            def rxput(val):
                mix.assignes[frag.name] = val

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
        mix: Mix,
        buffer: Buffer,
        separators: str,
    ):
        if self.cursor >= self.max_length:
            return

        first = self.fragments[self.cursor]
        self.fetch(mix, first, buffer, separators)

        if not first.variadic:
            self.cursor += 1

        return first

    def emit_header(self, mix: Mix, segment: str):
        self.emitted = True

        if self.header is None:
            return

        header = self.header

        def rxprev():
            if header.name in mix.assignes:
                return Value(mix.assignes[header.name])

        def rxput(val):
            mix.assignes[header.name] = val

        try:
            header.receiver.receive(lambda: segment, rxprev, rxput)
        except (CaptureRejected, ValidateRejected, TransformPanic):
            raise
        except Exception as e:
            raise ReceivePanic from e

    @property
    def assignable(self):
        return self.cursor < self.max_length

    def copy(self):
        return Track(self.fragments, self.header)

    def reset(self):
        self.cursor = 0

    def __bool__(self):
        return bool(self.fragments)


class Preset:
    __slots__ = ("subcommand_track", "option_tracks")

    subcommand_track: Track
    option_tracks: dict[str, Track]

    def __init__(self, subcommand_track: Track, option_tracks: dict[str, Track]):
        self.subcommand_track = subcommand_track
        self.option_tracks = option_tracks

        assert_fragments_order(subcommand_track.fragments)
        for track in self.option_tracks.values():
            assert_fragments_order(track.fragments)


class Mix:
    __slots__ = ("assignes", "command_tracks", "option_tracks")

    assignes: dict[str, Any]

    command_tracks: dict[tuple[str, ...], Track]
    option_tracks: dict[tuple[tuple[str, ...], str], Track]

    def __init__(self):
        self.assignes = {}
        self.command_tracks = {}
        self.option_tracks = {}

    def complete(self):
        for track in self.command_tracks.values():
            track.complete(self)

    @property
    def satisfied(self):
        for track in self.command_tracks.values():
            if not track.satisfied:
                return False

        return True

    def update(self, root: tuple[str, ...], preset: Preset):
        self.command_tracks[root] = preset.subcommand_track.copy()

        for track_id, track in preset.option_tracks.items():
            self.option_tracks[root, track_id] = track.copy()
