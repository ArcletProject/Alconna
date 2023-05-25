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

## 关于

`Alconna` 隶属于 `ArcletProject`, 是一个简单、灵活、高效的命令参数解析器, 并且不局限于解析命令式字符串。

`Alconna` 拥有复杂的解析功能与命令组件，但 一般情况下请当作~~奇妙~~简易的消息链解析器/命令解析器(雾)

## 安装

pip
```bash
pip install --upgrade arclet-alconna
pip install --upgrade arclet-alconna[full]
```

完整安装
```bash
pip install --upgrade arclet-alconna[all]
```

## 文档

文档链接: [👉指路](https://arcletproject.github.io/docs/alconna/tutorial)

相关文档: [📚文档](https://graiax.cn/guide/alconna.html#alconna)

## 简单使用

```python
from arclet.alconna import Alconna, Option, Slot, store_true

cmd = Alconna(
    "/pip", Slot("install"), Slot("pak", str), Option("-u|--upgrade", action=store_true, default=False)
)

result = cmd.parse("/pip install cesloi --upgrade")
print(result.options["upgrade"].value)
print(result.main_args['pak'])
```
其结果为
```
True
'cesloi'
```

## 讨论

QQ 交流群: [链接](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## 特点

* 高效. 在 i5-10210U 处理器上, 性能大约为 `120000 msg/s`; 测试脚本: [benchmark](benchmark.py)
* 强大的类型解析与转换功能
* 自定义语言文件, 支持 i18n

类型转换示范:
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


typing 支持示范:
```python
from typing import Annotated  # or typing_extensions.Annotated
from arclet.alconna import Alconna, Slot

alc = Alconna("test", Slot("foo", Annotated[int, lambda x: x % 2 == 0]))
alc.parse("test 2")
alc.parse("test 3")

'''
'foo': 2
ParamsUnmatched: 参数 3 不正确
'''
```

## 许可

Alconna 采用 [MIT](LICENSE) 许可协议

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FArcletProject%2FAlconna.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FArcletProject%2FAlconna?ref=badge_large)

## 鸣谢

[JetBrains](https://www.jetbrains.com/): 为本项目提供 [PyCharm](https://www.jetbrains.com/pycharm/) 等 IDE 的授权<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)

