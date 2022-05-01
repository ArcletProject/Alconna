<div align="center"> 

# Alconna

</div>

![Alconna](https://img.shields.io/badge/Arclet-Alconna-2564c2.svg)
![latest release](https://img.shields.io/github/release/ArcletProject/Alconna)
[![Licence](https://img.shields.io/github/license/ArcletProject/Alconna)](https://github.com/ArcletProject/Alconna/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-alconna)](https://pypi.org/project/arclet-alconna)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-alconna)](https://www.python.org/)

**English**: [README](README-EN.md)

`Alconna` 隶属于 `ArcletProject`, 是 `Cesloi-CommandAnalysis` 的高级版，
支持解析消息链或者其他原始消息数据

`Alconna` 拥有复杂的解析功能与命令组件，但 一般情况下请当作~~奇妙~~简易的消息链解析器/命令解析器(雾)

## 安装

pip
```
pip install --upgrade arclet-alconna
```

## 文档

文档链接: [👉指路](https://arcletproject.github.io/docs/alconna/tutorial)

相关文档: [📚文档](https://graiax.cn/guide/alconna.html#alconna)

## 简单使用
```python
from arclet.alconna import Alconna, Option, Subcommand, Args

cmd = Alconna(
    "/pip",
    options=[
        Subcommand("install", [Option("-u|--upgrade")], Args.pak_name[str]),
        Option("list"),
    ]
)

result = cmd.parse("/pip install cesloi --upgrade") # 该方法返回一个Arpamar类的实例
print(result.get('install'))  # 或者 result.install
```
其结果为
```
{'pak_name': 'cesloi', 'upgrade': Ellipsis}
```

## 讨论

QQ 交流群: [链接](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## 特点

* 高效. 在 i5-10210U 处理器上, 性能大约为 `41000~101000 msg/s`; 测试脚本: [benchmark](dev_tools/benchmark.py) 
* 精简、多样的构造方法
* 强大的自动类型转换功能
* 可传入同步与异步的 action 函数
* 高度自定义的 HelpFormat、Analyser
* 自定义语言文件, 支持 i18n
* 命令输入缓存, 以保证重复命令的快速响应
* Duplication、FuzzyMatch等一众特性

类型转换示范:
```python
from arclet.alconna import Alconna, Args
from pathlib import Path

read = Alconna(
    "read", Args["data":bytes], 
    action=lambda data: print(type(data))
)

read.parse(["read", b'hello'])
read.parse("read test_fire.py")
read.parse(["read", Path("test_fire.py")])

'''
<class 'bytes'>
<class 'bytes'>
<class 'bytes'>
'''
```

模糊匹配示范:
```python
from arclet.alconna import Alconna
alc = Alconna('!test_fuzzy', "foo:str", is_fuzzy_match=True)
alc.parse("！test_fuzy foo bar")

'''
！test_fuzy not matched. Are you mean "!test_fuzzy"?
'''
```

## 许可

Alconna 采用 [MIT](LICENSE) 许可协议

## 鸣谢

[JetBrains](https://www.jetbrains.com/): 为本项目提供 [PyCharm](https://www.jetbrains.com/pycharm/) 等 IDE 的授权<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)