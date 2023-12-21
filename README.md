![](https://socialify.git.ci/ArcletProject/Alconna/image?description=1&descriptionEditable=A%20High-performance%2C%20Generality%2C%20Humane%20Command%20Line%20Arguments%20Parser%20Library.&font=Inter&forks=1&issues=1&language=1&logo=https%3A%2F%2Farclet.top%2Fimg%2Farclet.png&name=1&owner=1&pattern=Brick%20Wall&stargazers=1&theme=Auto)
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

## 文档

文档链接: [👉指路](https://arclet.top/docs/tutorial/alconna)

相关文档: [📚文档](https://graiax.cn/guide/message_parser/alconna.html)

## 简单使用

```python
from arclet.alconna import Alconna, Option, Subcommand, Args

cmd = Alconna(
    "/pip",
    Subcommand("install", Option("-u|--upgrade"), Args.pak_name[str]),
    Option("list")
)

result = cmd.parse("/pip install numpy --upgrade") # 该方法返回一个Arpamar类的实例
print(result.query('install'))  # 或者 result.install
```
其结果为
```
value=None args={'pak_name': 'numpy'} options={'upgrade': value=Ellipsis args={}} subcommands={}
```

## 讨论

QQ 交流群: [链接](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## 特点

* 高效. 在 i5-10210U 处理器上, 性能大约为 `+71000~289000 msg/s`; 测试脚本: [benchmark](benchmark.py)
* 直观的命令组件创建方式
* 强大的类型解析与类型转换功能
* 自定义的帮助信息格式与命令解析控制
* i18n
* 命令输入缓存, 以保证重复命令的快速响应
* 易用的快捷命令创建与使用
* 可以绑定回调函数, 以便于在命令解析完成后执行
* 可创建命令补全会话, 以实现多轮连续的补全提示
* 模糊匹配、输出捕获等一众特性

执行回调示范:
```python
# callback.py
from arclet.alconna import Alconna, Args

alc = Alconna("callback", Args["foo", int]["bar", str])

@alc.bind()
def cb(foo: int, bar: str):
    print(f"foo: {foo}")
    print(f"bar: {bar}")
    print(bar * foo)

if __name__ == '__main__':
    alc()

    
```
```shell
$ python callback.py 2 hello
foo: 2
bar: hello
hellohello
```

类型转换示范:
```python
from arclet.alconna import Alconna, Args
from pathlib import Path

read = Alconna("read", Args["data", bytes])

@read.bind()
def cb(data: bytes):
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

组件创建示范:
```python
# component.py
from arclet.alconna import Alconna, Args, Option, Subcommand, store_true, count, append

alc = Alconna(
    "component",
    Args["path", str],
    Option("--verbose|-v", action=count),
    Option("-f", Args["flag", str], compact=True, action=append),
    Subcommand("sub", Option("bar", action=store_true, default=False))
)

if __name__ == '__main__':
    res = alc()
    print(res.query("path"))
    print(res.query("verbose.value"))
    print(res.query("f.flag"))
    print(res.query("sub"))
```

```shell
$ python component.py /home/arclet -vvvv -f1 -f2 -f3 sub bar
/home/arclet
4
['1', '2', '3']
(value=Ellipsis args={} options={'bar': (value=True args={})} subcommands={})
```

快捷命令示范:
```python
# shortcut.py
from arclet.alconna import Alconna, Args

alc = Alconna("eval", Args["content", str])
alc.shortcut("echo", {"command": "eval print(\\'{*}\\')"})

@alc.bind()
def cb(content: str):
    eval(content, {}, {})

if __name__ == '__main__':
    alc()
```

```shell
$ python shortcut.py eval print(\"hello world\")
hello world
$ python shortcut.py echo hello world!
hello world!
```

命令补全示范:
```python
# complete.py
from arclet.alconna import Alconna, Args, Option

alc = Alconna("complete", Args["bar", int]) + Option("foo") + Option("fool")

if __name__ == '__main__':
    alc()
```

```shell
$ python completion.py ?
以下是建议的输入：
* bar: int
* --help
* -h
* foo
* fool
```

typing 支持示范:
```python
from typing import Annotated  # or typing_extensions.Annotated
from arclet.alconna import Alconna, Args

alc = Alconna("test", Args.foo[Annotated[int, lambda x: x % 2 == 0]])
alc.parse("test 2")
alc.parse("test 3")

'''
'foo': 2
ParamsUnmatched: 参数 3 不正确
'''
```

模糊匹配示范:
```python
# fuzzy.py
from arclet.alconna import Alconna, CommandMeta, Arg

alc = Alconna('!test_fuzzy', Arg("foo", str), meta=CommandMeta(fuzzy_match=True))

if __name__ == '__main__':
    alc()
```

```shell
$ python fuzzy.py /test_fuzzy foo bar
无法解析 /test_fuzzy。您想要输入的是不是 "!test_fuzzy" ?
```

## 示例

| 名称    | 文件                                       |
|-------|------------------------------------------|
| 计算    | [calculate.py](./example/calculate.py)   |
| 执行代码  | [exec_code.py](./example/exec_code.py)   |
| 请求路由  | [endpoint.py](./example/endpoint.py)     |
| 图片搜索  | [img_search.py](./example/img_search.py) |
| PIP   | [pip.py](./example/pip.py)               |
| 数据库查询 | [exec_sql.py](./example/exec_sql.py)     |


## 许可

Alconna 采用 [MIT](LICENSE) 许可协议

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FArcletProject%2FAlconna.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FArcletProject%2FAlconna?ref=badge_large)

## 鸣谢

[JetBrains](https://www.jetbrains.com/): 为本项目提供 [PyCharm](https://www.jetbrains.com/pycharm/) 等 IDE 的授权<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)
