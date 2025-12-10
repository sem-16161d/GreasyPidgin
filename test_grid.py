import math
import numbers
import pytest

from .QuantisationGrid import Grid


# ------------------------------------------------------------
# Basic construction and behaviours
# ------------------------------------------------------------

def test_basic_construction():
    g = Grid([1, 2, 3])
    assert isinstance(g, Grid)
    assert set(g) == {1, 2, 3}


def test_sorted():
    g = Grid([5, 1, 3])
    assert g.sorted() == [1, 3, 5]


# ------------------------------------------------------------
# Type checking
# ------------------------------------------------------------

def test_check_types_with_expected_type():
    g = Grid([1, 2, 3])
    assert g.check_types(int) is True
    assert g.check_types(float) is False


def test_check_types_homogeneous():
    g = Grid([1, 2, 3])
    assert g.check_types() is True

    g2 = Grid([1, 2.0])
    assert g2.check_types() is False


def test_check_types_empty():
    g = Grid()
    assert g.check_types() is True
    assert g.check_types(int) is True


# ------------------------------------------------------------
# Comparability
# ------------------------------------------------------------

def test_is_comparable_numeric():
    g = Grid([1, 2, 3])
    assert g.is_comparable(2)
    assert g.is_comparable(2.5)
    assert not g.is_comparable("hello")


def test_is_comparable_empty():
    g = Grid()
    assert g.is_comparable(1) is False


def test_is_comparable_fallback_objects():
    class A:
        def __init__(self, x): self.x = x
        def __lt__(self, other): return self.x < other.x

    g = Grid([A(1), A(2), A(3)])
    assert g.is_comparable(A(2)) is True


# ------------------------------------------------------------
# Closest element
# ------------------------------------------------------------

def test_closest_numeric():
    g = Grid([0, 5, 10])
    assert g.quantise(6) == 5
    assert g.quantise(9.9) == 10


def test_closest_type_error():
    g = Grid([1, 5, 10])
    with pytest.raises(TypeError):
        g.quantise("hello")


def test_closest_empty():
    g = Grid()
    with pytest.raises(ValueError):
        g.quantise(10)


# ------------------------------------------------------------
# Constructor methods
# ------------------------------------------------------------

def test_fill_constant():
    g = Grid.fill(4, 7)
    assert isinstance(g, Grid)
    assert len(g) == 1  # set collapses duplicates
    assert list(g)[0] == 7


def test_fill_function():
    g = Grid.fill(5, lambda i: i * 2)
    assert set(g) == {0, 2, 4, 6, 8}


def test_series():
    g = Grid.series(start=0, step=2, size=5)
    assert g.sorted() == [0, 2, 4, 6, 8]


def test_geom():
    g = Grid.geom(start=1, ratio=2,size=4)
    # geometric progression: 1, 2, 4, 8
    assert g.sorted() == [1, 2, 4, 8]


def test_interpolation():
    g = Grid.interpolation(0, 10, size=6)
    # linspace-like: 0, 2, 4, 6, 8, 10
    assert g.sorted() == [0, 2, 4, 6, 8, 10]


def test_rand_deterministic_length():
    g = Grid.rand(size=10, low=0, high=1)
    assert len(g) <= 10  # because it is a set


def test_fib():
    g = Grid.fib(size=7)
    # Fibonacci: 0, 1, 1, 2, 3, 5, 8 → set removes the duplicate 1
    assert set(g) == {0, 1, 2, 3, 5, 8}
    assert max(g) == 8