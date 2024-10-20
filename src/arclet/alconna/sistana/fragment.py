from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from elaina_segment import Quoted, Segment, UnmatchedQuoted

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
            return self

        t = self.type.value

        from msgspec import ValidationError, convert

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
        
        return self

    def apply_nepattern(self, pat: BasePattern | None = None, capture_mode: bool = False):
        if pat is None:
            if self.type is None:
                return self

            from nepattern import BasePattern

            pat = BasePattern.to(self.type.value)
            assert pat is not None

        def _validate(v: Segment):
            if isinstance(v, (Quoted, UnmatchedQuoted)):
                if isinstance(v.ref, str):
                    v = str(v)
                else:
                    v = v.ref[0]
            return pat.validate(v).success

        self.validator = _validate
        if self.cast:
            def _transform(v: Segment):

                if isinstance(v, (Quoted, UnmatchedQuoted)):
                    if isinstance(v.ref, str):
                        v = str(v)
                    else:
                        v = v.ref[0]

                return pat.validate(v).value()

            self.transformer = _transform
        return self