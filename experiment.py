from functools import wraps


class Foo:
    def __init__(self, value):
        self._value = value

    def foo(self):
        return self._value

    def bar(self):
        return self._value * 2


def print_func(func):
    @wraps(func)
    def new_func(*args, **kwargs):
        print(func.__name__)
        return func(*args, **kwargs)

    return new_func


def wrap_print(obj):
    for field in dir(obj):
        if field.startswith('_'):
            continue

        if callable(method := getattr(obj, field)):
            method = print_func(method)
            setattr(obj, field, method)

    return obj


the_foo = Foo(7)
print(the_foo.foo())
print(the_foo.bar())

the_foo = wrap_print(the_foo)
print(the_foo.foo())
print(the_foo.bar())

