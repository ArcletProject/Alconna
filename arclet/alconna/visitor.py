"""
Alconna 负责命令节点访问与帮助文档生成的部分
"""
from typing import List, Dict, Optional, Any, Literal, Union, TYPE_CHECKING
from abc import ABCMeta, abstractmethod
from .exceptions import DuplicateCommand
from .lang_config import lang_config
from .base import CommandNode
from .component import Subcommand, Option

if TYPE_CHECKING:
    from .main import Alconna


class AbstractHelpTextFormatter(metaclass=ABCMeta):
    """
    帮助文档格式化器

    该格式化器负责将传入的命令节点字典解析并生成帮助文档字符串
    """

    @abstractmethod
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        """
        help text的生成入口
        """
        pass

    @abstractmethod
    def param(self, parameter: Dict[str, Any]) -> str:
        """
        对单个参数的描述
        """
        pass

    @abstractmethod
    def parameters(self, params: List[Dict[str, Any]], separator: str = " ") -> str:
        """
        参数列表的描述
        """
        pass

    @abstractmethod
    def header(self, root: Dict[str, Any]) -> str:
        """
        头部节点的描述
        """
        pass

    @abstractmethod
    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        """
        每个子节点的描述
        """
        pass

    @abstractmethod
    def body(self, parts: List[Dict[str, Any]]) -> str:
        """
        子节点列表的描述
        """
        pass


class _BaseNode:
    """
    存储命令节点信息的基础类
    """
    node_id: int
    type: str
    name: str
    parameters: List[Dict[str, Any]]
    description: str
    separator: str
    param_separator: str
    sub_nodes: List[int]
    additional_info: Dict[str, Any]

    def __init__(self, nid: int, target: CommandNode, node_type: Literal['command', 'subcommand', 'option']):
        self.node_id = nid
        self.type = node_type
        self.name = target.name
        self.description = target.help_text
        self.parameters = []
        self.separator = target.separator
        self.param_separator = target.args.separator
        self.additional_info = {}
        for key, arg in target.args.argument.items():
            self.parameters.append({'name': key, **arg})
        self.sub_nodes = []

    def __repr__(self):
        res = f'[{self.name}, {self.description}; {self.parameters}; {self.sub_nodes}]'
        return res


class AlconnaNodeVisitor:
    """
    命令节点访问器

    该访问器会读取Alconna内的命令节点, 并转为节点树
    """
    name_list: List[str]
    node_map: Dict[int, _BaseNode]

    def __init__(self, alconna: "Alconna") -> None:
        self.name_list = [alconna.name]
        self.node_map = {0: _BaseNode(0, alconna, 'command')}
        self.node_map[0].additional_info['command'] = alconna.command
        self.node_map[0].additional_info['headers'] = alconna.headers
        self.node_map[0].additional_info['namespace'] = alconna.namespace

        for node in alconna.options:
            real_name = node.name.lstrip('-')
            if isinstance(node, Option):
                if "option:" + real_name in self.name_list:
                    raise DuplicateCommand(lang_config.visitor_duplicate_option.format(target=real_name))
                self.name_list.append("option:" + real_name)
            elif isinstance(node, Subcommand):
                if "subcommand:" + real_name in self.name_list:
                    raise DuplicateCommand(lang_config.visitor_duplicate_subcommand.format(target=real_name))
                self.name_list.append("subcommand:" + real_name)
            new_id = max(self.node_map) + 1
            if isinstance(node, Subcommand):
                self.node_map[new_id] = _BaseNode(new_id, node, 'subcommand')
                for sub_node in node.options:
                    real_sub_name = sub_node.name.lstrip('-')
                    if "subcommand:" + real_name + ":" + real_sub_name in self.name_list:
                        raise DuplicateCommand(lang_config.visitor_duplicate_suboption.format(target=real_sub_name))
                    self.name_list.append(f"subcommand:{real_name}:{real_sub_name}")
                    sub_new_id = max(self.node_map) + 1
                    self.node_map[sub_new_id] = _BaseNode(sub_new_id, sub_node, 'option')
                    self.node_map[sub_new_id].additional_info['aliases'] = sub_node.aliases
                    self.node_map[new_id].sub_nodes.append(sub_new_id)
            else:
                self.node_map[new_id] = _BaseNode(new_id, node, 'option')
                self.node_map[new_id].additional_info['aliases'] = node.aliases
            self.node_map[0].sub_nodes.append(new_id)

    def require(self, path: Optional[Union[str, List[str]]] = None) -> _BaseNode:
        """
        依据指定路径获取节点
        """
        _cache_name = ""
        _cache_node = self.node_map[0]
        if path is None:
            return _cache_node
        if isinstance(path, str):
            path = path.split('.')
        for part in path:
            if part in ("option", "subcommand"):
                _cache_name = part
                continue
            if _cache_name:
                _cache_name = _cache_name + ':' + part
                if _cache_name in self.name_list:
                    _cache_node = self.node_map[self.name_list.index(_cache_name)]
            else:
                if 'option:' + part in self.name_list and 'subcommand:' + part in self.name_list:
                    raise ValueError(lang_config.visitor_ambiguous_name.format(target=part))
                if "subcommand:" + part in self.name_list:
                    _cache_name = "subcommand:" + part
                    _cache_node = self.node_map[self.name_list.index(_cache_name)]
                elif "option:" + part in self.name_list:
                    _cache_name = "option:" + part
                    _cache_node = self.node_map[self.name_list.index(_cache_name)]
        return _cache_node

    def trace_nodes(self, root: _BaseNode):
        """
        跟踪所有的节点
        """
        return {
            "type": root.type,
            "name": root.name,
            "description": root.description,
            "parameters": root.parameters,
            "separator": root.separator,
            "param_separator": root.param_separator,
            "additional_info": root.additional_info,
            "sub_nodes": [self.trace_nodes(self.node_map[i]) for i in root.sub_nodes]
        }

    def format_node(self, formatter: AbstractHelpTextFormatter, node: Optional[_BaseNode] = None) -> str:
        """
        通过格式化器格式化节点
        """
        if not node:
            node = self.node_map[0]
        return formatter.format(self.trace_nodes(node))
