import random
import math
import numbers


class Grid(set):
    """A grid is just a specialized set with optional helper methods."""
    
    def __init__(self, values=None):
        # values can be None, iterable, or another set
        super().__init__(values if values is not None else [])
    
    def sorted(self):
        """Return grid values in sorted order."""
        return sorted(self)
    
    def check_types(self, expected_type=None):
        """
        If expected_type is given:
            → returns True if all elements are instances of expected_type.

        If expected_type is None:
            → returns True if all elements share the same type.
        """
        if not self:
            return True  # empty grid satisfies the condition

        # Case 1: explicit expected_type
        if expected_type is not None:
            return all(isinstance(x, expected_type) for x in self)

        # Case 2: no type given → check homogeneity
        it = iter(self)
        first_type = type(next(it))
        return all(isinstance(x, first_type) for x in it)
    
    def is_comparable(self, value) -> bool:
        """
        Check whether `value` is comparable to the elements of the Grid.
        A Grid may be empty (then value is considered not comparable).
        """
        if not self:
            return False
            raise ValueError("is_comparable: The grid is empty, there is nothing to compare!")

        # get one representative element
        sample = next(iter(self))

        # numbers should be compared to numbers
        if isinstance(sample, numbers.Number) and isinstance(value, numbers.Number):
            return True

        # fallback: try comparing manually
        try:
            sample < value
            value < sample
            return True
        except Exception:
            return False


    def quantise(self, value):
        """
        Return the closest element in the Grid to the given value.

        Steps:
          1. Check comparability
          2. Return the element with minimal absolute difference
        """
        if not self:
            raise ValueError("closest: Grid is empty — cannot find closest element.")

        if not self.is_comparable(value):
            raise TypeError(
                f"closest: Value {value!r} is not comparable with elements of the Grid."
            )

        # compute minimum by distance
        return min(self, key=lambda x: abs(x - value))
    
    
    

####################################################################################################
# fill  — like Array.fill (superCollider)

    @classmethod
    def fill(cls, size: int, func_or_value):
        """
        Create a Grid with `size` elements.

        If func_or_value is callable, it is called as func_or_value(i)
        for i in [0 .. size-1]. Otherwise the same value is repeated.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        if callable(func_or_value):
            data = (func_or_value(i) for i in range(size))
        else:
            data = (func_or_value for _ in range(size))

        return cls(data)

####################################################################################################
# series  — arithmetic progression  (superCollider)

    @classmethod
    def series(cls, start, step, size: int):
        """
        Arithmetic series: start, start+step, ... for `length` elements.
        """
        if size < 0:
            raise ValueError("length must be >= 0")

        data = (start + i * step for i in range(size))
        return cls(data)

####################################################################################################
# geom  — geometric progression  (superCollider)
    @classmethod
    def geom(cls, start, ratio, size: int):
        """
        Geometric series: start * ratio^i for `length` elements.

        Note: if ratio == 1, it's just a constant series.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        data = (start * (ratio ** i) for i in range(size))
        return cls(data)

####################################################################################################
# interpolation  — linear interpolation between endpoints (superCollider)

    @classmethod
    def interpolation(cls, start, end, size: int):
        """
        `length` points linearly spaced between `start` and `end`.

        If length == 1, returns {start}.
        """
        if size <= 0:
            raise ValueError("length must be > 0")
        if size == 1:
            return cls([start])

        step = (end - start) / (size - 1)
        data = (start + i * step for i in range(size))
        return cls(data)

####################################################################################################
# rand  — random values

    @classmethod
    def rand(cls, size: int, low=0.0, high=1.0, *, integer: bool = False):
        """
        `size` random values in [low, high].

        If integer=True, uses randint and returns ints.
        Otherwise uses uniform and returns floats.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        if integer:
            # randint is inclusive on both ends
            data = (random.randint(int(low), int(high)) for _ in range(size))
        else:
            data = (random.uniform(low, high) for _ in range(size))

        return cls(data)

####################################################################################################
# fib  — Fibonacci-like sequence

    @classmethod
    def fib(cls, size: int, a=0, b=1):
        """
        Fibonacci-style sequence of `length` elements.
        Start values are a, b.
        """
        if size < 0:
            raise ValueError("length must be >= 0")
        if size == 0:
            return cls()
        if size == 1:
            return cls([a])

        values = [a, b]
        for _ in range(size - 2):
            values.append(values[-1] + values[-2])

        return cls(values)