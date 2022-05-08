from typing import Union, Dict, List, Any, Optional, TYPE_CHECKING, Type, TypeVar, Tuple
from .types import DataCollection
from .lang import lang_config
from .base import SubcommandResult, OptionResult
from .exceptions import BehaveCancelled
from .components.behavior import T_ABehavior, requirement_handler
from .components.duplication import AlconnaDuplication, generate_duplication

if TYPE_CHECKING:
    from .core import Alconna

T = TypeVar('T')
T_Duplication = TypeVar('T_Duplication', bound=AlconnaDuplication)


class Arpamar:
    """
    亚帕玛尔(Arpamar), Alconna的珍藏宝书

    Example:

    1. `Arpamar.main_args`: 当 Alconna 写入了 main_argument 时,该参数返回对应的解析出来的值

        2. `Arpamar.header`: 当 Alconna 的 command 内写有正则表达式时,该参数返回对应的匹配值

        3. `Arpamar.has`: 判断 Arpamar 内是否有对应的属性

        4. `Arpamar.get`: 返回 Arpamar 中指定的属性

        5. `Arpamar.matched`: 返回命令是否匹配成功

    """

    def __init__(self, alc: "Alconna"):
        self.source: "Alconna" = alc
        self.origin: Union[str, DataCollection] = ''
        self.matched: bool = False
        self.head_matched: bool = False
        self.error_data: List[Union[str, Any]] = []
        self.error_info: Optional[Union[str, BaseException]] = None
        self.other_args: Dict[str, Any] = {}
        self.main_args: Dict[str, Any] = {}

        self._header: Optional[Union[Dict[str, Any], bool]] = None
        self._options: Dict[str, OptionResult] = {}
        self._subcommands: Dict[str, SubcommandResult] = {}

    @staticmethod
    def _filter_opt(opt: OptionResult):
        if args := opt['args']:
            return args
        return opt['value']

    @staticmethod
    def _filter_sub(sub: SubcommandResult):
        val = {k: Arpamar._filter_opt(v) for k, v in sub['options'].items()}
        val.update(sub['args'])
        if val:
            return val
        return sub['value']

    @property
    def header(self):
        """返回可能解析到的命令头中的信息"""
        if self._header:
            return self._header
        return self.head_matched

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
        return generate_duplication(self.source).set_target(self)

    def encapsulate_result(
            self,
            header: Union[Dict[str, Any], bool, None],
            main_args: Dict[str, Any],
            options: Dict[str, OptionResult],
            subcommands: Dict[str, SubcommandResult]
    ) -> None:
        """处理 Arpamar 中的数据"""
        self.main_args = main_args
        self._header = header
        self._options = options
        self._subcommands = subcommands
        for v in options.values():
            self.other_args = {**self.other_args, **v['args']}
        for k in subcommands:
            v = subcommands[k]
            self.other_args = {**self.other_args, **v['args']}
            if sub_opts := v['options']:
                for vv in sub_opts.values():
                    self.other_args = {**self.other_args, **vv['args']}

    def execute(self, behaviors: Optional[List[T_ABehavior]] = None):
        behaviors = [
            *self.source.behaviors,
            *(behaviors or [])
        ]
        for behavior in behaviors:
            res = requirement_handler(behavior)
            for b in res:
                try:
                    b.operate(self)
                except BehaveCancelled:
                    continue
        return self

    def __require__(
            self,
            parts: List[str]
    ) -> Tuple[Optional[Union[Dict[str, Any], OptionResult, SubcommandResult]], str]:
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
                return getattr(self, "_" + part), ''
            if part in {"main_args", "other_args"}:
                return getattr(self, part), ''
            if part == "args":
                return self.all_matched_args, ''
            return None, part
        prefix = parts.pop(0)  # parts[0]
        if prefix in {"options", "subcommands"} and prefix in self.components:
            raise RuntimeError(lang_config.arpamar_ambiguous_name.format(target=prefix))

        def _r_opt(_p: str, _s: List[str], _opts: Dict[str, OptionResult]):
            if _p == "options":
                if not _s:
                    _c = _opts
                elif not (_c := _opts.get(_s.pop(0))):
                    return None, _p
            else:
                _c = _opts[prefix]
            if not _s:  # options.foo
                return _c, ''
            _e = _s.pop(0)
            if _e in {'args', 'value'}:
                return _c, _e
            if _e in _c['args']:
                return _c['args'], _e
            return None, _e

        if prefix == "options" or prefix in self._options:
            return _r_opt(prefix, parts, self._options)
        if prefix == "subcommands" or prefix in self._subcommands:
            if prefix == "subcommands" and not (_cache := self._subcommands.get(parts.pop(0))):
                return None, prefix
            else:
                _cache = self._subcommands[prefix]
            if not parts:
                return _cache, ''
            end = parts.pop(0)
            if end in {"args", "value"}:
                return _cache, end
            if end in _cache['args']:
                return _cache['args'], end
            if end == "options" and end in _cache['options']:
                raise RuntimeError(lang_config.arpamar_ambiguous_name.format(target=f"{prefix}.{end}"))
            if end == "options" or end in _cache['options']:
                return _r_opt(end, parts, _cache['options'])

    def query(self, path: str, default: Any = None) -> Union[Dict[str, Any], Any, None]:
        """根据path查询值"""
        parts = path.split('.')
        cache, endpoint = self.__require__(parts)
        if cache is None:
            return default
        if not endpoint:
            return cache if cache is not None else default
        return cache.get(endpoint, default)

    def update(self, path: str, value: Any):
        """根据path更新值"""
        parts = path.split('.')
        cache, endpoint = self.__require__(parts)
        if not endpoint:
            cache.update(value)
        else:
            cache[endpoint] = value

    def query_with(self, arg_type: Type[T], name: Optional[str] = None) -> Optional[Dict[str, T]]:
        """根据类型查询参数"""
        if name:
            res = self.query(name)
            return res if isinstance(res, arg_type) else None
        return {k: v for k, v in self.all_matched_args.items() if isinstance(v, arg_type)}

    def find(self, name: str) -> bool:
        """查询是否存在"""
        return any([name in self.components, name in self.main_args, name in self.other_args])

    def __getitem__(self, item: str) -> Any:
        return self.query(item)

    def __getattr__(self, item):
        return self.all_matched_args.get(item)

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s)) for s in ["matched", "head_matched", "error_data", "error_info"])
            return ", ".join([f"{a}={v}" for a, v in attrs if v is not None])
        else:
            attrs = ((s, getattr(self, s)) for s in [
                "matched", "header", "main_args", "options", "subcommands", "other_args"
            ])
            return ", ".join([f"{a}={v}" for a, v in attrs if v])
