from __future__ import annotations

from dataclasses import dataclass
from elaina_segment import Segment, Quoted, UnmatchedQuoted
from .model.fragment import _Fragment


@dataclass
class Fragment(_Fragment):
    def apply_msgspec(self):
        if self.type is None:
            return

        t = self.type.value

        from msgspec import convert, ValidationError

        def _validate(v: Segment):
            if not isinstance(v, (str, Quoted, UnmatchedQuoted)):
                return False

            v = str(v)

            try:
                convert(v, t)
            except ValidationError:
                return False

            return True

        def _transform(v: Segment):
            return convert(str(v), t)

        self.validator = _validate
        self.transformer = _transform

    def apply_nepattern(self):
        if self.type is None:
            return

        from nepattern import type_parser

        pat = type_parser(self.type.value)

        def _validate(v: Segment):
            if isinstance(v, (Quoted, UnmatchedQuoted)):
                if isinstance(v.ref, str):
                    v = str(v)
                else:
                    v = v.ref

            return pat.validate(v).success

        def _transform(v: Segment):
            return pat.transform(str(v)).value()

        self.validator = _validate
        self.transformer = _transform
