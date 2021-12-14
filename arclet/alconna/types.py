from typing import TypeVar

AnyIP = r"(\d+)\.(\d+)\.(\d+)\.(\d+)"
AnyDigit = r"(\d+)"
AnyStr = r"(.+)"
AnyUrl = r"(http[s]?://.+)"
Bool = r"(True|False)"

NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")