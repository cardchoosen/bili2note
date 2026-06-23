# Python装饰器原理与实现

> 原视频：模拟测试字幕
> UP主：测试 · 时长：01:24
> 笔记生成：2026-06-23 · 转写来源：AI字幕

## 装饰器的本质

装饰器本质上是一个函数，它接收一个函数作为参数，返回一个新的函数。它的价值在于：在不修改原函数代码的前提下，给函数增加额外功能。这是一种优雅的代码复用方式，把横切关注点（如日志、计时、权限校验）从业务逻辑中剥离出来。

## 一个最小的例子

假设有一个打印 hello 的函数，想在它执行前后各打印一行日志，又不想改动函数本身。这时可以定义一个 log 装饰器：它接收 func 作为参数，内部定义一个 wrapper 函数，wrapper 里先打印 before，然后调用原函数，再打印 after，最后返回 wrapper。

```python
def log(func):
    def wrapper():
        print("before")
        func()
        print("after")
    return wrapper

@log
def hello():
    print("hello")

hello()
# before
# hello
# after
```

用 `@log` 语法糖加在 hello 函数上，调用 hello 时实际执行的是 wrapper——这就是装饰器的基本原理。`@log` 等价于 `hello = log(hello)`，语法糖只是让这件事写起来更直观。

## functools.wraps 的作用

直接写 wrapper 有一个隐患：被装饰后的函数 `__name__` 会变成 `wrapper`，`__doc__` 也会丢失。这在调试和反射场景下会带来困扰。Python 标准库提供了 `functools.wraps` 来解决这个问题，用它装饰 wrapper 可以保留原函数的元信息：

```python
from functools import wraps

def log(func):
    @wraps(func)
    def wrapper():
        print("before")
        func()
        print("after")
    return wrapper
```

加了 `@wraps(func)` 后，`hello.__name__` 仍然是 `hello` 而不是 `wrapper`。写装饰器时务必记得加 wraps，这是一个容易被忽略但很关键的细节。
