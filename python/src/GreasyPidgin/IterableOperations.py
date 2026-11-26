from numbers import Number


def flatten(x):
    """Yield the items of arbitrarily nested lists / tuples; strings stay whole."""
    if isinstance(x, (list, tuple)):
        for item in x:
            yield from flatten(item)
    else:
        yield x


def isNested(iterable):
    """True for a non-empty list / tuple / set whose items are all lists or tuples."""
    return (isinstance(iterable, (list, tuple, set)) and len(iterable) > 0
            and all(isinstance(item, (tuple, list)) for item in iterable))


def ensureList(value):
    """Wrap a single value (number, string, None-free scalar) in a list; tuples and sets become lists."""
    if isinstance(value, (Number, str)):
        return [value]
    if isinstance(value, (tuple, set)):
        return list(value)
    return value
