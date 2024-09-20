from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union

from elaina_segment import Quoted, UnmatchedQuoted
from typing_extensions import TypeAlias

from ..utils.misc import Some, Value

from ..buffer import AheadToken, Buffer, SegmentToken
from ..err import RegexMismatch, UnexpectedType

T = TypeVar("T")

CaptureResult: TypeAlias = "tuple[T, Some[Any], Union[SegmentToken[T], AheadToken[T]]]"


class Capture(Generic[T]):
    def capture(self, buffer: Buffer[Any], separators: str) -> CaptureResult[T]: ...


class SimpleCapture(Capture[Any]):
    def capture(self, buffer: Buffer[Any], separators: str) -> CaptureResult[Any]:
        token = buffer.next(separators)
        return token.val, None, token


@dataclass
class ObjectCapture(Capture[T]):
    type: type[T] | tuple[type[T], ...]

    def capture(self, buffer: Buffer[Any], separators: str) -> CaptureResult[T]:
        token = buffer.next(separators)
        if not isinstance(token.val, self.type):
            raise UnexpectedType(self.type, type(token.val))

        return token.val, None, token


Plain: TypeAlias = "Union[str, Quoted[str], UnmatchedQuoted[str]]"


@dataclass
class PlainCapture(Capture[Plain]):
    def capture(self, buffer: Buffer[Any], separators: str) -> CaptureResult[Plain]:
        token = buffer.next(separators)

        if isinstance(token.val, str):
            return token.val, None, token
        elif isinstance(token.val, (Quoted, UnmatchedQuoted)):
            if not isinstance(token.val.ref, str):
                raise UnexpectedType(str, type(token.val.ref))

            return token.val, None, token
        else:
            raise UnexpectedType(str, type(token.val))


@dataclass
class RegexCapture(Capture[re.Match[str]]):
    pattern: str | re.Pattern[str]
    match_quote: bool = False

    def capture(self, buffer: Buffer[Any], separators: str) -> CaptureResult[re.Match[str]]:
        token = buffer.next(separators)

        if isinstance(token.val, str):
            val = token.val
        elif isinstance(token.val, (Quoted, UnmatchedQuoted)) and isinstance(token.val.ref, str) and self.match_quote:
            val = str(token.val)
        else:
            raise UnexpectedType(str, type(token.val))

        match = re.match(self.pattern, val)
        if not match:
            raise RegexMismatch(self.pattern, val)

        last = match.string[match.end() :]
        if last:
            return match, Value(last), token

        return match, None, token
