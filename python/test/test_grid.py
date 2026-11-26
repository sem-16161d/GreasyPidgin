import numpy as np
import pytest

from GreasyPidgin.Grid import Grid


def test_series_keeps_tiny_steps():
    assert len(Grid.series(0, 1e-7, 5)) == 5


def test_linear_interpolation_rounds_float_noise():
    assert Grid.linearInterpolation(0, 0.3, 4).sorted() == [0.0, 0.1, 0.2, 0.3]


def test_quantise_accepts_numpy_and_breaks_ties_low():
    assert Grid([0, 1]).quantise(np.int64(1)) == 1
    assert Grid([1.0, 0.0]).quantise(0.5) == 0.0


def test_rand_integer_is_inclusive_and_integer():
    g = Grid.rand(4, 0.5, 3, integer=True)
    assert g == {0, 1, 2, 3}
    assert all(isinstance(v, int) for v in g)


def test_differentiate_empty():
    assert Grid().differentiate() == []
    assert Grid().differentiate(copyFirst=True) == []


def test_sieve_returns_and_stores():
    g = Grid.series(0, 1, 20)
    out = g.sieve(stepSize=3, offsetIndex=5)
    assert out == {5, 8, 11, 14, 17} == g.sieved["sieved_0"]["sievedGrid"]


def test_sieve_rotation_wraps():
    g = Grid.series(0, 1, 20)
    assert g.sieve(3, 1, rotation=25) == g.sieve(3, 1, rotation=6)


def test_sieve_rejects_zero_step():
    with pytest.raises(ValueError):
        Grid([1, 2]).sieve(stepSize=0)
