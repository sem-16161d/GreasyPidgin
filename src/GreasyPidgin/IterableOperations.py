
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
    nested = False
    if isinstance(iterable,(list,tuple,set)):
        nested = all([isinstance(item, (tuple, list)) for item in iterable])
    return nested

def ensureList(value):
    if isinstance(value, (int, float, str)):
        value = [value]
    if isinstance(value, (tuple, set)):
        value= list(value)
    return value