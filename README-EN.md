<div align="center"> 

# Alconna

</div>

![Alconna](https://img.shields.io/badge/Arclet-Alconna-2564c2.svg)
![latest release](https://img.shields.io/github/release/ArcletProject/Alconna)
[![Licence](https://img.shields.io/github/license/ArcletProject/Alconna)](https://github.com/ArcletProject/Alconna/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-alconna)](https://pypi.org/project/arclet-alconna)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-alconna)](https://www.python.org/)

`Alconna` is a powerful cli tool for parsing message chain or other raw message data. It is an overload version of `Cesloi-CommandAnalysis`, affiliated to `ArcletProject`.

`Alconna` has a large number of built-in components and complex parsing functions. ~~But do not afraid~~, you can use it as a simple command parser.

## Installation

pip
```shell
$ pip install --upgrade arclet-alconna
```

## Documentation

Official Document : [👉Link](https://arcletproject.github.io/docs/alconna/tutorial)

Relevant Document : [📚Docs](https://graiax.cn/guide/alconna.html#alconna)

## A Simple Example

```python
from arclet.alconna import Alconna, Option, Subcommand, Args

cmd = Alconna(
    "/pip",
    options=[
        Subcommand("install", [Option("-u|--upgrade")], Args.pak_name[str]),
        Option("list"),
    ]
)

result = cmd.parse("/pip install cesloi --upgrade") # This method returns an 'Arpamar' class instance.
print(result.get('install'))  # Or result.install
```

Output as follows:
```
{'pak_name': 'cesloi', 'upgrade': Ellipsis}
```

## Communication

QQ Group: [Link](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## Features

* 高效. 在 i5-10210U 处理器上, 性能大约为 `41000~101000 msg/s`; 测试脚本: [benchmark](dev_tools/benchmark.py) 
* 精简、多样的构造方法
* 强大的自动类型转换功能
* 可传入同步与异步的 action 函数
* 高度自定义的 HelpFormat、Analyser
* 自定义语言文件, 间接支持 i18n
* Duplication、FuzzyMatch等一众特性

* High Performance. On i5-10210U, performance is about `41000~101000 msg/s`; test script: [benchmark](dev_tools/benchmark.py)
* Simple and Flexible Constructor 
* Powerful Automatic Type Conversion
* Support Synchronous and Asynchronous Actions
* Customizable HelpFormatter and Analyser
* Customizable Language File, Directly Support i18n
* Various Features (Duplication, FuzzyMatch, etc.)

Example of Type Conversion:

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

Example of FuzzyMatch:

```python
from arclet.alconna import Alconna
alc = Alconna('!test_fuzzy', "foo:str", is_fuzzy_match=True)
alc.parse("！test_fuzy foo bar")

'''
！test_fuzy not matched. Are you mean "!test_fuzzy"?
'''
```

## License

Alconna is licensed under the [MIT License](LICENSE).

## Acknowledgement

[JetBrains](https://www.jetbrains.com/): Support Authorize for [PyCharm](https://www.jetbrains.com/pycharm/)<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)