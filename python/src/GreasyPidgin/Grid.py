import random
from numbers import Real

# float noise (0.1 + 0.2 = 0.30000000000000004) is rounded away at this precision
_DECIMALS = 10


class Grid(set):
    """A grid is just a specialized set with optional helper methods.

    Note: set operations (|, &, -, copy()) return a plain set, not a Grid.
    """

    def __init__(self, values=None):
        super().__init__(() if values is None else values)
        self.latestSieveID = -1
        self.sieved = {}
        self.sampled = {}
        self.sampleID = -1

    def sorted(self):
        """Return grid values in sorted order."""
        return sorted(self)

    def quantise(self, value):
        """Snap a number (or each number in a list/tuple/set) to the nearest grid value.
        On a tie the lower grid value wins."""
        if isinstance(value, Real):
            return min(self, key=lambda x: (abs(x - value), x))
        if isinstance(value, (list, tuple, set)):
            return type(value)(self.quantise(v) for v in value)
        raise ValueError(f"Grid.quantise: Value {value} of type {type(value)} cannot be quantised!")

    def sieve(self, stepSize=1, offsetIndex=0, *, discardOffset=True,
              inverse=False, reverse=False, rotation=0):
        """Keep every stepSize-th value from offsetIndex on (Xenakis sieve).

        discardOffset : drop the values before offsetIndex (default) or keep them
        inverse       : keep the values the sieve would drop instead
        reverse       : sieve from the highest value downwards
        rotation      : shift the sieve's phase by this many positions

        The result is stored in self.sieved['sieved_<n>'] and also returned.
        """
        if stepSize < 1:
            raise ValueError(f"Grid.sieve: stepSize must be >= 1, got {stepSize}")
        values = sorted(self, reverse=reverse)
        head = [] if discardOffset else values[:offsetIndex]
        tail = values[offsetIndex:]
        if tail:
            r = rotation % len(tail)
            tail = tail[r:] + tail[:r]
        kept = [v for i, v in enumerate(tail) if (i % stepSize == 0) != inverse]

        self.latestSieveID += 1
        self.sieved[f"sieved_{self.latestSieveID}"] = {
            'sievedGrid': Grid(head + kept),
            'stepSize': stepSize,
            'offsetIndex': offsetIndex,
            'discardOffset': discardOffset,
            'inverse': inverse,
            'reverse': reverse,
            'rotation': rotation,
        }
        return self.sieved[f"sieved_{self.latestSieveID}"]['sievedGrid']

    def sample(self, numElements):
        """Pick numElements random values; stored in self.sampled['sampled_<n>'] and returned."""
        self.sampleID += 1
        self.sampled[f"sampled_{self.sampleID}"] = random.sample(self.sorted(), numElements)
        return self.sampled[f"sampled_{self.sampleID}"]

    # ------------------------------------------------------------------
    # Constructors (after SuperCollider's Array methods)
    # ------------------------------------------------------------------

    @staticmethod
    def _checkSize(size, minimum=0):
        if size < minimum:
            raise ValueError(f"size must be >= {minimum}")

    @classmethod
    def fill(cls, size: int, func_or_value):
        """`size` values: func_or_value(i) if callable, else the value repeated
        (a set, so a repeated value gives a Grid of length 1)."""
        cls._checkSize(size)
        f = func_or_value if callable(func_or_value) else (lambda _: func_or_value)
        return cls(f(i) for i in range(size))

    @classmethod
    def series(cls, start, step, size: int):
        """Arithmetic series: start, start + step, ... (`size` values)."""
        cls._checkSize(size)
        return cls(round(start + i * step, _DECIMALS) for i in range(size))

    @classmethod
    def geom(cls, start, ratio, size: int, *, decimals=None):
        """Geometric series: start * ratio**i (`size` values), optionally rounded."""
        cls._checkSize(size)
        values = (start * ratio ** i for i in range(size))
        return cls(values if decimals is None else (round(v, decimals) for v in values))

    @classmethod
    def linearInterpolation(cls, start, end, size: int, *, decimals=None, includeEnd=True):
        """`size` points evenly spaced from start to end (end excluded if includeEnd=False)."""
        cls._checkSize(size, 1)
        steps = max(size - 1, 1) if includeEnd else size
        decimals = _DECIMALS if decimals is None else decimals
        return cls(round(start + (end - start) * i / steps, decimals) for i in range(size))

    @classmethod
    def rand(cls, size: int, low=0.0, high=1.0, *, integer: bool = False):
        """`size` random values in [low, high]; distinct ints if integer=True."""
        cls._checkSize(size)
        if integer:
            return cls(random.sample(range(int(low), int(high) + 1), size))
        return cls(random.uniform(float(low), float(high)) for _ in range(size))

    @classmethod
    def fib(cls, size: int, a=0, b=1):
        """Fibonacci-style sequence of `size` values starting a, b (duplicates collapse)."""
        cls._checkSize(size)
        values = [a, b][:size]
        while len(values) < size:
            values.append(values[-1] + values[-2])
        return cls(values)

    def differentiate(self, copyFirst=False) -> list:
        """
        Deltas between consecutive sorted values. The first entry is 0, or the
        first value itself with copyFirst=True (SuperCollider's differentiate).

        >>> Grid([3, 7, 10, 15]).differentiate()
        [0, 4, 3, 5]
        """
        srt = self.sorted()
        if not srt:
            return []
        return [srt[0] if copyFirst else 0] + [b - a for a, b in zip(srt, srt[1:])]

    def __repr__(self):
        name = self.__class__.__name__
        if not self:
            return f"{name}(size=0)"
        srt = self.sorted()
        return f"{name}(size={len(srt)}, range=({srt[0]}, {srt[-1]}), preview={srt})"
