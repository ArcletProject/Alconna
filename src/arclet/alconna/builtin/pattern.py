import inspect
import re
from typing import Type, Tuple, Callable, Literal, TypeVar, Any, Union
from arclet.alconna import config, ParamsUnmatched, Args
from arclet.alconna.analysis.base import analyse_args
from arclet.alconna.typing import BasePattern, Empty, pattern_map, PatternModel, set_converter

TOrigin = TypeVar("TOrigin")


class ObjectPattern(BasePattern):
    def __init__(
            self,
            origin: Type[TOrigin],
            limit: Tuple[str, ...] = (),
            flag: Literal["urlget", "part", "json"] = "part",
            **suppliers: Callable
    ):
        self._args = Args()
        self._names = []
        for param in inspect.signature(origin.__init__).parameters.values():
            name = param.name
            anno = param.annotation
            default = param.default
            if name in ("self", "cls"):
                continue
            if limit and name not in limit:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if anno is Empty:
                anno = pattern_map[str]
            elif inspect.isclass(anno) and issubclass(anno, str):
                anno = pattern_map[str]
            elif inspect.isclass(anno) and issubclass(anno, int):
                anno = pattern_map[int]
            if name in suppliers and inspect.isclass(anno):
                _s_sig = inspect.signature(suppliers[name])
                if len(_s_sig.parameters) == 1 or (len(_s_sig.parameters) == 2 and inspect.ismethod(suppliers[name])):
                    anno = BasePattern(
                        model=PatternModel.TYPE_CONVERT, origin=anno, converter=lambda x: suppliers[name](x)
                    )
                elif len(_s_sig.parameters) == 0 or (len(_s_sig.parameters) == 1 and inspect.ismethod(suppliers[name])):
                    default = suppliers[name]()
                else:
                    raise TypeError(
                        config.lang.types_supplier_params_error.format(target=name, origin=origin.__name__)
                    )
            self._names.append(name)
            self._args.add_argument(name, value=anno, default=default)
        self.flag = flag
        if flag == 'part':
            self._re_pattern = re.compile(";".join(f"(?P<{i}>.+?)" for i in self._names))
        elif flag == 'urlget':
            self._re_pattern = re.compile("&".join(f"{i}=(?P<{i}>.+?)" for i in self._names))
        elif flag == 'json':
            self._re_pattern = re.compile(r"\{" + ",".join(f"\\'{i}\\':\\'(?P<{i}>.+?)\\'" for i in self._names) + "}")
        else:
            raise TypeError(config.lang.types_type_error.format(target=flag))
        super().__init__(model=PatternModel.TYPE_CONVERT, origin=origin, alias=origin.__name__)
        set_converter(self)

    def match(self, input_: Union[str, Any]) -> TOrigin:
        if isinstance(input_, self.origin):
            return input_
        elif not isinstance(input_, str):
            raise ParamsUnmatched(config.lang.args_type_error.format(target=input_.__class__))
        if not (mat := self._re_pattern.fullmatch(input_)):
            raise ParamsUnmatched(config.lang.args_error.format(target=input_))
        res = analyse_args(self._args, list(mat.groupdict().values()), raise_exception=False)
        if not res:
            raise ParamsUnmatched(config.lang.args_error.format(target=input_))
        return self.origin(**res)

    def __call__(self, *args, **kwargs):
        return self.origin(*args, **kwargs)

    def __eq__(self, other):
        return isinstance(other, ObjectPattern) and self.origin == other.origin
