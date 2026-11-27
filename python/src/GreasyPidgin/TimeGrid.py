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
TimeGrid.RQQfromLSystem(rqqs, productionRules, numIterations, ...)
TimeGrid.fromEuclidean(pulses, steps, rotation, ...)
TimeGrid.fromPulsesEuclidean(pulses, subdivisions, rotation, ...)
TimeGrid.fromDensityEuclidean(densityHz, subdivisions, rotation, ...)
TimeGrid.fromDensity(startTimeSec, durationSec, densityHz, leaning, subdivisions, ...)
TimeGrid.fromMidiFile(path, trackNumber, *, pitches)

Export
------
tg.toMidi(path, name, allLayers)   — one note per grid point
tg.parseMidi(...)                  — legacy alias

Analysis
--------
tg.toRelativeTimes(unit)
tg.getDensityCurve(lookbackInterval, lookBackFrame, *, lookBackUnit)
tg.getSelfSimilarity(maxVal, maxLength)
tg.analyseExternalStartTimesSec(starts)
"""

import random
from bisect import bisect_left, bisect_right
from collections import Counter
from math import ceil, exp, log

from GreasyPidgin.Grid import Grid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def beatToSec(beat: float, bpm: float = 60.0) -> float:
    return float(beat) * 60.0 / float(bpm)

def secToBeat(sec: float, bpm: float = 60.0) -> float:
    return float(sec) * float(bpm) / 60.0


def midiTempoMap(midiFile):
    """
    Tempo changes of all tracks of a mido.MidiFile as a function
    tick -> seconds, plus the first tempo in bpm (MIDI default 120 if none).
    """
    from mido import MetaMessage, tempo2bpm
    tpb = midiFile.ticks_per_beat
    tempos = []
    for track in midiFile.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if isinstance(msg, MetaMessage) and msg.type == 'set_tempo':
                tempos.append((tick, msg.tempo))
    tempos.sort(key=lambda t: t[0])
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, 500000))
    segments = []                                  # (startTick, startSec, tempo)
    for tick, tempo in tempos:
        if segments:
            t0, s0, tp0 = segments[-1]
            segments.append((tick, s0 + (tick - t0) * tp0 / 1e6 / tpb, tempo))
        else:
            segments.append((tick, 0.0, tempo))

    def tickToSec(tick: int) -> float:
        t0, s0, tempo = next(s for s in reversed(segments) if s[0] <= tick)
        return round(s0 + (tick - t0) * tempo / 1e6 / tpb, 6)

    return tickToSec, float(tempo2bpm(segments[0][2]))


def _bjorklund(pulses: int, steps: int) -> list[int]:
    """Euclidean rhythm: `pulses` onsets spread as evenly as possible over `steps`."""
    pulses = max(0, min(int(pulses), steps))
    if pulses in (0, steps):
        return [1 if pulses else 0] * steps
    ones, zeros = [[1]] * pulses, [[0]] * (steps - pulses)
    while len(zeros) > 1:
        n = min(len(ones), len(zeros))
        ones, zeros = [ones[i] + zeros[i] for i in range(n)], (ones[n:] if len(ones) > len(zeros) else zeros[n:])
    return [bit for group in ones + zeros for bit in group]


def _rotate(pattern: list, rotation: int) -> list:
    r = rotation % len(pattern) if pattern else 0
    return pattern[r:] + pattern[:r]


def _subdivisionTimes(startTimeSec, totalSec, subdivisions, bpm, includeEnd=False) -> list[float]:
    """Sorted, unique times (seconds) of all beat subdivisions within the span."""
    startBeats = secToBeat(startTimeSec, bpm)
    spanBeats  = secToBeat(totalSec, bpm)
    eps, endSec = 1e-9, startTimeSec + totalSec
    seen = set()
    for sd in subdivisions:
        for i in range(int(round(spanBeats * sd)) + 1):
            t = round(beatToSec(startBeats + i / sd, bpm), 8)
            if startTimeSec - eps <= t and (t <= endSec + eps if includeEnd else t < endSec - eps):
                seen.add(t)
    return sorted(seen)


def _totalSec(durationSec, durationBeats, bpm, defaultBeats):
    if durationSec is not None:
        return float(durationSec)
    return beatToSec(float(durationBeats if durationBeats is not None else defaultBeats), bpm)


def _leaningWeights(n, leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve) -> list[float]:
    """Probability weight per candidate position (0 = first, n-1 = last)."""
    if abs(leaning) < 1e-9:
        return [1.0] * n
    k = log(leaningMax / leaningMin) * abs(leaning) * leaningIntensity
    weights = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.5
        if leaningCurve == 'exponential':
            w = leaningMax * exp(-k * (t if leaning < 0 else 1.0 - t))
        else:
            w = leaningMax + (leaningMin - leaningMax) * t if leaning < 0 else leaningMin + (leaningMax - leaningMin) * t
        weights.append(max(leaningMin, min(leaningMax, w)))
    return weights


def _bernoulliPick(candidates, expectedEvents, weights, leaning, maxRetries=100) -> list[float]:
    """
    Keep each candidate with probability base * weight, base chosen so the
    expected number of kept candidates is `expectedEvents` (capped at all).
    Retries if nothing survives; falls back to the most probable candidate.
    """
    base = expectedEvents / sum(weights) if sum(weights) else 0.0
    probs = [min(1.0, base * w) for w in weights]
    for _ in range(maxRetries):
        events = [t for t, p in zip(candidates, probs) if random.random() < p]
        if events:
            return events
    return [candidates[0 if leaning <= 0 else -1]]


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

    Divides a duration into proportional parts. A nested RQQ counts with
    its own duration as its weight and keeps its subdivisions. Rest()
    values take up time but have no onset.

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
    >>> RQQ(4, [1, 1, Rest(1), 1])          # 4 beats: quarter, quarter, quarter rest, quarter
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
        self._getStartsBeats()

    def _divideDurationRaw(self) -> None:
        total = sum(self.ratios)
        self.rawdividedDurations = [
            Rest(r / total * self.durationBeats) if isinstance(r, Rest) else r / total * self.durationBeats
            for r in self.ratios
        ]

    def _getStartsBeats(self) -> None:
        """Onsets (beats) of the non-rest parts."""
        self._divideDurationRaw()
        self.startsBeats = []
        pos = self.startOffsetBeats
        for dur in self.rawdividedDurations:
            if not isinstance(dur, Rest):
                self.startsBeats.append(pos)
            pos += float(dur)

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
        super().__init__(values)
        self.bpm          = float(bpm)
        self.ticksPerBeat = int(ticksPerBeat)
        self.layers:       dict = {}
        self.densityCurve: dict = {}
        self.startTimeSec   = float(startTimeSec)
        self.startTimeBeats = secToBeat(self.startTimeSec, self.bpm)

        srt = self.sorted()
        if endTimeSec is not None:
            self.endTimeSec = float(endTimeSec)
        elif len(srt) >= 2:
            self.endTimeSec = 2 * srt[-1] - srt[-2]
        else:
            self.endTimeSec = srt[-1] if srt else 0.0

        self.durationSec   = self.endTimeSec - self.startTimeSec
        self.durationBeats = secToBeat(self.durationSec, self.bpm)
        self.endTimeBeats  = secToBeat(self.endTimeSec, self.bpm)

    def _like(self, values) -> "TimeGrid":
        """New TimeGrid with this grid's span and tempo."""
        return TimeGrid(values, startTimeSec=self.startTimeSec, endTimeSec=self.endTimeSec,
                        bpm=self.bpm, ticksPerBeat=self.ticksPerBeat)

    def sample(self, numElements: int) -> "TimeGrid":
        """numElements random positions as a new TimeGrid (same span and tempo)."""
        return self._like(super().sample(numElements))

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def series(cls, startTimeSec: float, stepSec: float, size: int, *,
               bpm: float = 60.0, ticksPerBeat: int = 480) -> "TimeGrid":
        """Arithmetic series of time positions."""
        return cls(Grid.series(startTimeSec, stepSec, size), startTimeSec=startTimeSec,
                   endTimeSec=startTimeSec + size * stepSec, bpm=bpm, ticksPerBeat=ticksPerBeat)

    @classmethod
    def linearInterpolation(cls, startTimeSec: float, endTimeSec: float, size: int, *,
                            bpm: float = 60.0, ticksPerBeat: int = 480, decimals: int = 4,
                            includeEnd: bool = True) -> "TimeGrid":
        """Linearly spaced time positions between startTimeSec and endTimeSec."""
        base = Grid.linearInterpolation(startTimeSec, endTimeSec, size, decimals=decimals, includeEnd=includeEnd)
        return cls(base, startTimeSec=startTimeSec, endTimeSec=endTimeSec, bpm=bpm, ticksPerBeat=ticksPerBeat)

    @classmethod
    def fromSubdivisions(cls, subdivisions: list | None = None, *, bpm: float = 60.0,
                         startTimeBeats: float = 0.0, durationBeats: float,
                         ticksPerBeat: int = 480) -> "TimeGrid":
        """
        Multiple simultaneous beat subdivisions, e.g. [1, 2, 3] for quarters,
        eighths and triplets. Each one is kept as a layer ("/ 3"); all are
        merged into the grid.

        >>> TimeGrid.fromSubdivisions([1, 2, 3], bpm=120, durationBeats=4)
        """
        startSec = beatToSec(startTimeBeats, bpm)
        layers = {
            f"/ {sd}": TimeGrid.series(startSec, beatToSec(1 / sd, bpm), int(durationBeats * sd),
                                       bpm=bpm, ticksPerBeat=ticksPerBeat)
            for sd in (subdivisions or [1])
        }
        tg = cls(set().union(*layers.values()), startTimeSec=startSec,
                 endTimeSec=beatToSec(startTimeBeats + durationBeats, bpm), bpm=bpm, ticksPerBeat=ticksPerBeat)
        tg.layers = layers
        return tg

    @classmethod
    def fromRQQ(cls, rqq: RQQ, *, startTimeSec: float = 0.0, bpm: float = 60.0,
                ticksPerBeat: int = 480) -> "TimeGrid":
        """Onsets of an RQQ rhythm, starting at startTimeSec (the RQQ itself is not changed)."""
        values = [round(startTimeSec + beatToSec(b - rqq.startOffsetBeats, bpm), 10) for b in rqq.startsBeats]
        return cls(values, startTimeSec=startTimeSec,
                   endTimeSec=startTimeSec + beatToSec(rqq.durationBeats, bpm), bpm=bpm, ticksPerBeat=ticksPerBeat)

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
        TimeGrid from an integer L-System whose final generation indexes a
        palette of RQQs.

        rqqs                 : palette, index 0 = rqqs[0], ...
        productionRules      : [[predecessor, [successor0, ...]], ...],
                               e.g. [[0, [0,1]], [1, [2,1,2]], [2, [0]]]
        axiom                : starting sequence, default [0]
        durationsCutoffBeats : keep only this many beats, taken from the
                               'start' (default), 'end' or 'middle'

        >>> r1, r2, r3 = RQQ(0.5, [1, 1]), RQQ(1, [1, 1, 1]), RQQ(1.5, [1, 1, 1, 1])
        >>> TimeGrid.RQQfromLSystem([r1, r2, r3], [[0, [0,1]], [1, [2,1,2]], [2, [0]]],
        ...     5, bpm=90, durationsCutoffBeats=16, cutoffMode='end')
        """
        from GreasyPidgin.LSystem import LSystem, ProductionRules, ProductionRule

        rules = ProductionRules([ProductionRule(pred, succ) for pred, succ in productionRules])
        lind = LSystem(axiom if axiom is not None else [0], rules)
        lind.iterate(numIterations)
        sequence = [rqqs[i] for i in lind.currentGeneration() if 0 <= i < len(rqqs)]
        if not sequence:
            return cls([], startTimeSec=startTimeSec, bpm=bpm, ticksPerBeat=ticksPerBeat)

        durationBeats = sum(r.durationBeats for r in sequence)
        tg = cls.fromRQQ(RQQ(durationBeats, sequence), startTimeSec=startTimeSec, bpm=bpm, ticksPerBeat=ticksPerBeat)
        if durationsCutoffBeats is None:
            return tg

        windowSec = beatToSec(durationsCutoffBeats, bpm)
        spare = max(0.0, beatToSec(durationBeats, bpm) - windowSec)
        offset = {'end': spare, 'middle': spare / 2}.get(cutoffMode, 0.0)
        windowStart = startTimeSec + offset
        kept = [t - offset for t in tg.sorted() if windowStart - 1e-9 <= t < windowStart + windowSec]
        return cls(kept, startTimeSec=startTimeSec, endTimeSec=startTimeSec + windowSec,
                   bpm=bpm, ticksPerBeat=ticksPerBeat)

    @classmethod
    def fromEuclidean(cls, pulses: int, steps: int, rotation: int = 0, *,
                      durationBeats: float | None = None, durationSec: float | None = None,
                      startTimeSec: float = 0.0, bpm: float = 60.0, ticksPerBeat: int = 480) -> "TimeGrid":
        """
        Euclidean rhythm (Bjorklund): `pulses` onsets spread evenly over `steps`
        equal steps, rotated left by `rotation`. Duration: durationSec, else
        durationBeats, else one beat per step.

        E(3,8) = [1,0,0,1,0,0,1,0] (tresillo), E(5,8) = [1,0,1,1,0,1,1,0] (cinquillo)

        >>> TimeGrid.fromEuclidean(3, 8, durationBeats=2.0, bpm=120)
        """
        if pulses < 0 or steps <= 0:
            raise ValueError(f"TimeGrid.fromEuclidean: need steps > 0 and pulses >= 0, got pulses={pulses}, steps={steps}")
        pattern = _rotate(_bjorklund(pulses, steps), rotation)
        totalSec = _totalSec(durationSec, durationBeats, bpm, steps)
        stepSec = totalSec / steps
        return cls([startTimeSec + i * stepSec for i, v in enumerate(pattern) if v],
                   startTimeSec=startTimeSec, endTimeSec=startTimeSec + totalSec, bpm=bpm, ticksPerBeat=ticksPerBeat)

    @classmethod
    def fromPulsesEuclidean(cls, pulses: int, subdivisions: list | None = None, rotation: int = 0, *,
                            durationBeats: float | None = None, durationSec: float | None = None,
                            startTimeSec: float = 0.0, bpm: float = 60.0, ticksPerBeat: int = 480) -> "TimeGrid":
        """
        Euclidean rhythm on the union of beat subdivisions (default [1, 2, 4]):
        those positions are the steps; `pulses` is clamped to their number.
        Duration default: 4 beats.

        >>> TimeGrid.fromPulsesEuclidean(7, [3], 0, durationBeats=8.0, bpm=126.0)
        """
        totalSec = _totalSec(durationSec, durationBeats, bpm, 4.0)
        times = _subdivisionTimes(startTimeSec, totalSec, subdivisions or [1, 2, 4], bpm)
        if not times:
            return cls([], startTimeSec=startTimeSec, bpm=bpm, ticksPerBeat=ticksPerBeat)
        pattern = _rotate(_bjorklund(pulses, len(times)), rotation)
        return cls([t for t, v in zip(times, pattern) if v],
                   startTimeSec=startTimeSec, endTimeSec=startTimeSec + totalSec, bpm=bpm, ticksPerBeat=ticksPerBeat)

    @classmethod
    def fromDensityEuclidean(cls, densityHz: float = 4.0, subdivisions: list | None = None, rotation: int = 0, *,
                             durationBeats: float | None = None, durationSec: float | None = None,
                             startTimeSec: float = 0.0, bpm: float = 60.0, ticksPerBeat: int = 480) -> "TimeGrid":
        """
        Like fromPulsesEuclidean, with pulses = round(densityHz * duration).

        >>> TimeGrid.fromDensityEuclidean(4.0, [1, 2, 4], durationBeats=2.0, bpm=120)
        """
        totalSec = _totalSec(durationSec, durationBeats, bpm, 4.0)
        return cls.fromPulsesEuclidean(int(round(densityHz * totalSec)), subdivisions, rotation,
                                       durationSec=totalSec, startTimeSec=startTimeSec, bpm=bpm,
                                       ticksPerBeat=ticksPerBeat)

    @classmethod
    def fromMidiFile(cls, path: str, trackNumber: int = 0, *,
                     pitches: int | list[int] | None = None) -> "TimeGrid":
        """
        Note-on times (seconds) of one track of a MIDI file. Tempo changes of
        all tracks are honoured; bpm is the first tempo and ticksPerBeat the
        file's resolution, ready for Gesture / Phonon.

        pitches : None = all, int or list = only those MIDI notes

        >>> tg = TimeGrid.fromMidiFile('/tmp/melody.mid')
        >>> kick = TimeGrid.fromMidiFile('/tmp/drums.mid', pitches=36)
        """
        from mido import MidiFile, Message

        pitchSet = None if pitches is None else ({pitches} if isinstance(pitches, int) else set(pitches))
        midiFile = MidiFile(path)
        tickToSec, bpm = midiTempoMap(midiFile)
        tpb = midiFile.ticks_per_beat

        tick, onsets = 0, []
        for msg in midiFile.tracks[trackNumber]:
            tick += msg.time
            if (isinstance(msg, Message) and msg.type == 'note_on' and msg.velocity > 0
                    and (pitchSet is None or msg.note in pitchSet)):
                onsets.append(tickToSec(tick))

        if not onsets:
            print(f"TimeGrid.fromMidiFile: no matching note-on events in '{path}'")
            return cls([], bpm=bpm, ticksPerBeat=tpb)
        tg = cls(onsets, startTimeSec=min(onsets), endTimeSec=max(onsets), bpm=bpm, ticksPerBeat=tpb)
        print(
            f"TimeGrid.fromMidiFile: {len(tg)} events | bpm={bpm:.2f} | ticksPerBeat={tpb} | "
            f"{tg.startTimeSec:.3f}s – {tg.endTimeSec:.3f}s"
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
        subdivisions: list | None = None,
        *,
        leaningIntensity: float = 5.0,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
        leaningMin: float = 0.01,
        leaningMax: float = 0.99,
        leaningCurve: str = 'exponential',
    ) -> "TimeGrid":
        """
        Random onsets with an expected density, optionally leaning towards one end.

        Every candidate position gets a Bernoulli trial; probabilities are
        weighted by the leaning and calibrated so the expected number of
        events is densityHz * durationSec (at most every candidate).

        densityHz        : expected events per second
        leaning          : -1 = dense at the start, 0 = uniform, +1 = dense at the end
        subdivisions     : candidates on these beat subdivisions, e.g. [1, 2, 3];
                           None / [] = every millisecond
        leaningIntensity : steepness of the leaning (default 5)
        leaningMin / Max : weight at the sparse / dense end
        leaningCurve     : 'exponential' (default) or 'linear'

        >>> TimeGrid.fromDensity(0.0, 4.0, 10, leaning=-0.8, subdivisions=[1, 2, 4])
        """
        if subdivisions:
            candidates = _subdivisionTimes(startTimeSec, durationSec, subdivisions, bpm, includeEnd=True)
        else:
            candidates = [round(startTimeSec + i * 0.001, 8) for i in range(int(durationSec / 0.001) + 1)]
        if not candidates:
            return cls([], startTimeSec=startTimeSec, bpm=bpm, ticksPerBeat=ticksPerBeat)
        weights = _leaningWeights(len(candidates), leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve)
        events = _bernoulliPick(candidates, densityHz * durationSec, weights, leaning)
        return cls(events, startTimeSec=startTimeSec, endTimeSec=startTimeSec + durationSec,
                   bpm=bpm, ticksPerBeat=ticksPerBeat)

    def leaningSample(self, densityHz: float = 5.0, leaning: float = 0.0, *,
                      leaningIntensity: float = 5.0, leaningMin: float = 0.01,
                      leaningMax: float = 0.99, leaningCurve: str = 'exponential') -> "TimeGrid":
        """
        Probabilistic selection from this grid's own positions with the same
        density / leaning logic as fromDensity (same span and tempo).

        >>> tg = TimeGrid.fromSubdivisions([1,2,4], bpm=120, durationBeats=4)
        >>> sparse = tg.leaningSample(3.0, leaning=-0.8, leaningIntensity=3.0)
        """
        candidates = self.sorted()
        if not candidates:
            return self._like([])
        weights = _leaningWeights(len(candidates), leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve)
        return self._like(_bernoulliPick(candidates, densityHz * self.durationSec, weights, leaning))

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def toRelativeTimes(self, unit: str = 'seconds') -> list[float]:
        """Inter-onset intervals between consecutive grid points; unit 'seconds' | 'beats'."""
        srt = self.sorted()
        deltas = [b - a for a, b in zip(srt, srt[1:])]
        if unit in ('beats', 'b'):
            deltas = [secToBeat(d, self.bpm) for d in deltas]
        return deltas

    def getDensityCurve(self, lookbackInterval: float = 1.0, lookBackFrame: float = 1.0, *,
                        lookBackUnit: str = 'sec') -> dict:
        """
        Events per second in a window of lookBackFrame ending at every
        lookbackInterval step from startTimeSec to endTimeSec.

        lookBackUnit : 'sec' / 'seconds' / 's' or 'beats' / 'b'

        Returns the result dict (also stored in self.densityCurve).
        """
        if lookBackUnit in ('sec', 'seconds', 's'):
            intervalSec, frameSec = float(lookbackInterval), float(lookBackFrame)
        elif lookBackUnit in ('beats', 'b'):
            intervalSec, frameSec = beatToSec(lookbackInterval, self.bpm), beatToSec(lookBackFrame, self.bpm)
        else:
            raise ValueError(f"TimeGrid.getDensityCurve: invalid lookBackUnit '{lookBackUnit}'")

        points = self.sorted()
        densities = []
        for i in range(int(ceil(self.durationSec / intervalSec)) + 1):
            end = self.startTimeSec + i * intervalSec
            count = bisect_right(points, end) - bisect_left(points, end - frameSec)
            densities.append(count / frameSec if frameSec > 0 else 0.0)

        result = {
            "density":             densities,
            "minDensityHz":        min(densities),
            "maxDensityHz":        max(densities),
            "relativeMaxPosition": densities.index(max(densities)) / len(densities),
            "meanDensityHz":       sum(densities) / len(densities),
        }
        self.densityCurve[f"frame_{frameSec}_interval_{intervalSec}"] = result
        return result

    def getSelfSimilarity(self, maxVal: float = 1.0, maxLength: int = 8) -> float:
        """
        How much the rhythm repeats itself: the share of distinct inter-onset
        patterns (lengths 2..maxLength) that occur more than once, scaled to
        0..maxVal. IOIs are compared at microsecond precision.
        """
        iois = [round(d, 6) for d in self.toRelativeTimes()]
        counts = Counter(
            tuple(iois[i:i + n])
            for n in range(2, min(maxLength, len(iois) - 1) + 1)
            for i in range(len(iois) - n + 1)
        )
        if not counts:
            return 0.0
        return maxVal * sum(1 for c in counts.values() if c > 1) / len(counts)

    def analyseExternalStartTimesSec(self, starts: list[float]) -> dict:
        """
        How external event times relate to this grid:
            density : events per beat
            leaning : mean position of their nearest grid points, -1 (early) .. 1 (late)
        """
        grid = self.sorted()
        if not grid or not starts:
            return {"density": 0.0, "leaning": 0.0}
        index = {t: i for i, t in enumerate(grid)}
        positions = [index[self.quantise(s)] / (len(grid) - 1) if len(grid) > 1 else 0.5 for s in starts]
        return {
            "density": len(starts) / self.durationBeats if self.durationBeats else 0.0,
            "leaning": 2 * sum(positions) / len(positions) - 1,
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(self, path: str = "/tmp/timeGrid.mid", name: str = "timeGrid", allLayers: bool = True) -> None:
        """
        Export the grid as short notes (C4), one per position, each as long as
        the smallest inter-onset interval so none overlap; layers go to
        separate files next to `path`.
        """
        from .TemporalObject import TemporalObject
        from .Exporters import MidiExporter

        srt = self.sorted()
        if not srt:
            print("TimeGrid.toMidi: grid is empty, nothing to export.")
            return
        minDurSec = min(self.toRelativeTimes()) if len(srt) > 1 else 0.25
        container = TemporalObject(0.0, data={"bpm": self.bpm, "ticksPerBeat": self.ticksPerBeat})
        for t in srt:
            container.addChild(TemporalObject(t, minDurSec, data={
                "pitchMidi": 60.0, "pitchwheel": (0.0, 0.0), "dynamicdB": 80.0,
                "bpm": self.bpm, "ticksPerBeat": self.ticksPerBeat,
            }))
        container.export(MidiExporter(path, trackName=name))
        print(f"TimeGrid: saved -> {path}")

        if allLayers:
            for key, layer in self.layers.items():
                if isinstance(layer, TimeGrid):
                    layer.toMidi(path[:-4] + key.replace("/", "_by") + ".mid", key, allLayers=False)

    def parseMidi(self, path: str = "/tmp/timeGrid.mid", name: str = "timeGrid", allLayers: bool = True) -> None:
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
