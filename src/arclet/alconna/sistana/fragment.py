from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from dataclasses import dataclass
from elaina_segment import Segment, Quoted, UnmatchedQuoted

from arclet.alconna._dcls import safe_dcls_kw

from .model.capture import RegexCapture
from .model.fragment import _Fragment
from .some import Some

if TYPE_CHECKING:
    from nepattern import BasePattern

@dataclass(**safe_dcls_kw(slots=True))
class Fragment(_Fragment):
    type: Some[Any] = None
    cast: bool = True
    prefer_checker: Literal["msgspec", "nepattern"] = "nepattern"

    def __post_init__(self):
        if self.type is not None:
            if self.prefer_checker == "msgspec":
                self.apply_msgspec()
            elif self.prefer_checker == "nepattern":
                self.apply_nepattern()
            else:
                raise ValueError("Invalid prefer_checker value.")

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

    def apply_nepattern(self, pat: BasePattern | None = None, capture_mode: bool = False):
        if pat is None:
            if self.type is None:
                return

            from nepattern import type_parser

            pat = type_parser(self.type.value)
            assert pat is not None

        from nepattern import MatchMode

        if capture_mode:
            if pat.mode in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
                self.capture = RegexCapture(pat.regex_pattern)
            else:
                self.capture = RegexCapture(pat.alias)  # type: ignore
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
                return pat.validate(str(v)).value()

            self.transformer = _transform
