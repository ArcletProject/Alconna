from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from elaina_segment import Segment, Quoted, UnmatchedQuoted

from .model.capture import RegexCapture
from .model.fragment import _Fragment
from .utils.misc import Some


@dataclass
class Fragment(_Fragment):
    type: Some[Any] = None
    cast: bool = True

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

        self.validator = _validate
    
        if self.cast:
            def _transform(v: Segment):
                return convert(str(v), t)

            self.transformer = _transform

    def apply_nepattern(self, capture_mode: bool = False):
        if self.type is None:
            return

        from nepattern import type_parser

        pat = type_parser(self.type.value)

        if capture_mode:
            self.capture = RegexCapture(pat.alias)
        else:
            def _validate(v: Segment):
                if isinstance(v, (Quoted, UnmatchedQuoted)):
                    if isinstance(v.ref, str):
                        v = str(v)
                    else:
                        v = v.ref

                return pat.validate(v).success

            self.validator = _validate

        if self.cast:
            def _transform(v: Segment):
                return pat.transform(str(v)).value()

            self.transformer = _transform
