# Alconna
[![Licence](https://img.shields.io/github/license/ArcletProject/Alconna)](https://github.com/ArcletProject/Alconna/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-alconna)](https://pypi.org/project/arclet-alconna)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-alconna)](https://www.python.org/)

`Alconna` 隶属于`ArcletProject`， 在`Cesloi`内有内置

`Alconna` 是 `Cesloi-CommandAnalysis` 的高级版，支持解析消息链

一般情况下请当作简易的消息链解析器/命令解析器

## 文档

[暂时的文档](https://github.com/RF-Tar-Railt/Cesloi/wiki/Alconna-Introduction)

## Example
```python
from arclet.alconna import Alconna
from arclet.alconna.component import Option, Subcommand
from arclet.alconna.types import Pattern, Args

cmd = Alconna(
    command="/pip",
    options=[
        Subcommand("install", Option("--upgrade"), args=Args["pak_name": Pattern(str)])
        Option("list"),
    ]
)

msg = "/pip install cesloi --upgrade"
result = cmd.analysis_message(msg) # 该方法返回一个Arpamar类的实例
print(result.get('install'))
```
其结果为
```
{'pak_name': 'cesloi', 'upgrade': Ellipsis}
```

## 用法
通过阅读Alconna的签名可以得知，Alconna支持四大类参数：
 - `headers` : 呼叫该命令的命令头，一般是你的机器人的名字或者符号，与command至少有一个填写. 例如: /, !
 - `command` : 命令名称，你的命令的名字，与headers至少有一个填写
 - `options` : 命令选项，你的命令可选择的所有option,是一个包含Subcommand与Option的列表
 - `main_argument` : 主参数，填入后当且仅当命令中含有该参数时才会成功解析

解析时，先判断命令头(即 headers + command),再判断options与main argument, 这里options与main argument在输入指令时是不分先后的

假设有个Alconna如下:
```python
Alconna(
    headers=["/"],
    command="name",
    options=[
        Subcommand(
            "sub_name",
            Option("sub_opt", sub_opt_arg="sub_arg"), 
            sub_main_arg="sub_main_arg"
        ),
        Option("opt", opt_arg="opt_arg")
    ]
    main_args="main_args"
)
```
则它可以解析如下命令:
```
/name sub_name sub_opt sub_arg sub_main_arg opt arg main_args
/name sub_name sub_main_arg opt arg main_argument
/name main_args opt arg
/name main_args
```
解析成功的命令的参数会保存在analysis_message方法返回的`Arpamar`实例中

## 性能参考
在 i5-10210U 处理器上, `Alconna` 的性能大约为 `38000~61000 msg/s`, 取决于 `Alconna` 的复杂程度
