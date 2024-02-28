from __future__ import annotations

from typing import Any, Callable, Literal, TypeVar, overload
from typing_extensions import Concatenate, ParamSpec, Self

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


@overload
def deco(fn: Callable[P, T]) -> Callable[[Callable[[T], R]], Callable[P, R]]: ...


@overload
def deco(
    fn: Callable[P, T], is_method: Literal[True]
) -> Callable[[Callable[[Any, T], R]], Callable[Concatenate[Any, P], R]]: ...


def deco(  # type: ignore
    fn: Callable[P, T], is_method: bool = False
) -> Callable[[Callable[[T], R] | Callable[[Any, T], R]], Callable[P, R] | Callable[Concatenate[Any, P], R]]:
    def wrapper(func: Callable[[T], R] | Callable[[Any, T], R]) -> Callable[P, R] | Callable[Concatenate[Any, P], R]:
        def inner(*args: P.args, **kwargs: P.kwargs):
            if is_method:
                return func(args[0], fn(*args[1:], **kwargs))  # type: ignore
            return func(fn(*args, **kwargs))  # type: ignore

        return inner

    return wrapper


class A:
    def __init__(self, num: int):
        self.num = num


class B:
    def foo(self, num: int):
        ...

    @deco(A, is_method=True)
    def add(self, args: A) -> Self:
        print(args.num)
        return self


b = B()
b.foo(1)
print(b.add(1).add(2).add(3))
