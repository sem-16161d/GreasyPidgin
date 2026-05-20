import random
import numbers
from signal import siginterrupt


class Grid(set):
    """A grid is just a specialized set with optional helper methods."""
    
    def __init__(self, values=None):
        # values can be None, iterable, or another set
        super().__init__(values if values is not None else [])
        self.latestSieveID = -1
        self.sieved = dict()
        self.sampled = {}
        self.sampleID = -1
    
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
    


    def quantise(self, value):
        
        if isinstance(value, (float, int)):
            quantised = min(self, key=lambda x: abs(x - value))
        elif isinstance(value, list):
            quantised = [self.quantise(v) for v in value]
        elif isinstance(value, tuple):
            quantised = tuple([self.quantise(v) for v in value])
        elif isinstance(value, set):
            quantised = set([self.quantise(v) for v in value])
        else:
            raise ValueError(f"Grid.quantise: Value {value} of type {type(value)} cannot be quantised!")

        # compute minimum by distance
        return quantised
    
    def rotateList(self,lst, rotation):
        return lst[rotation:] + lst[:rotation]


    def sieve(
        self, 
        stepSize = 1, 
        offsetIndex = 0, 
        *,
        discardOffset = True, 
        inverse = False, 
        reverse = False,
        rotation = 0):
        list = self.sorted()
        boolIterator = []
        if reverse:
            list = list[::-1]
        for i in range(stepSize):
            newBool = False
            if i == 0:
                newBool = True
            if inverse:
                newBool = not newBool
            boolIterator.append(newBool)
        out = list[:offsetIndex]
        if discardOffset:
            out = []
        iterList = self.rotateList(list[offsetIndex:], rotation)
        for i,elem in enumerate(iterList):
            if len(boolIterator) == 0:
                return []
            if boolIterator[i%len(boolIterator)]:
                out.append(elem)
        

        
        # out = self.rotateList(out,rotation)
        self.latestSieveID += 1
        self.sieved["sieved_"+ str(self.latestSieveID)] = {
            'sievedGrid': Grid(out),
            'stepSize': stepSize,
            'offsetIndex': offsetIndex,
            'discardOffset': discardOffset,
            'inverse':inverse,
            'reverse': reverse,
            'rotation': rotation
        }
        
    def sample(self, numElements):
        sampled = random.sample(self.sorted(), numElements)
        self.sampleID += 1
        self.sampled['sampled_'+str(self.sampleID)] = sampled
    
####################################################################################################
# helper functions
# get decimal places on an integer
    @staticmethod
    def _decimal_places(x):
        """
        Return number of decimal places in a number
        based on its string representation.
        """
        s = format(x, "f")  # avoids scientific notation
        if "." in s:
            return len(s.rstrip("0").split(".")[1])
        return 0
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
        if size < 0:
            raise ValueError("size must be >= 0")

        # detect required precision
        decimals = max(
            cls._decimal_places(start),
            cls._decimal_places(step),
        )

        data = (
            round(start + i * step, decimals)
            for i in range(size)
        )

        return cls(data)

####################################################################################################
# geom  — geometric progression  (superCollider)
    @classmethod
    def geom(cls, start, ratio, size: int, *, decimals = 100):
        """
        Geometric series: start * ratio^i for `length` elements.

        Note: if ratio == 1, it's just a constant series.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        data = (start * (ratio ** i) for i in range(size))
        if decimals < 100:
            data = (round(start * (ratio ** i), decimals) for i in range(size))
        return cls(data)

####################################################################################################
# interpolation  — linear interpolation between endpoints (superCollider)

    @classmethod
    def linearInterpolation(cls, start, end, size: int, *,decimals = 100, includeEnd = True):
        """
        `length` points linearly spaced between `start` and `end`.

        If length == 1, returns {start}.
        """
        if size <= 0:
            raise ValueError("length must be > 0")
        if size == 1:
            return cls([start])
        if includeEnd:
            step = (end - start) / (size - 1)
        else:
            step= (end - start) / (size)
        data = (start + i * step for i in range(size))
        if decimals < 100:
            data = (round(start + i * step, decimals) for i in range(size))
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
            rangeHiLow = int(int(high)-int(low))
            data = random.sample([ i+low for i in range(rangeHiLow)], size)
        else:
            data = (random.uniform(float(low), float(high)) for _ in range(size))

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

    def differentiate(self, copyFirst = False) -> list:
        """
        Return the deltas between consecutive sorted elements.
        by default it assume the first elem to be 0 (delta of first element with itself)
        to use the original SuperCollider-differentiate behaviours, set copyFirst = True

        Example
        -------
        >>> Grid([3, 7, 10, 15]).differentiate()
        [0, 4, 3, 5]
        """
        srt    = self.sorted()
        if copyFirst:
            result = [srt[0]]
        else:
            result = [0]
        for i in range(1, len(srt)):
            result.append(srt[i] - srt[i - 1])
        return result

    def __repr__(self):
        size = len(self)
        if size == 0:
            return f"{self.__class__.__name__}(size=0)"

        try:
            vmin = min(self)
            vmax = max(self)
        except Exception:
            vmin = "?"
            vmax = "?"

        return (
            f"{self.__class__.__name__}("
            f"size={size}, "
            f"range=({vmin}, {vmax}), "
            f"preview={sorted(self)})"
        )