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
1.修复几个Bug
2.加入from_dict与to_dict，暂时无法支持保存action
3.命令行功能加入using

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