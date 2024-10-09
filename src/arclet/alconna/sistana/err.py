from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ReasonableParseError(Exception): ...


class ParseCancelled(ReasonableParseError): ...


class Rejected(ReasonableParseError): ...


class CaptureRejected(Rejected): ...


class ValidateRejected(Rejected): ...


@dataclass
class UnexpectedType(CaptureRejected):
    expected: type | tuple[type, ...]
    got: type | Any

    def __str__(self):
        return f"Expected {self.expected}, got {self.got}"


@dataclass
class RegexMismatch(CaptureRejected):
    pattern: str | re.Pattern[str]
    raw: str

    def __str__(self):
        return f"Pattern {self.pattern!r} does not match {self.raw!r}"


class ParsePanic(Exception): ...


class TransformPanic(ParsePanic): ...


class ReceivePanic(ParsePanic): ...
