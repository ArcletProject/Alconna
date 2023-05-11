from typing_extensions import ParamSpec, Self
from typing import Callable, TypeVar, Any

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


def deco(fn: Callable[P, T]) -> Callable[[Callable[[Any, T], R]], Callable[P, R]]:
    def wrapper(func: Callable[[Any, T], R]) -> Callable[P, R]:
        def inner(*args: P.args, **kwargs: P.kwargs):
            return func(args[0], fn(*args[1:], **kwargs))  # type: ignore

        return inner

    return wrapper


class A:
    def __init__(self, num: int):
        self.num = num


class B:
    def foo(self, num: int):
        ...

    @deco(A)
    def add(self, args: A) -> Self:
        print(args.num)
        return self


b = B()
b.foo(1)
print(b.add(1).add(2).add(3))
