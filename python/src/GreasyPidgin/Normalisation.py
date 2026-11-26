# Normalisation.py
import math
import warnings
from numbers import Real


def is_number(*args):
    """True if every argument is a real number (numpy numbers included, bool excluded)."""
    return all(isinstance(x, Real) and not isinstance(x, bool) for x in args)


# Max/MSP-like scale()  (linear if exponent=1.0)
def scale(value, in_lo, in_hi, out_lo, out_hi, exponent=1.0, clipToRange=False):
    """
    Map value from [in_lo, in_hi] to [out_lo, out_hi], like Max's [scale].
    A reversed input range (in_lo > in_hi) inverts the mapping. exponent != 1
    curves the normalized position t: t ** exponent, keeping the sign of t for
    values below the input range.
    """
    if not is_number(value, in_lo, in_hi, out_lo, out_hi, exponent):
        raise TypeError("scale: all arguments must be numbers")
    value, in_lo, in_hi, out_lo, out_hi, exponent = map(float, (value, in_lo, in_hi, out_lo, out_hi, exponent))

    if in_lo == in_hi:
        return out_lo
    if clipToRange:
        value = min(max(value, min(in_lo, in_hi)), max(in_lo, in_hi))

    t = (value - in_lo) / (in_hi - in_lo)
    if exponent != 1.0:
        t = math.copysign(abs(t) ** exponent, t)
    return out_lo + t * (out_hi - out_lo)


def scaleValues(values, in_lo, in_hi, out_lo, out_hi, exponent=1.0, clipToRange=True):
    values = list(values) if values is not None else []
    if not values:
        raise ValueError("scaleValues: values is empty")
    return [scale(v, in_lo, in_hi, out_lo, out_hi, exponent, clipToRange) for v in values]


def normaliseIntoRange(value, lo, hi, clipToRange=True):
    """Map value from [lo..hi] into [0..1] (warns if it lies outside); None if not a number."""
    if not is_number(value, lo, hi):
        return None
    if lo != hi and not min(lo, hi) <= value <= max(lo, hi):
        warnings.warn("Value out of bounds" + ("; clipping to 0..1" if clipToRange else ""), stacklevel=2)
    return scale(value, lo, hi, 0.0, 1.0, exponent=1.0, clipToRange=clipToRange)


def normaliseValuesIntoRange(values, lo, hi, clipToRange=True):
    """Map each item in values from [lo..hi] into [0..1]."""
    return scaleValues(values, lo, hi, 0.0, 1.0, exponent=1.0, clipToRange=clipToRange)


def normaliseValues(values):
    """Normalise any iterable of numbers into [0..1] using its own min/max."""
    if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
        raise ValueError("normaliseValues: Wrong Type! values is not iterable")
    values = list(values)
    if not values:
        raise ValueError("normaliseValues: values is empty")
    return normaliseValuesIntoRange(values, min(values), max(values), clipToRange=True)
