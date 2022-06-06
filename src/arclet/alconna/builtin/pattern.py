import inspect
from types import LambdaType
from typing import Type, Tuple, Callable, Literal, TypeVar, Dict, Any, get_args

from arclet.alconna import lang_config, ParamsUnmatched
from arclet.alconna.typing import BasePattern, Empty, pattern_map, PatternModel, set_converter

TOrigin = TypeVar("TOrigin")


class ObjectPattern(BasePattern):

    def __init__(
            self,
            origin: Type[TOrigin],
            limit: Tuple[str, ...] = (),
            head: str = "",
            flag: Literal["http", "part", "json"] = "part",
            **suppliers: Callable
    ):
        """
        将传入的对象类型转换为接收序列号参数解析后实例化的对象

        Args:
            origin: 原始对象
            limit: 指定该对象初始化时需要的参数
            head: 是否需要匹配一个头部
            flag: 匹配类型
            suppliers: 对象属性的匹配方法
        """
        self.origin = origin
        self._require_map: Dict[str, Callable] = {}
        self._supplement_map: Dict[str, Callable] = {}
        self._transform_map: Dict[str, Callable] = {}
        self._params: Dict[str, Any] = {}
        _re_pattern = ""
        _re_patterns = []
        sig = inspect.signature(origin.__init__)
        for param in sig.parameters.values():
            name = param.name
            if name in ("self", "cls"):
                continue
            if limit and name not in limit:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            self._params[name] = None
            if name in suppliers:
                _s_sig = inspect.signature(suppliers[name])
                if _s_sig.return_annotation in get_args(param.annotation):
                    if len(_s_sig.parameters) == 0 or (
                            len(_s_sig.parameters) == 1 and inspect.ismethod(suppliers[name])
                    ):
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1 or (
                            len(_s_sig.parameters) == 2 and inspect.ismethod(suppliers[name])
                    ):
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                        elif flag == "json":
                            _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                        elif flag == "part":
                            _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                    else:
                        raise TypeError(
                            lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__)
                        )
                elif isinstance(suppliers[name], LambdaType):
                    if len(_s_sig.parameters) == 0:
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1:
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                        elif flag == "json":
                            _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                        elif flag == "part":
                            _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                    else:
                        raise TypeError(
                            lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__)
                        )
                else:
                    raise TypeError(lang_config.types_supplier_return_error.format(
                        target=name, origin=origin.__name__, source=param.annotation
                    ))
            elif param.default not in (Empty, None, Ellipsis):
                self._params[name] = param.default
            else:
                if not (args := get_args(param.annotation)):
                    args = (param.annotation,)
                for anno in args:
                    pat: BasePattern = pattern_map.get(anno, None)
                    if pat is not None:
                        break
                else:
                    pat = param.annotation
                    if param.annotation is Empty:
                        pat = pattern_map[str]
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, str):
                        pat = pattern_map[str]
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, int):
                        pat = pattern_map[int]
                    if pat is None:
                        raise TypeError(lang_config.types_supplier_missing.format(target=name, origin=origin.__name__))

                if isinstance(pat, ObjectPattern):
                    raise TypeError(lang_config.types_type_error.format(target=pat))
                self._require_map[name] = pat.match
                if pat.model == PatternModel.REGEX_CONVERT:
                    self._transform_map[name] = pat.converter
                if flag == "http":
                    _re_patterns.append(f"{name}=(?P<{name}>{pat.pattern.strip('()')})")  # &
                elif flag == "part":
                    _re_patterns.append(f"(?P<{name}>{pat.pattern.strip('()')})")  # ;
                elif flag == "json":
                    _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>{pat.pattern.strip('()')})\\'")  # ,
        if _re_patterns:
            if flag == "http":
                _re_pattern = (rf"{head}\?" if head else "") + "&".join(_re_patterns)
            elif flag == "json":
                _re_pattern = (f"{head}:" if head else "") + "{" + ",".join(_re_patterns) + "}"
            elif flag == "part":
                _re_pattern = (f"{head};" if head else "") + ";".join(_re_patterns)
        else:
            _re_pattern = f"{head}" if head else f"{self.origin.__name__}"

        super().__init__(
            _re_pattern,
            model=PatternModel.REGEX_MATCH, origin_type=self.origin, alias=head or self.origin.__name__,
        )
        set_converter(self)

    def match(self, text: str):
        if matched := self.regex_pattern.fullmatch(text):
            args = matched.groupdict()
            for k in self._require_map:
                if k in args:
                    self._params[k] = self._require_map[k](args[k])
                    if self._transform_map.get(k, None):
                        self._params[k] = self._transform_map[k](self._params[k])
            for k in self._supplement_map:
                self._params[k] = self._supplement_map[k]()
            return self.origin(**self._params)
        raise ParamsUnmatched(lang_config.args_error.format(target=text))

    def __call__(self, *args, **kwargs):
        return self.origin(*args, **kwargs)

    def __eq__(self, other):
        return isinstance(other, ObjectPattern) and self.origin == other.origin
