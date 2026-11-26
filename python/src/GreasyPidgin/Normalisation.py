# Normalisation.py
from numpy import clip
import warnings


def is_number(*args):
    return all(x is not None and isinstance(x, (int, float)) for x in args)

# Max/MSP-like scale()  (linear if exponent=1.0)
def scale(value, in_lo, in_hi, out_lo, out_hi, exponent=1.0, clipToRange=False):
    if not is_number(value, in_lo, in_hi, out_lo, out_hi, exponent):
        raise TypeError("scale: all arguments must be numbers")

    value = float(value)
    in_lo = float(in_lo)
    in_hi = float(in_hi)
    out_lo = float(out_lo)
    out_hi = float(out_hi)
    exponent = float(exponent)

    if in_lo == in_hi:
        return out_lo

    # allow reversed input range
    if in_lo > in_hi:
        in_lo, in_hi = in_hi, in_lo

    if clipToRange:
        value = float(clip(value, in_lo, in_hi))

    # normalize to 0..1
    t = (value - in_lo) / (in_hi - in_lo)

    # exponent curve
    if exponent != 1.0:
        t = t ** exponent

    return out_lo + t * (out_hi - out_lo)

def scaleValues(values, in_lo, in_hi, out_lo, out_hi, exponent=1.0, clipToRange=True):
    if values is None or len(values) == 0:
        raise ValueError("scaleValues: values is empty")
    return [
        scale(v, in_lo, in_hi, out_lo, out_hi, exponent, clipToRange)
        for v in values
    ]

def normaliseIntoRange(value, lo, hi, clipToRange=True):
    """
    Returns value mapped into [0..1] given input range [lo..hi].
    """
    if not is_number(value, lo, hi):
        return None

    # keep your warning behavior
    v = float(value)
    lo = float(lo)
    hi = float(hi)

    if lo != hi:
        out_of_bounds = (v < min(lo, hi)) or (v > max(lo, hi))
        if out_of_bounds:
            warnings.warn("Value out of bounds")
            if clipToRange:
                warnings.warn("Clipping to 0,1")

    return scale(v, lo, hi, 0.0, 1.0, exponent=1.0, clipToRange=clipToRange)

def normaliseValuesIntoRange(values, lo, hi, clipToRange=True):
    """
    Maps each item in values from [lo..hi] into [0..1].
    """
    return scaleValues(values, lo, hi, 0.0, 1.0, exponent=1.0, clipToRange=clipToRange)

def normaliseValues(values):
    """
    Normalise iterable into [0..1] using its own min/max.
    """
    if not isinstance(values, (list, tuple, set)):
        raise ValueError("normaliseValues: Wrong Type! values is not iterable")
    if values is None or len(values) == 0:
        raise ValueError("normaliseValues: values is empty")

    lo = min(values)
    hi = max(values)
    return normaliseValuesIntoRange(values, lo, hi, clipToRange=True)