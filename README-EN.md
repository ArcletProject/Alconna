![](https://socialify.git.ci/ArcletProject/Alconna/image?description=1&descriptionEditable=A%20High-performance%2C%20Generality%2C%20Humane%20Command%20Line%20Arguments%20Parser%20Library.&font=Inter&forks=1&issues=1&language=1&logo=https%3A%2F%2Favatars.githubusercontent.com%2Fu%2F42648639%3Fs%3D400%26u%3Da81d93f3683d0a3b7d38ea8e6a4903355986e8c7%26v%3D4&name=1&owner=1&pattern=Brick%20Wall&stargazers=1&theme=Light)

<div align="center"> 

# Alconna

</div>

![Alconna](https://img.shields.io/badge/Arclet-Alconna-2564c2.svg)
![latest release](https://img.shields.io/github/release/ArcletProject/Alconna)
[![Licence](https://img.shields.io/github/license/ArcletProject/Alconna)](https://github.com/ArcletProject/Alconna/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-alconna)](https://pypi.org/project/arclet-alconna)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-alconna)](https://www.python.org/)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FArcletProject%2FAlconna.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2FArcletProject%2FAlconna?ref=badge_shield)

[**简体中文**](README.md)|[**English**](README-EN.md)

## About

`Alconna` is a powerful cli tool for parsing message chain or other raw message data. It is an overload version of `CommandAnalysis`, affiliated to `ArcletProject`.

`Alconna` has a large number of built-in components and complex parsing functions. ~~But do not afraid~~, you can use it as a simple command parser.

## Installation

pip
```shell
$ pip install --upgrade arclet-alconna
$ pip install --upgrade arclet-alconna[full]
$ pip install --upgrade arclet-alconna[all]
```

## Documentation

Official Document : [👉Link](https://arcletproject.github.io/docs/alconna/tutorial)

Relevant Document : [📚Docs](https://graiax.cn/guide/alconna.html#alconna)

## A Simple Example

```python
from arclet.alconna import Alconna, Option, Slot, store_true

cmd = Alconna(
    "/pip", Slot("install"), Slot("pak", str), Option("-u|--upgrade", action=store_true, default=False)
)

result = cmd.parse("/pip install cesloi --upgrade")
print(result.options["upgrade"].value)
print(result.main_args['pak'])
```

Output as follows:
```
True
'cesloi'
```

## Communication

QQ Group: [Link](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## Features

* High Performance. On i5-10210U, performance is about `120000 msg/s`; test script: [benchmark](benchmark.py)
* Powerful Automatic Type Parse and Conversion
* Customizable Language File, Support i18n

Example of Type Conversion:

```python
from arclet.alconna import Alconna, Slot
from pathlib import Path

read = Alconna("read", Slot("data", bytes))

@read.bind
def _(data: bytes):
    print(type(data))

read.parse(["read", b'hello'])
read.parse("read test_fire.py")
read.parse(["read", Path("test_fire.py")])

'''
<class 'bytes'>
<class 'bytes'>
<class 'bytes'>
'''
```


Example of `typing` Support:
```python
from typing import Annotated  # or typing_extensions.Annotated
from arclet.alconna import Alconna, Slot

alc = Alconna("test", Slot("foo", Annotated[int, lambda x: x % 2 == 0]))
alc.parse("test 2")
alc.parse("test 3")

'''
'foo': 2
ParamsUnmatched: Param '3' is not matched.
'''
```

## License

Alconna is licensed under the [MIT License](LICENSE).

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FArcletProject%2FAlconna.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FArcletProject%2FAlconna?ref=badge_large)

## Acknowledgement

[JetBrains](https://www.jetbrains.com/): Support Authorize for [PyCharm](https://www.jetbrains.com/pycharm/)<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)