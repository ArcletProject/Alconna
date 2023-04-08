try:
    from lru import LRU
except ImportError:
    from collections import OrderedDict

    class LRU:

        __slots__ = ("max_size", "cache", "__size")

        def __init__(self, max_size: int = -1) -> None:
            self.max_size = max_size
            self.cache = OrderedDict()
            self.__size = 0

        def get(self, key, default=None):
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            return default

        def __getitem__(self, item):
            return self.cache[item]

        def set(self, key, value) -> None:
            if key in self.cache:
                return
            self.cache[key] = value
            self.__size += 1
            if 0 < self.max_size < self.__size:
                _k = self.cache.popitem(last=False)[0]
                self.__size -= 1

        def __setitem__(self, key, value):
            return self.set(key, value)

        def delete(self, key) -> None:
            self.cache.pop(key)

        def has_key(self, key) -> bool:
            return key in self.cache

        def clear(self) -> None:
            self.cache.clear()

        def __len__(self) -> int:
            return len(self.cache)

        __contains__ = has_key

        def __iter__(self):
            return iter(self.cache)

        def __repr__(self) -> str:
            return repr(self.cache)

        def peek_first_item(self):
            return next(iter(self.cache.items()))

        def keys(self):
            return list(self.cache.keys())

        def values(self):
            return list(self.cache.values())

        def items(self):
            return list(self.cache.items())
