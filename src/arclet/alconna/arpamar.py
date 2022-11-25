from typing import Union, Dict, List, Any, Optional, TYPE_CHECKING, Type, TypeVar, Tuple, overload, Generic, Mapping, \
    Callable
from types import MappingProxyType
from contextlib import suppress
from nepattern import Empty
from .typing import TDataCollection
from weakref import finalize
from .config import config
from .base import SubcommandResult, OptionResult
from .exceptions import BehaveCancelled, OutBoundsBehave
from .components.behavior import T_ABehavior, requirement_handler
from .components.duplication import Duplication, generate_duplication

if TYPE_CHECKING:
    from .core import Alconna

T = TypeVar('T')
T_Duplication = TypeVar('T_Duplication', bound=Duplication)


class Arpamar(Generic[TDataCollection]):
    """
    亚帕玛尔(Arpamar), Alconna的珍藏宝书
    """

    def _clr(self):
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __init__(self, alc: "Alconna"):
        self.source: "Alconna" = alc
        self.origin: TDataCollection = ''
        self.matched: bool = False
        self.head_matched: bool = False
        self.error_data: List[Union[str, Any]] = []
        self.error_info: Optional[Union[str, BaseException]] = None
        self.other_args: Dict[str, Any] = {}
        self.main_args: Dict[str, Any] = {}

        self._header: Optional[Union[Dict[str, Any], bool]] = None
        self._options: Dict[str, OptionResult] = {}
        self._subcommands: Dict[str, SubcommandResult] = {}
        self._record = set()

        finalize(self, self._clr)

    @staticmethod
    def _filter_opt(opt: OptionResult):
        if args := opt['args']:
            args = args.copy()
            args.pop('__varargs__', None)
            args.pop('__kwargs__', None)
            args.pop('__kwonly__', None)
            return args
        return opt['value']

    @staticmethod
    def _filter_sub(sub: SubcommandResult):
        val = {k: Arpamar._filter_opt(v) for k, v in sub['options'].items()}
        val.update(sub['args'])
        if val:
            val = val.copy()
            val.pop('__varargs__', None)
            val.pop('__kwargs__', None)
            val.pop('__kwonly__', None)
            return val
        return sub['value']

    @property
    def header(self):
        """返回可能解析到的命令头中的信息"""
        return self._header or self.head_matched

    @property
    def non_component(self) -> bool:
        return not self._subcommands and not self._options

    @property
    def components(self) -> Dict[str, Union[OptionResult, SubcommandResult]]:
        return {**self._options, **self._subcommands}

    @property
    def options(self) -> Dict[str, Union[Dict[str, Any], Any]]:
        return {k: self._filter_opt(v) for k, v in self._options.items()}

    @property
    def subcommands(self) -> Dict[str, Union[Dict[str, Any], Any]]:
        return {k: self._filter_sub(v) for k, v in self._subcommands.items()}

    @property
    def all_matched_args(self) -> Dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    def get_duplication(self, dup: Optional[Type[T_Duplication]] = None) -> T_Duplication:
        if dup:
            return dup(self.source).set_target(self)
        return generate_duplication(self.source).set_target(self)  # type: ignore

    def encapsulate_result(
            self,
            header: Union[Dict[str, Any], bool, None],
            main_args: Dict[str, Any],
            options: Dict[str, OptionResult],
            subcommands: Dict[str, SubcommandResult]
    ) -> None:
        """处理 Arpamar 中的数据"""
        self.main_args = main_args.copy()
        self._header = header.copy() if isinstance(header, dict) else header
        self._options = options.copy()
        self._subcommands = subcommands.copy()
        for v in options.values():
            self.other_args = {**self.other_args, **v['args']}
        for k in subcommands:
            v = subcommands[k]
            self.other_args = {**self.other_args, **v['args']}
            if sub_opts := v['options']:
                for vv in sub_opts.values():
                    self.other_args = {**self.other_args, **vv['args']}

    def behave_cancel(self):
        raise BehaveCancelled

    def behave_fail(self):
        raise OutBoundsBehave

    def execute(self, behaviors: Optional[List[T_ABehavior]] = None):
        self.source.behaviors[0].operate(self)
        if behaviors := (self.source.behaviors[1:] + (behaviors or [])):
            exc_behaviors = []
            for behavior in behaviors:
                exc_behaviors.extend(requirement_handler(behavior))
            for b in exc_behaviors:
                try:
                    b.operate(self)  # type: ignore
                except BehaveCancelled:
                    continue
                except OutBoundsBehave as e:
                    return self._fail(e)
        return self

    def call(self, target: Callable[..., T], **additional):
        if self.matched:
            return target(**self.all_matched_args, **additional)

    def _fail(self, exc: Union[Type[BaseException], BaseException, str]):
        arp = Arpamar(self.source)
        arp.matched = False
        arp.head_matched = True
        arp.error_info = exc
        return arp

    def __require__(self, parts: List[str]) -> Tuple[Union[Dict[str, Any], OptionResult, SubcommandResult, None], str]:
        """如果能够返回, 除开基本信息, 一定返回该path所在的dict"""
        if len(parts) == 1:
            part = parts[0]
            if part in self.main_args:
                return self.main_args, part
            if part in self.other_args:
                return self.other_args, part
            if part in self.components:
                return self.components[part], ''
            if part in {"options", "subcommands"}:
                return getattr(self, f"_{part}"), ''
            if part in {"main_args", "other_args"}:
                return getattr(self, part), ''
            return (self.all_matched_args, '') if part == "args" else (None, part)
        prefix = parts.pop(0)  # parts[0]
        if prefix in {"options", "subcommands"} and prefix in self.components:
            raise RuntimeError(config.lang.arpamar_ambiguous_name.format(target=prefix))

        def _r_opt(_p: str, _s: List[str], _opts: Dict[str, OptionResult]):
            if _p == "options":
                if not _s:
                    _c = _opts
                elif not (_c := _opts.get(__p := _s.pop(0))):
                    return _opts, __p
            else:
                _c = _opts[_p]
            if not _s:  # options.foo
                return _c, ''
            if (_e := _s.pop(0)) in {'args', 'value'}:
                return _c, _e
            return (_c['args'], _e) if _e in _c['args'] else (None, _e)

        if prefix == "options" or prefix in self._options:
            return _r_opt(prefix, parts, self._options)
        if prefix == "subcommands" or prefix in self._subcommands:
            if prefix == "subcommands" and not (_cache := self._subcommands.get(_prefix := parts.pop(0))):
                return self._subcommands, _prefix
            else:
                _cache = self._subcommands[prefix]
            if not parts:
                return _cache, ''
            if (end := parts.pop(0)) in {"args", "value"}:
                return _cache, end
            if end in _cache['args']:
                return _cache['args'], end
            if end == "options" and end in _cache['options']:
                raise RuntimeError(config.lang.arpamar_ambiguous_name.format(target=f"{prefix}.{end}"))
            if end == "options" or end in _cache['options']:
                return _r_opt(end, parts, _cache['options'])
        return None, prefix

    @overload
    def query(self, path: str) -> Union[Mapping[str, Any], Any, None]:
        ...

    @overload
    def query(self, path: str, default: T) -> Union[T, Mapping[str, Any], Any]:
        ...

    def query(self, path: str, default: Optional[T] = None) -> Union[Any, Mapping[str, Any], T, None]:
        """根据path查询值"""
        cache, endpoint = self.__require__(path.split('.'))
        if cache is None:
            return default
        if not endpoint:
            return MappingProxyType(cache) if cache is not None else default
        return cache.get(endpoint, default)

    def update(self, path: str, value: Any):
        """根据path更新值"""
        parts = path.split('.')
        cache, endpoint = self.__require__(parts)
        if cache is None:
            return
        if endpoint:
            self._record.add(path)
            cache[endpoint] = value
        elif isinstance(value, dict):
            cache.update(value)
            self._record.update([f"{path}.{k}" for k in value])

    def query_with(self, arg_type: Type[T], path: Optional[str] = None, default: Optional[T] = None) -> Optional[T]:
        """根据类型查询参数"""
        if path:
            return res if isinstance(res := self.query(path, Empty), arg_type) else default
        with suppress(IndexError):
            return [v for v in self.all_matched_args.values() if isinstance(v, arg_type)][0]
        return default

    def find(self, path: str) -> bool:
        """查询路径是否存在"""
        return self.query(path, Empty) != Empty

    def clean(self):
        if not self._record:
            return
        for path in self._record:
            parts = path.split('.')
            cache, _ = self.__require__(parts[:-1])
            if not cache:
                return
            cache.pop(parts[-1], None)

    @overload
    def __getitem__(self, item: Type[T]) -> Optional[T]:
        ...

    @overload
    def __getitem__(self, item: str) -> Any:
        ...

    def __getitem__(self, item: Union[str, Type[T]]) -> Union[T, Any, None]:
        if isinstance(item, str):
            return self.query(item)
        if data := self.query_with(item):
            return data.popitem()[1]

    def __getattr__(self, item):
        return self.all_matched_args.get(item)

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s)) for s in ["matched", "head_matched", "error_data", "error_info"])
            return ", ".join(f"{a}={v}" for a, v in attrs if v is not None)
        else:
            attrs = [(s, getattr(self, s)) for s in ["matched", "header", "options", "subcommands"]]
            margs = self.main_args.copy()
            margs.pop('__varargs__', None)
            margs.pop('__kwargs__', None)
            margs.pop('__kwonly__', None)
            attrs.append(("main_args", margs))
            other_args = self.other_args.copy()
            other_args.pop('__varargs__', None)
            other_args.pop('__kwargs__', None)
            other_args.pop('__kwonly__', None)
            attrs.append(("other_args", other_args))
            return ", ".join(f"{a}={v}" for a, v in attrs if v)
