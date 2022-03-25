# Alconna 0.7.x:

## Alconna 0.7.0:
1. 内部结构大更改, 将`Command`与`Analyser`进行了一个解耦
2. 多个api更改或去除, 请留意. 该特性为不兼容的特性.
 - `Alconna`:
    - `Alconna.analyse_message`: 变更为`Alconna.parse`; 其新增参数`static`, 可以指定是否动态创建`Analyser`
    - `Alconna.order_parse`: 移除, 以`Alconna.analyser_type`为准
    - `Alconna.from_string`、`Alconna.format`: 迁移至`alconna.builtin.construct`中
 - `TemplateCommand`:
   - 变更为`CommandNode`
   - `CommandNode.__init__`: 移除`kwargs`
   - `CommandNode.__init__`: 增加参数`help_text`, `separator`, 替代`CommandNode.help`与`CommandNode.separate`
   - `CommandNode.help`: 仍然保留, 但推荐从__init__中传入
   - `CommandNode.separate`: 移除
   - `CommandNode.action`: 增加对Iterable的判断
 - `Subcommand`:
   - `Option`的传入由`*option`改为`options`
 - `Arpamar`:
   - 新增`Arpamar.get_first_arg`, 用以获取第一个参数
 - `ArgAction`:
   - 从`alconna.actions`迁移至`alconna.base`, 剩余的`ArgAction`迁移至`alconna.builtin.actions`
 - `AlconnaDecorate`:
   - 迁移至`alconna.builtin.construct`
 - `alconna.analyser`:
   - 迁移至`alconna.analysis.analyser`
   - `analyse_args`、`analyse_option`、`analyse_subcommand`、`analyse_headers`: 迁移至`alconna.analysis.parts`
3. 增加`alconna.analysis`, 其中:
 - `analysis.compile`: 用以从`Alconna`中生成`Analyser`
 - `analysis.analyse`: 隐式调用`analyser.analyse`
 - `analysis.analyse_args`: 可直接传入`Args`以针对性解析
 - `analysis.analyse_option`: 可直接传入`Option`以针对性解析
 - `analysis.analyse_subcommand`: 可直接传入`Subcommand`以针对性解析
 - `analysis.analyse_headers`: 可直接传入`Headers`以针对性解析

## Alconna 0.7.1:
1. 增加`alconna.builtin.construct.AlconnaFire`，为`Alconna`的`Fire-like`方法. 
其会尝试根据传入的对象生成`Alconna`
2. 增加 `UnionArg`, 其传入的列表中可以包含`ArgPattern`、`Type`与实际值. 为`choice`的改进
3. `Args`支持传入`Union[...]`格式的参数
4. 增加 `ObjectPattern`, 其会尝试从对象中生成`ArgPattern`, 并在解析成功后创建实例
5. `action`现支持传入异步函数
6. `AlconnaString`现在会读取`locals`的值

## Alconna 0.7.2:
1. 改进`AlconnaFire`方法, 其可通过`AlconnaFire.instance`获取目标对象的可能实例
2. 加入`SequenceArg`与`MappingArg`, 其对应解析列表、元组、集合与字典
3. Subcommand在其Args未解析时抛出异常
4. Arpamar现在可以获取subcommands与error_info
5. 增强Format
6. 修改help—action相关

## Alconna 0.7.3:
1. 优化结构
2. 增加`AlconnaFire`的Config, 用来约束`AlconnaFire`的参数
3. `AlconnaFire`现在可以解析子命令, 通过Config传入`get_subcommand=True`来启用
4. 更好的parameter-helptext
5. 新增Args构造方法`a = Args.xxx[value, default]`
6. `util.chain_filter`重新归并到`Analyser.handle_message`里
7. 增加`Force`类, 用以标记arg类型不需要进行转换; 或者在key前面加上`"#"`
8. 支持传入键值对参数与可变键值对参数, 分别用`"@"`和`"**""`标记
9. 支持将参数设为可选(即未解析成功时不报错而是跳过), 用`"?"`标记
10. `Arpamar`可以通过`XXX.opt.arg1`、`XXX.sub.sub_opt.arg2`等方式获取参数值
11. 修复bug

## Alconna 0.7.4 - 0.7.4.3:
1. 加入`Alconna.local_args`, 可用来注入额外参数
2. `actions`关键字改为`action`
3. 加入`_`前缀，用来隐藏该参数的类型注解
4. 修复bug

## Alconna 0.7.5
1. 内部类型改进, `MessageChain` -> `DataCollection`
2. 加入`ArpamarBehavior`, 用以解析后的预处理, 并提供三个预制的`behavior`:
- `set_default`: 当某个选项未被输入时, 使用该行为添加一个默认值
- `exclusion`: 当指定的两个选项同时出现时报错
- `cool_down`: 限制命令调用频率
3. 加入`NodeVisitor`与`HelpFormatter`, 并将原先给CommandNode的help生成转移给Formatter
4. 加入`AlconnaMessageProxy`, 用作对外适配接口

## Alconna 0.7.6 - 0.7.6.1
1. 增加对`Graia`系的原生支持, 位于`arclet.alconna.graia`
2. header现在可支持非文字类元素与文字混用的解析, 原来的方式请改用`元组(非文本元素, 文本)`
3. 增加`Alconna` 对 `/`与`@` 运算符的支持, 作用为重置命名空间
4. 增加`Alconna` 对 `+` 运算符的支持, 作用为增加选项
5. `Args` 可直接传入 `str`, 即`Args["foo":"foo"]` -> `Args["foo"]`
6. `Format`中的format slot可以直接写入类型, 如`"{name: str}"`
7. 修复Bug

## Alconna 0.7.7
1. 加入`Argparser`风格的HelpFormatter
2. 加入`AlconnaDuplication`, 旨在提供更好的解析结果使用
3. option的name与alias现在会根据长度自动倒换
4. 修复Bug


# Alconna 0.6.x:

## Alconna 0.6.0:
1. 加入click-like构造方法，具体内容在alconna/decorate里
2. 加入命令行功能，目前功能为便捷式编写Alconna与便捷查看docstring
3. 性能优化, 包含正则参数解析的速度提升大约10%
4. Option支持重复输入，此时多个解析结果会以列表形式存放


## Alconna 0.6.1:
1. 性能优化加强, 现在纯字符串匹配可以跑到60000msg/s (与之相对, 匹配其他消息元素可以跑到10w msg/s, re出来挨打)
2. commandline增加一个`analysis`功能，可以把命令转为命令格式
3. 修复Bug

## Alconna 0.6.2:
1. 修复几个Bug
2. 加入from_dict与to_dict，暂时无法支持保存action
3. 命令行功能加入using

## Alconna 0.6.3:
1. 修复命令行的Bug
2. 加入变长参数的支持, 可以在参数名前面添加一个`*`来表示变长参数

## Alconna 0.6.4:
1. 加入快捷指令功能, 可以用一段特殊的字符串来表示命令
2. 加入arg-choice, 可以指定参数的可选值
3. 修改docstring, 使其变得更加可读
4. 加入commandManager.broadcast功能, 可以广播命令

## Alconna 0.6.5:
1. 可以自定义all_command_help
2. 加入anti-arg, 用以反向检查参数
3. 修复一些bug

# Alconna 0.5.x:

## Alconna 0.5.1: 
1. 优化整体结构
2. 完善了action相关
3. 修改参数默认值的bug

## Alconna 0.5.2: 
紧急修复Action无法返回值的bug

## Alconna 0.5.3: 
1. 增加自定义消息元素过滤
2. headers支持传入消息元素

## Alconna 0.5.4: 
1. 优化结构
2. Arpamar 现可直接以XXX.name方式获取参数

## Alconna 0.5.5: 
1. from_sting可以传入option了
2. 修复bug

## Alconna 0.5.6: 
1. 修复Bug
2. 增加了Email的参数匹配

## Alconna 0.5.7: 
修复非ArgPattern修饰的参数无法解析消息元素的Bug

## Alconna 0.5.8: 
加入有序匹配模式与命令缓存, 能使性能大大提升

## Alconna 0.5.9: 
1. help选项可用传入一自定义函数已达到直接发送帮助说明的效果
2. 规范format方法；from_string现在可以用#加入帮助说明
3. 加入commandManager，帮助管理所有命令；支持解析原始消息链


# Alconna 0.4.x

## Alconna 0.4.1：
1. 加入 AnyParam类型 (单次泛匹配)与AllParam类型 (全部泛匹配)
2. 修改部分逻辑

## Alconna 0.4.2：
1. 加入AnyFloat预制正则
2. Args构造支持传入元组;
3. 增加两种简易构造Alconna的形式
4. 修复Bug

## Alconna 0.4.3：
1. 加入Action (暂时只针对Option)
2. Args解析出来的结果 (如bool值, int值) 会转为指定的类型