"""
TimeGrid.py

A TimeGrid is a Grid (set) of time positions in seconds, with tempo
context (bpm, ticksPerBeat) and optional named sublayers.

Constructors
------------
TimeGrid(values, *, startTimeSec, endTimeSec, bpm, ticksPerBeat)
TimeGrid.series(startTimeSec, stepSec, size, ...)
TimeGrid.linearInterpolation(startTimeSec, endTimeSec, size, ...)
TimeGrid.fromSubdivisions(subdivisions, *, bpm, startTimeBeats, durationBeats, ...)
TimeGrid.fromRQQ(rqq, *, startTimeSec, bpm, ticksPerBeat)
TimeGrid.fromDensity(density, steps, durationBeats, ...)
TimeGrid.fromDensityHz(density, *, steps, durationBeats, ...)

Export
------
tg.toMidi(path, name, allLayers)   — one note per grid point
tg.parseMidi(...)                  — legacy alias

Analysis
--------
tg.toRelativeTimes(unit)
tg.getDensityCurve(lookbackInterval, lookBackFrame, *, lookBackUnit)
tg.getSelfSimilarity(maxVal)
tg.analyseExternalStartTimesSec(starts)
"""

from random import randint, random
from math import ceil
from GreasyPidgin.LSystem import LSystem, ProductionRules, ProductionRule

from GreasyPidgin.Grid import Grid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def beatToSec(beat: float, bpm: float = 60.0) -> float:
    return float(beat) * 60.0 / float(bpm)

def secToBeat(sec: float, bpm: float = 60.0) -> float:
    return float(sec) * float(bpm) / 60.0


# ---------------------------------------------------------------------------
# Rest and RQQ
# ---------------------------------------------------------------------------

class Rest(float):
    """A duration that contributes to timing but produces no note."""
    def __new__(cls, f):
        return super().__new__(cls, f)

R = Rest


def _flattenRQQ(rqqRatios) -> list:
    flat = []
    if isinstance(rqqRatios, (int, float)):
        flat.append(rqqRatios)
    elif isinstance(rqqRatios, (tuple, list)):
        for r in rqqRatios:
            flat += _flattenRQQ(r)
    elif isinstance(rqqRatios, RQQ):
        flat += _flattenRQQ(rqqRatios.rawdividedDurations)
    return flat


class RQQ:
    """
    Rhythm Quantisation Quotient — a hierarchical rhythm notation.

    Divides a duration into proportional parts. Nested RQQs create
    sub-divisions. Rest() values skip a slot (no note-onset there).

    Parameters
    ----------
    durationBeats : float
        Total duration in beats.
    ratios : list | tuple
        Proportional divisions, optionally nested or containing Rest().
    bpm : float
    startOffsetBeats : float

    Example
    -------
    >>> RQQ(4, [1, 1, Rest(1), 2])          # 4 beats: quarter, quarter, rest, half
    >>> RQQ(4, [1, RQQ(1, [1,1,1]), 1, 1]) # triplet subdivision in beat 2
    """

    def __init__(
        self,
        durationBeats: float,
        ratios: list | tuple,
        *,
        bpm: float = 60.0,
        startOffsetBeats: float = 0.0,
    ) -> None:
        self.durationBeats    = float(durationBeats)
        self.ratios           = _flattenRQQ(ratios)
        self.bpm              = float(bpm)
        self.startOffsetBeats = float(startOffsetBeats)
        self.rawdividedDurations: list = []
        self.startsBeats:         list = []
        self._divideDurationRaw()
        self._getStartsBeats()

    def _divideDurationRaw(self) -> None:
        total = sum(self.ratios)
        self.rawdividedDurations = []
        for r in self.ratios:
            dur = r / total * self.durationBeats
            self.rawdividedDurations.append(Rest(dur) if isinstance(r, Rest) else dur)

    def _getStartsBeats(self) -> None:
        self._divideDurationRaw()
        self.startsBeats = [self.startOffsetBeats]
        for dur in self.rawdividedDurations[:-1]:
            if isinstance(dur, Rest):
                self.startsBeats[-1] = self.startsBeats[-1] + float(dur)
            else:
                self.startsBeats.append(self.startsBeats[-1] + dur)

    def __repr__(self) -> str:
        return (
            f"RQQ\n"
            f"  durationBeats    : {self.durationBeats}\n"
            f"  subdivisions     : {self.ratios}\n"
            f"  bpm              : {self.bpm}\n"
            f"  startOffsetBeats : {self.startOffsetBeats}\n"
            f"  startsBeats      : {self.startsBeats}\n"
        )


# ---------------------------------------------------------------------------
# TimeGrid
# ---------------------------------------------------------------------------

class TimeGrid(Grid):
    """
    A set of time positions in seconds, with tempo context.

    The grid values are always seconds. Beat-domain mirrors are computed
    automatically from bpm.

    Parameters
    ----------
    values : iterable | None
        Time positions in seconds.
    startTimeSec : float
    endTimeSec : float | None
        If None, inferred as last + (last - second_to_last) step.
    bpm : float
    ticksPerBeat : int
    """

    def __init__(
        self,
        values=None,
        *,
        startTimeSec: float = 0.0,
        endTimeSec: float | None = None,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> None:
        super().__init__(values if values is not None else [])

        self.bpm          = float(bpm)
        self.ticksPerBeat = int(ticksPerBeat)
        self.layers:      dict = {}
        self.densityCurve: dict = {}
        self.startTimeSec  = float(startTimeSec)
        self.startTimeBeats = secToBeat(self.startTimeSec, self.bpm)

        srt = self.sorted()
        if srt:
            if endTimeSec is not None:
                self.endTimeSec = float(endTimeSec)
            elif len(srt) >= 2:
                self.endTimeSec = 2 * srt[-1] - srt[-2]
            else:
                self.endTimeSec = srt[-1]
        else:
            self.endTimeSec = float(endTimeSec) if endTimeSec is not None else 0.0

        self.durationSec    = self.endTimeSec - self.startTimeSec
        self.durationBeats  = secToBeat(self.durationSec, self.bpm)
        self.endTimeBeats   = secToBeat(self.endTimeSec,  self.bpm)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    def sample(self, numElements: int) -> "TimeGrid":
        import random as _random
        sampled = _random.sample(self.sorted(), numElements)
        return TimeGrid(sampled, bpm=self.bpm, ticksPerBeat=self.ticksPerBeat)

    @classmethod
    def series(
        cls,
        startTimeSec: float,
        stepSec: float,
        size: int,
        *,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """Arithmetic series of time positions."""
        base = Grid.series(startTimeSec, stepSec, size)
        tg = cls(
            base,
            startTimeSec=startTimeSec,
            endTimeSec=startTimeSec + size * stepSec,
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )
        return tg

    @classmethod
    def linearInterpolation(
        cls,
        startTimeSec: float,
        endTimeSec: float,
        size: int,
        *,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
        decimals: int = 4,
        includeEnd: bool = True,
    ) -> "TimeGrid":
        """Linearly spaced time positions between startTimeSec and endTimeSec."""
        base = Grid.linearInterpolation(
            startTimeSec, endTimeSec, size,
            decimals=decimals, includeEnd=includeEnd,
        )
        tg = cls(
            base,
            startTimeSec=startTimeSec,
            endTimeSec=endTimeSec,
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )
        return tg

    @classmethod
    def fromSubdivisions(
        cls,
        subdivisions: list | None = None,
        *,
        bpm: float = 60.0,
        startTimeBeats: float = 0.0,
        durationBeats: float,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """
        Build a TimeGrid from multiple simultaneous beat subdivisions.

        Each subdivision creates a sublayer; all are merged into the main grid.

        Parameters
        ----------
        subdivisions : list[int | float] | None
            List of subdivision values, e.g. [1, 2, 3] for quarter, eighth,
            and triplet subdivisions simultaneously.
        durationBeats : float
            Total duration in beats.

        Example
        -------
        >>> TimeGrid.fromSubdivisions([1, 2, 3], bpm=120, durationBeats=4)
        """
        if subdivisions is None:
            subdivisions = [1]

        allValues: set = set()
        subGrids:  dict = {}

        for sd in subdivisions:
            key      = f"/ {sd}"
            nSteps   = int(durationBeats * sd)
            stepSec  = beatToSec(1 / sd, bpm)
            startSec = beatToSec(startTimeBeats, bpm)
            layer    = TimeGrid.series(
                startSec, stepSec, nSteps,
                bpm=bpm, ticksPerBeat=ticksPerBeat,
            )
            allValues = allValues.union(layer)
            subGrids[key] = layer

        tg = cls(
            allValues,
            startTimeSec=beatToSec(startTimeBeats, bpm),
            endTimeSec=beatToSec(startTimeBeats + durationBeats, bpm),
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )
        tg.layers = subGrids
        return tg

    @classmethod
    def fromRQQ(
        cls,
        rqq: RQQ,
        *,
        startTimeSec: float = 0.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """Build a TimeGrid from an RQQ rhythm pattern."""
        rqq.bpm              = bpm
        rqq.startOffsetBeats = secToBeat(startTimeSec, bpm)
        rqq._getStartsBeats()
        values = [beatToSec(b, bpm) for b in rqq.startsBeats]
        return cls(
            values=values,
            startTimeSec=startTimeSec,
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )

    @classmethod
    def RQQfromLSystem(
        cls,
        rqqs: list,
        productionRules: list,
        numIterations: int = 5,
        *,
        axiom: list | None = None,
        startTimeSec: float = 0.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
        durationsCutoffBeats: float | None = None,
        cutoffMode: str = 'start',
    ) -> "TimeGrid":
        """
        Build a TimeGrid from an integer L-System, translating the final
        generation into RQQ objects via an index palette.

        The L-System works entirely with integers (clean, fast, hashable).
        After iteration, each integer is mapped to the corresponding RQQ
        in *rqqs* by index.

        Parameters
        ----------
        rqqs : list[RQQ]
            Palette of RQQ objects. Index 0 = rqqs[0], etc.
        productionRules : list[list]
            Index-based rules: [[predecessor, [successor0, successor1, ...]], ...]
            e.g. [[0, [0,1]], [1, [2,1,2]], [2, [0]]]
        numIterations : int
            Number of L-System iterations.
        axiom : list[int] | None
            Starting symbol sequence. None = [0].
        startTimeSec : float
        bpm : float
        ticksPerBeat : int
        durationsCutoffBeats : float | None
            If set, only this many beats of the sequence are kept.
        cutoffMode : str
            'start'  — first N beats (default)
            'end'    — last N beats
            'middle' — middle N beats

        Example
        -------
        >>> r1 = RQQ(0.5, [1, 1])
        >>> r2 = RQQ(1,   [1, 1, 1])
        >>> r3 = RQQ(1.5, [1, 1, 1, 1])
        >>> tg = TimeGrid.RQQfromLSystem(
        ...     rqqs            = [r1, r2, r3],
        ...     productionRules = [[0, [0,1]], [1, [2,1,2]], [2, [0]]],
        ...     numIterations   = 5,
        ...     axiom           = [0],
        ...     bpm             = 90,
        ...     durationsCutoffBeats = 16,
        ...     cutoffMode      = 'end',
        ... )
        """
        from GreasyPidgin.LSystem import LSystem, ProductionRules, ProductionRule

        # build integer L-System
        intRules = ProductionRules([
            ProductionRule(predIdx, succIndices)
            for predIdx, succIndices in productionRules
        ])
        intAxiom = axiom if axiom is not None else [0]
        lind     = LSystem(intAxiom, intRules)
        lind.iterate(numIterations)

        # translate integer generation → RQQ sequence
        generation   = lind.currentGeneration()
        print('currentGen: ', generation)
        rqqSequence  = [rqqs[i] for i in generation if 0 <= i < len(rqqs)]

        if not rqqSequence:
            return cls([], startTimeSec=startTimeSec, bpm=bpm,
                       ticksPerBeat=ticksPerBeat)

        # join into one RQQ and build TimeGrid
        durationBeats = sum(rqq.durationBeats for rqq in rqqSequence)
        rJoined       = RQQ(durationBeats, rqqSequence)
        print(rJoined.ratios[0])
        tg            = cls.fromRQQ(
            rJoined,
            startTimeSec = startTimeSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )

        # apply cutoff window
        if durationsCutoffBeats is not None:
            allOnsets  = tg.sorted()
            windowSec  = beatToSec(durationsCutoffBeats, bpm)
            totalSec   = beatToSec(durationBeats, bpm)

            if cutoffMode == 'end':
                windowStart = startTimeSec + max(0.0, totalSec - windowSec)
            elif cutoffMode == 'middle':
                windowStart = startTimeSec + max(0.0, (totalSec - windowSec) / 2)
            else:  # 'start'
                windowStart = startTimeSec

            windowEnd = windowStart + windowSec
            offset    = windowStart - startTimeSec
            filtered  = [t - offset for t in allOnsets
                         if windowStart - 1e-9 <= t < windowEnd]

            tg = cls(
                filtered,
                startTimeSec = startTimeSec,
                endTimeSec   = startTimeSec + windowSec,
                bpm          = bpm,
                ticksPerBeat = ticksPerBeat,
            )

        return tg
        """
        Build a TimeGrid from an L-System whose symbols are RQQ objects,
        using index-based production rules for ergonomic rule definition.

        Parameters
        ----------
        rqqs : list[RQQ]
            The palette of RQQ objects, indexed from 0.
        productionRules : list[list]
            Index-based rules as nested lists:
            [[predecessorIdx, [successorIdx0, successorIdx1, ...]], ...]
            e.g. [[0, [0,1]], [1, [0,1,2]]]
        numIterations : int
            Number of L-System iterations.
        startTimeSec : float
        bpm : float
        ticksPerBeat : int
        durationsCutoffBeats : float | None
            If set, only this many beats of the sequence are kept.
            None = full sequence.
        cutoffMode : str
            Where to take the window from when durationsCutoffBeats is set:
            'start'  — first N beats (default)
            'end'    — last N beats
            'middle' — middle N beats

        Example
        -------
        >>> tg = TimeGrid.RQQfromLSystem(
        ...     rqqs            = [r1, r2, r3],
        ...     productionRules = [[0, [0,1]], [1, [2,1,2]], [2, [0]]],
        ...     numIterations   = 5,
        ...     bpm             = 90,
        ...     durationsCutoffBeats = 16,
        ...     cutoffMode      = 'end',
        ... )
        """
        

        # build ProductionRules from index-based nested list
        rules = ProductionRules([
            ProductionRule(
                rqqs[predIdx],
                [rqqs[succIdx] for succIdx in succIndices]
            )
            for predIdx, succIndices in productionRules
        ])

        axiom = [rqqs[0]]
        lind  = LSystem(axiom, rules)
        lind.iterate(numIterations)

        # join generation into one RQQ
        generation    = lind.currentGeneration()
        durationBeats = sum(rqq.durationBeats for rqq in generation)
        rJoined       = RQQ(durationBeats, generation)

        # build full TimeGrid
        tg = cls.fromRQQ(
            rJoined,
            startTimeSec = startTimeSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )

        # apply cutoff window
        if durationsCutoffBeats is not None:
            allOnsets    = tg.sorted()
            windowSec    = beatToSec(durationsCutoffBeats, bpm)
            totalSec     = beatToSec(durationBeats, bpm)

            if cutoffMode == 'end':
                windowStart = startTimeSec + totalSec - windowSec
            elif cutoffMode == 'middle':
                windowStart = startTimeSec + (totalSec - windowSec) / 2
            else:  # 'start'
                windowStart = startTimeSec

            windowEnd = windowStart + windowSec
            filtered  = [t for t in allOnsets if windowStart - 1e-9 <= t < windowEnd]
            # re-zero onset times to startTimeSec
            offset    = windowStart - startTimeSec
            filtered  = [t - offset for t in filtered]

            tg = cls(
                filtered,
                startTimeSec = startTimeSec,
                endTimeSec   = startTimeSec + windowSec,
                bpm          = bpm,
                ticksPerBeat = ticksPerBeat,
            )

        return tg

    
    @classmethod
    def fromEuclidean(
        cls,
        pulses: int,
        steps: int,
        rotation: int = 0,
        *,
        durationBeats: float | None = None,
        durationSec: float | None = None,
        startTimeSec: float = 0.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """
        Build a TimeGrid from a Euclidean rhythm (Bjorklund algorithm).

        Distributes *pulses* as evenly as possible across *steps* positions.
        Classic examples: E(3,8) = [1,0,0,1,0,0,1,0] (tresillo),
                          E(5,8) = [1,0,1,1,0,1,1,0] (cinquillo).

        Parameters
        ----------
        pulses : int
            Number of onsets (active steps).
        steps : int
            Total number of grid positions.
        rotation : int
            Rotate the pattern left by this many steps. Default 0.
        durationBeats : float | None
            Total duration in beats. If both None, defaults to steps beats.
        durationSec : float | None
            Total duration in seconds. Takes precedence over durationBeats
            if both are given.
        startTimeSec : float
        bpm : float
        ticksPerBeat : int

        Examples
        --------
        >>> TimeGrid.fromEuclidean(3, 8, durationBeats=2.0, bpm=120)
        >>> TimeGrid.fromEuclidean(5, 8, rotation=2, durationBeats=4.0, bpm=90)
        """
        if pulses < 0 or steps <= 0:
            raise ValueError(
                f"TimeGrid.fromEuclidean: need steps > 0 and pulses >= 0, "
                f"got pulses={pulses}, steps={steps}"
            )
        # clamp pulses to available steps
        pulses = min(pulses, steps)

        # --- Bjorklund / Euclidean algorithm ---
        # Build the pattern as a list of 1s and 0s
        if pulses == 0:
            pattern = [0] * steps
        elif pulses == steps:
            pattern = [1] * steps
        else:
            # Bjorklund algorithm via Euclidean string construction
            # Represent as two groups: ones and zeros, then recursively
            # interleave until remainder has length <= 1
            ones  = [[1]] * pulses
            zeros = [[0]] * (steps - pulses)

            while len(zeros) > 1:
                # pair each zero with a one
                nPairs  = min(len(ones), len(zeros))
                paired  = [ones[i] + zeros[i] for i in range(nPairs)]
                remainder = ones[nPairs:] if len(ones) > len(zeros) else zeros[nPairs:]
                ones  = paired
                zeros = remainder
                if not zeros:
                    break

            # flatten
            pattern = []
            for group in ones + zeros:
                pattern += group

        # apply rotation (left shift)
        rotation = rotation % len(pattern) if pattern else 0
        pattern  = pattern[rotation:] + pattern[:rotation]

        # --- convert to onset times ---
        if durationSec is not None:
            totalSec  = float(durationSec)
        elif durationBeats is not None:
            totalSec  = beatToSec(float(durationBeats), bpm)
        else:
            totalSec  = beatToSec(float(len(pattern)), bpm)

        stepSec = totalSec / len(pattern)
        onsets  = [
            startTimeSec + i * stepSec
            for i, v in enumerate(pattern) if v == 1
        ]

        endTimeSec = startTimeSec + totalSec
        return cls(
            onsets,
            startTimeSec = startTimeSec,
            endTimeSec   = endTimeSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )

    @classmethod
    def fromPulsesEuclidean(
        cls,
        pulses: int,
        subdivisions: list = [1, 2, 4],
        rotation: int = 0,
        *,
        durationBeats: float | None = None,
        durationSec: float | None = None,
        startTimeSec: float = 0.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """
        Build a Euclidean rhythm from a number of pulses and a subdivision list.

        Like fromDensityEuclidean but takes pulses directly instead of Hz.
        Pulses are clamped to the number of available grid positions.

        Parameters
        ----------
        pulses : int
            Number of onsets to distribute across the grid.
        subdivisions : list
            Beat subdivisions defining the grid, e.g. [1, 2, 4].
        rotation : int
            Rotate the pattern left by this many steps.
        durationBeats : float | None
        durationSec : float | None
        startTimeSec : float
        bpm : float
        ticksPerBeat : int

        Examples
        --------
        >>> # 7 pulses on a triplet grid over 8 beats
        >>> TimeGrid.fromPulsesEuclidean(7, [3], 0, durationBeats=8.0, bpm=126.0)

        >>> # 5 pulses on a mixed grid, rotated by 2
        >>> TimeGrid.fromPulsesEuclidean(5, [1,2,4], 2, durationBeats=4.0, bpm=120)
        """
        # resolve duration
        if durationSec is not None:
            totalSec = float(durationSec)
        elif durationBeats is not None:
            totalSec = beatToSec(float(durationBeats), bpm)
        else:
            totalSec = beatToSec(4.0, bpm)

        # build actual grid positions in seconds
        startBeats     = secToBeat(startTimeSec, bpm)
        durationBeats_ = secToBeat(totalSec, bpm)
        _EPS           = 1e-9
        seen: set[float] = set()
        for sd in subdivisions:
            nSteps = int(round(durationBeats_ * sd))
            for i in range(nSteps + 1):
                tBeat = startBeats + i / sd
                tSec  = round(beatToSec(tBeat, bpm), 8)
                if startTimeSec - _EPS <= tSec < startTimeSec + totalSec - _EPS:
                    seen.add(tSec)

        gridTimes = sorted(seen)
        steps     = len(gridTimes)

        if steps == 0:
            return cls([], startTimeSec=startTimeSec, bpm=bpm,
                       ticksPerBeat=ticksPerBeat)

        # clamp pulses to available steps
        pulses = max(0, min(int(pulses), steps))

        # Euclidean pattern
        if pulses == 0:
            pattern = [0] * steps
        elif pulses == steps:
            pattern = [1] * steps
        else:
            ones  = [[1]] * pulses
            zeros = [[0]] * (steps - pulses)
            while len(zeros) > 1:
                nPairs    = min(len(ones), len(zeros))
                paired    = [ones[i] + zeros[i] for i in range(nPairs)]
                remainder = ones[nPairs:] if len(ones) > len(zeros) else zeros[nPairs:]
                ones      = paired
                zeros     = remainder
                if not zeros:
                    break
            pattern = []
            for group in ones + zeros:
                pattern += group

        # apply rotation
        rotation = rotation % len(pattern) if pattern else 0
        pattern  = pattern[rotation:] + pattern[:rotation]

        onsets = [gridTimes[i] for i, v in enumerate(pattern) if v == 1]

        return cls(
            onsets,
            startTimeSec = startTimeSec,
            endTimeSec   = startTimeSec + totalSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )

    @classmethod
    def fromDensityEuclidean(
        cls,
        densityHz: float = 4.0,
        subdivisions: list = [1, 2, 4],
        rotation: int = 0,
        *,
        durationBeats: float | None = None,
        durationSec: float | None = None,
        startTimeSec: float = 0.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> "TimeGrid":
        """
        Build a Euclidean rhythm from a density in Hz and a subdivision list.

        The subdivision list defines the grid (steps). The number of pulses
        is derived from densityHz * durationSec, rounded to the nearest integer
        and clamped to [0, steps].

        Parameters
        ----------
        densityHz : float
            Expected events per second.
        subdivisions : list
            Beat subdivisions defining the grid, e.g. [1, 2, 4].
            The union of all subdivision positions becomes the step pool.
        rotation : int
            Rotate the Euclidean pattern left by this many steps.
        durationBeats : float | None
        durationSec : float | None
        startTimeSec : float
        bpm : float
        ticksPerBeat : int

        Examples
        --------
        >>> # triplet grid, ~10 events/sec over 8 beats
        >>> TimeGrid.fromDensityEuclidean(10, [3], 8, bpm=126.0)
        >>> # mixed grid
        >>> TimeGrid.fromDensityEuclidean(4.0, [1,2,4], durationBeats=2.0, bpm=120)
        """
        # resolve duration
        if durationSec is not None:
            totalSec = float(durationSec)
        elif durationBeats is not None:
            totalSec = beatToSec(float(durationBeats), bpm)
        else:
            totalSec = beatToSec(4.0, bpm)

        # build the actual grid positions in seconds (sorted, deduplicated)
        startBeats     = secToBeat(startTimeSec, bpm)
        durationBeats_ = secToBeat(totalSec, bpm)
        _EPS           = 1e-9
        seen: set[float] = set()
        for sd in subdivisions:
            nSteps = int(round(durationBeats_ * sd))
            for i in range(nSteps + 1):
                tBeat = startBeats + i / sd
                tSec  = round(beatToSec(tBeat, bpm), 8)
                if startTimeSec - _EPS <= tSec < startTimeSec + totalSec - _EPS:
                    seen.add(tSec)

        gridTimes = sorted(seen)
        steps     = len(gridTimes)

        if steps == 0:
            return cls([], startTimeSec=startTimeSec, bpm=bpm,
                       ticksPerBeat=ticksPerBeat)

        # derive pulses from densityHz — clamp to [0, steps]
        pulses = int(round(densityHz * totalSec))
        pulses = max(0, min(pulses, steps))

        # build Euclidean binary pattern
        if pulses == 0:
            pattern = [0] * steps
        elif pulses == steps:
            pattern = [1] * steps
        else:
            ones  = [[1]] * pulses
            zeros = [[0]] * (steps - pulses)
            while len(zeros) > 1:
                nPairs    = min(len(ones), len(zeros))
                paired    = [ones[i] + zeros[i] for i in range(nPairs)]
                remainder = ones[nPairs:] if len(ones) > len(zeros) else zeros[nPairs:]
                ones      = paired
                zeros     = remainder
                if not zeros:
                    break
            pattern = []
            for group in ones + zeros:
                pattern += group

        # apply rotation
        rotation = rotation % len(pattern) if pattern else 0
        pattern  = pattern[rotation:] + pattern[:rotation]

        # select onset times from the actual grid positions
        onsets = [gridTimes[i] for i, v in enumerate(pattern) if v == 1]

        endTimeSec = startTimeSec + totalSec
        return cls(
            onsets,
            startTimeSec = startTimeSec,
            endTimeSec   = endTimeSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )

    @classmethod
    def fromMidiFile(
        cls,
        path: str,
        trackNumber: int = 0,
        *,
        pitches: int | list[int] | None = None,
    ) -> "TimeGrid":
        """
        Build a TimeGrid from note-on events in a MIDI file.

        Tempo is searched across ALL tracks (DAWs typically place set_tempo
        in track 0 regardless of which track contains the notes).
        Time values are stored in seconds. bpm and ticksPerBeat from the
        file are preserved so they can be passed directly to Gesture/Phonon.

        Parameters
        ----------
        path : str
            Path to the MIDI file.
        trackNumber : int
            Which track to read note-on events from (0-indexed).
        pitches : int | list[int] | None
            None  = import all pitches (default).
            int   = import only that MIDI note number.
            list  = import only those MIDI note numbers.

        Returns
        -------
        TimeGrid with:
            values       — note-on times in seconds
            bpm          — tempo from file  → pass to Gesture(bpm=tg.bpm)
            ticksPerBeat — resolution from file → pass to Gesture(ticksPerBeat=tg.ticksPerBeat)

        Example
        -------
        >>> tg = TimeGrid.fromMidiFile('/tmp/melody.mid')
        >>> tg_kick = TimeGrid.fromMidiFile('/tmp/drums.mid', pitches=36)
        >>>
        >>> # Preserve file tempo when building a Gesture:
        >>> g = Gesture(0,
        ...     [Phonon(st, 0.1, 60, bpm=tg.bpm) for st in tg.sorted()],
        ...     bpm=tg.bpm, ticksPerBeat=tg.ticksPerBeat)
        """
        from mido import MidiFile, MetaMessage, Message, tempo2bpm, tick2second

        # normalise pitch filter
        if pitches is None:
            pitchSet = None
        elif isinstance(pitches, int):
            pitchSet = {pitches}
        else:
            pitchSet = set(pitches)

        midiFile     = MidiFile(path)
        ticksPerBeat = midiFile.ticks_per_beat
        tempo        = 500000   # MIDI default = 120 bpm
        bpm          = 120.0

        # search ALL tracks for the first tempo marking
        found_tempo = False
        for track in midiFile.tracks:
            for msg in track:
                if isinstance(msg, MetaMessage) and msg.type == 'set_tempo':
                    tempo       = msg.tempo
                    bpm         = float(tempo2bpm(tempo))
                    found_tempo = True
                    break
            if found_tempo:
                break

        # collect note-on times in seconds from the target track
        currentTick  = 0
        noteOnTimes: list[float] = []

        for msg in midiFile.tracks[trackNumber]:
            if not isinstance(msg, Message):
                continue
            currentTick += msg.time
            if msg.type != 'note_on' or msg.velocity == 0:
                continue
            if pitchSet is not None and msg.note not in pitchSet:
                continue
            timeSec = round(tick2second(currentTick, ticksPerBeat, tempo), 6)
            noteOnTimes.append(timeSec)

        if not noteOnTimes:
            print(f"TimeGrid.fromMidiFile: no matching note-on events in '{path}'")
            return cls([], bpm=bpm, ticksPerBeat=ticksPerBeat)

        startTimeSec = min(noteOnTimes)
        endTimeSec   = max(noteOnTimes)

        tg = cls(
            noteOnTimes,
            startTimeSec = startTimeSec,
            endTimeSec   = endTimeSec,
            bpm          = bpm,
            ticksPerBeat = ticksPerBeat,
        )
        print(
            f"TimeGrid.fromMidiFile: {len(tg)} events | "
            f"bpm={bpm:.2f} | ticksPerBeat={ticksPerBeat} | "
            f"{startTimeSec:.3f}s – {endTimeSec:.3f}s"
            + (f" | pitches={sorted(pitchSet)}" if pitchSet else "")
        )
        return tg



    @classmethod
    def fromDensity(
        cls,
        startTimeSec: float = 0.0,
        durationSec: float = 4.0,
        densityHz: float = 5.0,
        leaning: float = 0.0,
        subdivisions: list = [],
        *,
        leaningIntensity: float = 5.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
        leaningMin: float = 0.01,
        leaningMax: float = 0.99,
        leaningCurve: str = 'exponential',
    ) -> "TimeGrid":
        """
        Generate a TimeGrid using soft probabilistic density.

        Each candidate time position gets a Bernoulli trial. The base
        probability is calibrated so the expected event count ≈
        densityHz * durationSec. Leaning skews the probability distribution
        across the duration.

        Parameters
        ----------
        startTimeSec : float
        durationSec : float
        densityHz : float
            Expected events per second.
        leaning : float
            -1.0 = front-heavy (dense at start, sparse at end)
             0.0 = uniform probability
            +1.0 = end-heavy   (sparse at start, dense at end)
        subdivisions : list
            Quantisation grid e.g. [1, 2, 3] snaps events to the nearest
            point from those beat subdivisions combined.
            [] = no quantisation (continuous positions at 1ms resolution).
        leaningIntensity : float
            Scales the steepness of the decay curve. Default 5.0.
            Higher = more aggressive concentration at the dense end.
        bpm : float
        ticksPerBeat : int
        leaningMin : float
            Probability at the sparse end. Default 0.01.
        leaningMax : float
            Probability at the dense end. Default 0.99.
        leaningCurve : str
            'exponential' — true exponential decay (default).
            'linear'      — linear interpolation between leaningMin/Max.

        Example
        -------
        >>> TimeGrid.fromDensity(0.0, 4.0, 10,
        ...     leaning=-0.8, subdivisions=[1, 2, 4],
        ...     leaningIntensity=3.0)
        """
        from math import log, exp
        import random as _random

        expectedEvents = densityHz * durationSec

        # --- build candidate time positions ---
        if subdivisions:
            startBeats    = secToBeat(startTimeSec, bpm)
            durationBeats = secToBeat(durationSec, bpm)
            seen: set[float] = set()
            candidates: list[float] = []
            for sd in subdivisions:
                nSteps = int(durationBeats * sd)
                for i in range(nSteps + 1):
                    tSec = round(beatToSec(startBeats + i / sd, bpm), 8)
                    if startTimeSec <= tSec <= startTimeSec + durationSec:
                        if tSec not in seen:
                            candidates.append(tSec)
                            seen.add(tSec)
            candidates.sort()
        else:
            resolution = 0.001
            nSteps     = int(durationSec / resolution)
            candidates = [
                round(startTimeSec + i * resolution, 8)
                for i in range(nSteps + 1)
            ]

        nCandidates = len(candidates)
        if nCandidates == 0:
            return cls([], startTimeSec=startTimeSec, bpm=bpm,
                       ticksPerBeat=ticksPerBeat)

        baseProbability = min(0.99, expectedEvents / nCandidates)

        def weight(t: float) -> float:
            if abs(leaning) < 1e-9:
                return 1.0
            k = log(leaningMax / leaningMin) * abs(leaning) * leaningIntensity
            if leaningCurve == 'exponential':
                w = (leaningMax * exp(-k * t) if leaning < 0
                     else leaningMax * exp(-k * (1.0 - t)))
            else:
                w = (leaningMax + (leaningMin - leaningMax) * t if leaning < 0
                     else leaningMin + (leaningMax - leaningMin) * t)
            return max(leaningMin, min(leaningMax, w))

        maxRetries = 100
        events: list[float] = []
        for attempt in range(maxRetries):
            events = []
            for i, tSec in enumerate(candidates):
                t = i / (nCandidates - 1) if nCandidates > 1 else 0.5
                p = min(1.0, baseProbability * weight(t))
                if _random.random() < p:
                    events.append(tSec)
            if events:
                break

        if not events:
            # fallback: return the single most probable candidate
            peakIdx = 0 if leaning <= 0 else nCandidates - 1
            events  = [candidates[peakIdx]]

        return cls(
            events,
            startTimeSec=startTimeSec,
            endTimeSec=startTimeSec + durationSec,
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )

    def leaningSample(
        self,
        densityHz: float = 5.0,
        leaning: float = 0.0,
        *,
        leaningIntensity: float = 5.0,
        leaningMin: float = 0.01,
        leaningMax: float = 0.99,
        leaningCurve: str = 'exponential',
    ) -> "TimeGrid":
        """
        Probabilistically sample from this TimeGrid's existing positions
        using the same leaning/density logic as fromDensity.

        Unlike fromDensity, no new positions are generated — the grid itself
        provides the candidates. densityHz is calibrated against the number
        of existing positions, so the expected event count ≈
        densityHz * durationSec, but may be lower on coarse grids since
        duplicate selections collapse (it's a set).

        Parameters
        ----------
        densityHz : float
            Expected events per second.
        leaning : float
            -1.0 = front-heavy, 0.0 = uniform, +1.0 = end-heavy.
        leaningIntensity : float
            Steepness of the decay curve. Default 5.0.
        leaningMin : float
            Probability at the sparse end. Default 0.01.
        leaningMax : float
            Probability at the dense end. Default 0.99.
        leaningCurve : str
            'exponential' or 'linear'.

        Returns
        -------
        A new TimeGrid with the surviving positions, preserving bpm,
        ticksPerBeat, startTimeSec and endTimeSec.

        Example
        -------
        >>> tg = TimeGrid.fromSubdivisions([1,2,4], bpm=120, durationBeats=4)
        >>> sparse = tg.leaningSample(3.0, leaning=-0.8, leaningIntensity=3.0)
        """
        from math import log, exp
        import random as _random

        candidates  = self.sorted()
        nCandidates = len(candidates)
        if nCandidates == 0:
            return TimeGrid([], startTimeSec=self.startTimeSec,
                            endTimeSec=self.endTimeSec,
                            bpm=self.bpm, ticksPerBeat=self.ticksPerBeat)

        expectedEvents  = densityHz * self.durationSec
        baseProbability = min(0.99, expectedEvents / nCandidates)

        def weight(t: float) -> float:
            if abs(leaning) < 1e-9:
                return 1.0
            k = log(leaningMax / leaningMin) * abs(leaning) * leaningIntensity
            if leaningCurve == 'exponential':
                w = (leaningMax * exp(-k * t) if leaning < 0
                     else leaningMax * exp(-k * (1.0 - t)))
            else:
                w = (leaningMax + (leaningMin - leaningMax) * t if leaning < 0
                     else leaningMin + (leaningMax - leaningMin) * t)
            return max(leaningMin, min(leaningMax, w))

        maxRetries = 100
        events: list[float] = []
        for attempt in range(maxRetries):
            events = []
            for i, tSec in enumerate(candidates):
                t = i / (nCandidates - 1) if nCandidates > 1 else 0.5
                p = min(1.0, baseProbability * weight(t))
                if _random.random() < p:
                    events.append(tSec)
            if events:
                break

        if not events:
            # fallback: return the single most probable candidate
            peakIdx = 0 if leaning <= 0 else nCandidates - 1
            events  = [candidates[peakIdx]]

        return TimeGrid(
            events,
            startTimeSec=self.startTimeSec,
            endTimeSec=self.endTimeSec,
            bpm=self.bpm,
            ticksPerBeat=self.ticksPerBeat,
        )

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
        """
        Return inter-onset intervals between consecutive grid points.

        unit : 'seconds' | 'beats'
        """
        absTimes = self.sorted()
        if len(absTimes) < 2:
            return []
        deltas = [absTimes[i+1] - absTimes[i] for i in range(len(absTimes) - 1)]
        if unit in ('beats', 'b'):
            deltas = [secToBeat(d, self.bpm) for d in deltas]
        return deltas

    def getDensityCurve(
        self,
        lookbackInterval: float = 1.0,
        lookBackFrame: float = 1.0,
        *,
        lookBackUnit: str = 'sec',
    ) -> dict:
        """
        Compute event density over sliding windows.

        Parameters
        ----------
        lookbackInterval : float
            Step between density calculation points.
        lookBackFrame : float
            Width of each analysis window.
        lookBackUnit : str
            'sec' / 'seconds' / 's'  or  'beats' / 'b'.

        Returns the density dict (also stored in self.densityCurve).
        """
        match lookBackUnit:
            case u if u in ('sec', 'seconds', 's'):
                intervalSec = float(lookbackInterval)
                frameSec    = float(lookBackFrame)
            case u if u in ('beats', 'b'):
                intervalSec = beatToSec(lookbackInterval, self.bpm)
                frameSec    = beatToSec(lookBackFrame,    self.bpm)
            case _:
                raise ValueError(
                    f"TimeGrid.getDensityCurve: invalid lookBackUnit '{lookBackUnit}'"
                )

        nPoints = int(ceil(self.durationSec / intervalSec)) + 1
        frames  = [(i * intervalSec - frameSec, i * intervalSec)
                   for i in range(nPoints)]

        # grid values are already in seconds
        pointsSec = self.sorted()

        densities   = []
        minDensity  = float("inf")
        maxDensity  = 0.0

        for frameStart, frameEnd in frames:
            count   = sum(1 for s in pointsSec if frameStart <= s <= frameEnd)
            density = count / frameSec if frameSec > 0 else 0.0
            densities.append(density)
            minDensity = min(minDensity, density)
            maxDensity = max(maxDensity, density)

        key = f"frame_{frameSec}_interval_{intervalSec}"
        result = {
            "density":             densities,
            "minDensityHz":        minDensity,
            "maxDensityHz":        maxDensity,
            "relativeMaxPosition": (densities.index(maxDensity) / len(densities)
                                    if densities else 0.0),
            "meanDensityHz":       sum(densities) / len(densities) if densities else 0.0,
        }
        self.densityCurve[key] = result
        return result

    def getSelfSimilarity(self, maxVal: float = 1.0) -> float:
        """
        Compute a self-similarity score from the inter-onset interval sequence.
        """
        relativeTimes = self.toRelativeTimes()
        if len(relativeTimes) < 2:
            return 0.0

        sublists = []
        for i in range(len(relativeTimes)):
            for j in range(i + 1, len(relativeTimes)):
                sub = relativeTimes[i:j]
                if sub:
                    sublists.append(sub)

        similarity = []
        for sl in sublists:
            n = len(sl)
            indices = [
                idx for idx in range(len(relativeTimes) - n)
                if relativeTimes[idx:idx+n] == sl
            ]
            if indices:
                similarity.append(n / len(indices))

        return len(similarity) / maxVal if maxVal else 0.0

    def analyseExternalStartTimesSec(self, starts: list[float]) -> dict:
        """
        Analyse how a set of external event times relates to this grid.

        Returns
        -------
        dict with keys:
            density : events per beat
            leaning : centroid position [-1, 1] (negative = early, positive = late)
        """
        grid  = self.sorted()
        steps = len(grid)

        if steps == 0 or not starts:
            return {"density": 0.0, "leaning": 0.0}

        indices = []
        for s in starts:
            q   = self.quantise(s)
            idx = min(range(steps), key=lambda i: abs(grid[i] - q))
            indices.append(idx)

        if not indices:
            return {"density": 0.0, "leaning": 0.0}

        density   = len(indices) / self.durationBeats if self.durationBeats else 0.0
        positions = [i / (steps - 1) for i in indices] if steps > 1 else [0.5]
        centroid  = sum(positions) / len(positions)
        leaning   = centroid * 2 - 1

        return {"density": density, "leaning": leaning}

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/timeGrid.mid",
        name: str = "timeGrid",
        allLayers: bool = True,
    ) -> None:
        """
        Export the grid as a sequence of short notes, one per time position.

        Each note has the minimum inter-onset duration so no notes overlap.
        """
        from .TemporalObject import TemporalObject
        from .Exporters import MidiExporter

        srt = self.sorted()
        if not srt:
            print("TimeGrid.toMidi: grid is empty, nothing to export.")
            return

        minDurSec = (
            min(srt[i+1] - srt[i] for i in range(len(srt) - 1))
            if len(srt) > 1 else 0.25  # fallback: quarter second for single-point grids
        )

        container = TemporalObject(0.0, data={"bpm": self.bpm,
                                               "ticksPerBeat": self.ticksPerBeat})
        for stSec in srt:
            container.addChild(TemporalObject(
                stSec, minDurSec,
                data={
                    "pitchMidi":  60.0,
                    "pitchwheel": (0.0, 0.0),
                    "dynamicdB":  80.0,
                    "bpm":        self.bpm,
                    "ticksPerBeat": self.ticksPerBeat,
                },
            ))

        container.export(MidiExporter(path, trackName=name))
        print(f"TimeGrid: saved -> {path}")

        if allLayers:
            for key, layer in self.layers.items():
                layerPath = path[:-4] + key.replace("/", "_by") + ".mid"
                if isinstance(layer, TimeGrid):
                    layer.toMidi(layerPath, key, allLayers=False)

    def parseMidi(
        self,
        path: str = "/tmp/timeGrid.mid",
        name: str = "timeGrid",
        allLayers: bool = True,
    ) -> None:
        """Legacy alias for toMidi()."""
        self.toMidi(path, name, allLayers)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TimeGrid\n"
            f"   sorted        = {self.sorted()},\n"
            f"   durationSec   = {self.durationSec},\n"
            f"   durationBeats = {self.durationBeats},\n"
            f"   endTimeSec    = {self.endTimeSec},\n"
            f"   bpm           = {self.bpm},\n"
            f"   ticksPerBeat  = {self.ticksPerBeat},\n"
            f"   size          = {len(self)},\n"
            f"   layers        = {list(self.layers.keys())}\n"
        )