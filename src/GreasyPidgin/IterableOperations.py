
from re import I


def flatten(x):
    if isinstance(x, list):
        for item in x:
            yield from flatten(item)
    elif isinstance(x, str):
        for ch in x:
            yield ch
    else:
        yield x

def isNested(iterable):
    bool = False
    if isinstance(iterable,(list,tuple,set)):
        bool = all([isinstance(iter, (tuple, list)) for iter in iterable])
    return bool

def ensureList(value):
    if isinstance(value, (int, float, str)):
        value = [value]
    if isinstance(value, (tuple, set)):
        value= list(value)
    return value