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

## About

`Alconna` is a powerful cli tool for parsing message chain or other raw message data. It is an overload version of `CommandAnalysis`, affiliated to `ArcletProject`.

`Alconna` has a large number of built-in components and complex parsing functions. ~~But do not afraid~~, you can use it as a simple command parser.

## Installation

pip
```shell
$ pip install --upgrade arclet-alconna
$ pip install --upgrade arclet-alconna[full]
```

## Documentation

Official Document : [👉Link](https://arclet.top/docs/tutorial/alconna)

Relevant Document : [📚Docs](https://graiax.cn/guide/message_parser/alconna.html)

## A Simple Example

```python
from arclet.alconna import Alconna, Option, Subcommand, Args

cmd = Alconna(
    "/pip",
    Subcommand("install", Option("-u|--upgrade"), Args.pak_name[str]),
    Option("list")
)

result = cmd.parse("/pip install numpy --upgrade") # This method returns an 'Arparma' class instance.
print(result.query('install'))  # Or result.install
```

Output as follows:
```
value=None args={'pak_name': 'numpy'} options={'upgrade': value=Ellipsis args={}} subcommands={}
```

## Communication

QQ Group: [Link](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

## Features

* High Performance. On i5-10210U, performance is about `71000~289000 msg/s`; test script: [benchmark](benchmark.py)
* Intuitive way to create command components
* Powerful Automatic Type Parse and Conversion
* Customizable Help Text Formatter and Control of Command Analyser
* i18n Support
* Cache of input command for quick response of repeated command
* Easy-to-use Construct and Usage of Command Shortcut
* Can bind callback function to execute after command parsing
* Can create command completion session to implement multi-round continuous completion prompt
* Various Features (FuzzyMatch, Output Capture, etc.)

Example of Callback Executor:

```python
# callback.py
from arclet.alconna import Alconna, Args

alc = Alconna("callback", Args["foo", int]["bar", str])

@alc.bind()
def callback(foo: int, bar: str):
    print(f"foo: {foo}")
    print(f"bar: {bar}")
    print(bar * foo)
    
if __name__ == "__main__":
    alc()
```

```shell
$ python callback.py 3 hello
foo: 3
bar: hello
hellohellohello
```


Example of Type Conversion:

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

Example of Component creation:
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

Example of Command Shortcut:
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

Example of Command Completion:
```python
# completion.py
from arclet.alconna import Alconna, Args, Option

alc = Alconna("complete", Args["bar", int]) + Option("foo") + Option("fool")

if __name__ == "__main__":
    alc()
```

```shell
$ python completion.py ?
suggest input follows:
* bar: int
* --help
* -h
* foo
* fool
```

Example of `typing` Support:
```python
from typing import Annotated  # or typing_extensions.Annotated
from arclet.alconna import Alconna, Args

alc = Alconna("test", Args.foo[Annotated[int, lambda x: x % 2 == 0]])
alc.parse("test 2")
alc.parse("test 3")

'''
'foo': 2
ParamsUnmatched: param 3 is incorrect
'''
```

Example of FuzzyMatch:

```python
# fuzzy.py
from arclet.alconna import Alconna, CommandMeta, Arg

alc = Alconna('!test_fuzzy', Arg("foo", str), meta=CommandMeta(fuzzy_match=True))

if __name__ == "__main__":
    alc()

```

```shell
$ python fuzzy.py /test_fuzzy foo bar
/test_fuzy not matched. Are you mean "!test_fuzzy"?
```

## Examples

| Name           | File                                     |
|----------------|------------------------------------------|
| Calculate      | [calculate.py](./example/calculate.py)   |
| Execute        | [exec_code.py](./example/exec_code.py)   |
| Request Route  | [endpoint.py](./example/endpoint.py)     |
| Image Search   | [img_search.py](./example/img_search.py) |
| PIP            | [pip.py](./example/pip.py)               |
| Database Query | [exec_sql.py](./example/exec_sql.py)     |

## License

Alconna is licensed under the [MIT License](LICENSE).

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FArcletProject%2FAlconna.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FArcletProject%2FAlconna?ref=badge_large)

## Acknowledgement

[JetBrains](https://www.jetbrains.com/): Support Authorize for [PyCharm](https://www.jetbrains.com/pycharm/)<br>
[<img src="https://cdn.jsdelivr.net/gh/Kyomotoi/CDN@master/noting/jetbrains-variant-3.png" width="200"/>](https://www.jetbrains.com/)