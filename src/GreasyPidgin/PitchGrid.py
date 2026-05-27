"""
PitchGrid.py

A PitchGrid is a concrete set of MIDI float values derived from a TuningSystem
within a register (lowestPitch, highestPitch).

MIDI floats are the primary unit. They are universal:
    69.0 = A4 always
    60.0 = C4 always
    non-integer values = microtonal pitches
    values > 127 = pitches above standard MIDI range (valid for BP etc.)

referenceAHz is only used when converting to Hz for audio output.

Constructors
------------
PitchGrid(values, ...)
    Direct construction from MIDI floats, SPN strings, or Hz floats.

PitchGrid.fromTuningSystem(ts, lowestPitch, highestPitch, ...)
    All pitches of a TuningSystem within a register.

PitchGrid.fromMask(ts, maskName, lowestPitch, highestPitch,
                   tuningSystemRoot, scaleRoot, ...)
    Pitches filtered by a ScaleMask with root transposition.

PitchGrid.fromCorrelation(targetPitch, lowestPitch, highestPitch, ...)
    Best-fitting TuningSystem + ScaleMask for a set of target pitches.

Example
-------
    # E Dorian, tuning rooted on Bb, Werckmeister I, A=419 Hz, E4-E5
    pg = PitchGrid.fromMask(
        'werckmeister1', 'dorian',
        'e4', 'e5',
        'bf3', 'e4',
        referenceAHz = 419,
    )
    pg.toMidi('/tmp/dorian.mid')
"""

from GreasyPidgin.Grid import Grid
from GreasyPidgin.Pitch import mtof, forceIntoRangeMidi
from GreasyPidgin.TuningSystemAndScaleMask import (
    TuningSystem, ScaleMask, TUNING_SYSTEMS,
    _toMidi, _circDist,
)


# ---------------------------------------------------------------------------
# PitchGrid
# ---------------------------------------------------------------------------

class PitchGrid(Grid):
    """
    A set of MIDI floats representing a concrete pitch grid.

    Attributes
    ----------
    lowestPitch, highestPitch : float
    referenceAHz : float
        Physical A4 frequency — used only for MIDI↔Hz conversion.
    tuningSystemName : str
    maskName : str | None
    tuningSystemRoot : float | None
    scaleRoot : float | None
    """

    def __init__(
        self,
        values: list | None = None,
        *,
        referenceAHz: float = 440.0,
    ) -> None:
        if values is None:
            values = []
        converted = [_toMidi(v, referenceAHz) for v in values]
        super().__init__(converted)

        self.lowestPitch          = min(self) if self else 0.0
        self.highestPitch         = max(self) if self else 0.0
        self.referenceAHz        = referenceAHz
        self.tuningSystemName    = "undefined"
        self.maskName            = None
        self.tuningSystemRoot = None
        self.scaleRoot       = None

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def fromTuningSystem(
        cls,
        ts: "TuningSystem | str",
        lowestPitch: float | str = 48.0,
        highestPitch: float | str = 84.0,
        tuningSystemRoot: float | str | None = None,
        *,
        pitchUnit: str = 'midi',
        referenceAHz: float = 440.0,
    ) -> "PitchGrid":
        """
        All pitches of *ts* within [lowestPitch, highestPitch].

        Parameters
        ----------
        ts : TuningSystem | str
        lowestPitch, highestPitch, tuningSystemRoot : float | str
            Register bounds and tuning anchor.
        pitchUnit : str
            Unit for all pitch inputs: 'midi' (default), 'hz', or 'spn'.
        referenceAHz : float
            Physical A4 — used for Hz / SPN conversion.

        Examples
        --------
        >>> PitchGrid.fromTuningSystem('edo12', 'c3', 'c6', 'c4', pitchUnit='spn')
        >>> PitchGrid.fromTuningSystem('meantoneQC', 20, 120, 60, pitchUnit='midi')
        >>> PitchGrid.fromTuningSystem('werckmeister1', 220.0, 1760.0, 261.63, pitchUnit='hz')
        """
        ts   = _resolveTS(ts)
        low  = _toMidi(lowestPitch,  referenceAHz, pitchUnit)
        high = _toMidi(highestPitch, referenceAHz, pitchUnit)

        pitches = ts.generatePitches(
            low, high,
            referenceAHz         = referenceAHz,
            tuningSystemRoot = (
                _toMidi(tuningSystemRoot, referenceAHz, pitchUnit)
                if tuningSystemRoot is not None else None
            ),
        )

        pg = cls(pitches, referenceAHz=referenceAHz)
        pg.lowestPitch           = low
        pg.highestPitch          = high
        pg.tuningSystemName     = ts.name
        pg.tuningSystemRoot = (
            _toMidi(tuningSystemRoot, referenceAHz, pitchUnit)
            if tuningSystemRoot is not None else None
        )
        return pg

    @classmethod
    def fromMask(
        cls,
        ts: "TuningSystem | str",
        maskName: str,
        lowestPitch: float | str = 48.0,
        highestPitch: float | str = 84.0,
        tuningSystemRoot: float | str | None = None,
        scaleRoot: float | str | None = None,
        *,
        pitchUnit: str = 'midi',
        referenceAHz: float = 440.0,
        useAscending: bool = False,
    ) -> "PitchGrid":
        """
        Pitches of *ts* filtered by *maskName* with optional root transposition.

        Parameters
        ----------
        ts : TuningSystem | str
        maskName : str
        lowestPitch, highestPitch : float | str
            Register bounds.
        tuningSystemRoot : float | str | None
            Note that becomes index 0 of the pitch class list (the key).
        scaleRoot : float | str | None
            Note where the mask pattern begins (the mode root).
        pitchUnit : str
            Unit for all pitch inputs: 'midi' (default), 'hz', or 'spn'.
        referenceAHz : float
            Physical A4.
        useAscending : bool
            Use ascending mask form if available.

        Examples
        --------
        # E Dorian, tuning rooted on Bb, Werckmeister I, A=419
        >>> PitchGrid.fromMask(
        ...     'werckmeister1', 'dorian',
        ...     'e4', 'e5',
        ...     'bf3', 'e4',
        ...     referenceAHz=419,
        ... )

        # Ionian from C, edo12, standard pitch
        >>> PitchGrid.fromMask('edo12', 'ionian', 'c3', 'c6', 'c4', 'c4')
        """
        ts = _resolveTS(ts)

        if maskName not in ts.scaleMasks:
            raise KeyError(
                f"PitchGrid.fromMask: mask '{maskName}' not in '{ts.name}'. "
                f"Available: {list(ts.scaleMasks.keys())}"
            )

        low  = _toMidi(lowestPitch,  referenceAHz, pitchUnit)
        high = _toMidi(highestPitch, referenceAHz, pitchUnit)
        mask = ts.scaleMasks[maskName]

        pitches = ts.generatePitches(
            low, high,
            referenceAHz         = referenceAHz,
            tuningSystemRoot = (
                _toMidi(tuningSystemRoot, referenceAHz, pitchUnit)
                if tuningSystemRoot is not None else None
            ),
            scaleRoot        = (
                _toMidi(scaleRoot, referenceAHz, pitchUnit)
                if scaleRoot is not None else None
            ),
            mask                 = mask,
            useAscending         = useAscending,
        )

        pg = cls(pitches, referenceAHz=referenceAHz)
        pg.lowestPitch           = low
        pg.highestPitch          = high
        pg.tuningSystemName     = ts.name
        pg.maskName             = maskName
        pg.tuningSystemRoot = (
            _toMidi(tuningSystemRoot, referenceAHz, pitchUnit)
            if tuningSystemRoot is not None else None
        )
        pg.scaleRoot = (
            _toMidi(scaleRoot, referenceAHz, pitchUnit)
            if scaleRoot is not None else None
        )
        return pg

    @classmethod
    def fromCorrelation(
        cls,
        targetPitch: list[float | str],
        lowestPitch: float | str = 48.0,
        highestPitch: float | str = 84.0,
        *,
        pitchUnit: str = 'midi',
        referenceAHz: float = 440.0,
        possibleSystems: list[str] | None = None,
        possibleMasks: list[str] | None = None,
        possibleScaleRoots: list[float | str] | None = None,
        applyMask: bool = True,
    ) -> "PitchGrid":
        """
        Find the best-fitting TuningSystem + ScaleMask for *targetPitch*.

        Correlation is transposition-invariant (pitch classes normalised
        by subtracting the minimum before comparison).

        Parameters
        ----------
        targetPitch : list[float | str]
            Reference pitches as MIDI floats or SPN strings.
        lowestPitch, highestPitch : float | str
            Register for the output grid.
        pitchUnit : str
        referenceAHz : float
        possibleSystems : list[str] | None
            Restrict search. None = all systems.
        possibleMasks : list[str] | None
            Restrict search. None = all masks per system.
        possibleScaleRoots : list[float | str] | None
            If set, the best-matching scale root from this list is used
            when building the output grid. Accepts the same pitchUnit as
            the rest of the constructor. None = no scaleRoot applied.
        applyMask : bool
            If False, return full TuningSystem grid without mask.
        """
        if not targetPitch:
            raise ValueError("PitchGrid.fromCorrelation: targetPitch is empty")

        low      = _toMidi(lowestPitch,  referenceAHz, pitchUnit)
        high     = _toMidi(highestPitch, referenceAHz, pitchUnit)
        tgtPitch = [_toMidi(p, referenceAHz, pitchUnit) for p in targetPitch]

        # convert possibleScaleRoots to MIDI using the same pitchUnit
        scaleRootsMidi: list[float] | None = None
        if possibleScaleRoots is not None:
            scaleRootsMidi = [_toMidi(r, referenceAHz, pitchUnit)
                              for r in possibleScaleRoots]

        systemNames = possibleSystems or list(TUNING_SYSTEMS.keys())
        candidates: list[tuple[str, str]] = [
            (tsName, mName)
            for tsName in systemNames
            if tsName in TUNING_SYSTEMS
            for mName in (possibleMasks or list(TUNING_SYSTEMS[tsName].scaleMasks.keys()))
            if mName in TUNING_SYSTEMS[tsName].scaleMasks
        ]

        if not candidates:
            raise ValueError("PitchGrid.fromCorrelation: no valid candidates")

        def pcNorm(midi_list: list[float], interval: float) -> list[float]:
            pcs = sorted(set(round(m % interval, 6) for m in midi_list))
            mn  = pcs[0] if pcs else 0.0
            return [round(p - mn, 6) for p in pcs]

        def error(tgtNorm: list[float], maskPCs: list[float], interval: float) -> float:
            if not tgtNorm or not maskPCs:
                return float("inf")
            mn       = maskPCs[0]
            maskNorm = [round(p - mn, 6) for p in maskPCs]
            return sum(
                min(_circDist(p, q, interval) ** 2 for q in maskNorm)
                for p in tgtNorm
            ) / len(tgtNorm)

        best: tuple[float, str, str] | None = None
        for tsName, mName in candidates:
            ts       = TUNING_SYSTEMS[tsName]
            interval = ts.repeatIntervalSemitones or 12.0
            tgtNorm  = pcNorm(tgtPitch, interval)
            maskPCs  = ts.scaleMasks[mName].pitchClasses(ts)
            if not maskPCs:
                continue
            err = error(tgtNorm, maskPCs, interval)
            if best is None or err < best[0]:
                best = (err, tsName, mName)

        if best is None:
            raise ValueError("PitchGrid.fromCorrelation: no match found")

        _, bestTSName, bestMaskName = best

        # find best scale root if candidates were provided
        bestScaleRoot: float | None = None
        if scaleRootsMidi is not None and applyMask:
            ts       = TUNING_SYSTEMS[bestTSName]
            interval = ts.repeatIntervalSemitones or 12.0
            tgtNorm  = pcNorm(tgtPitch, interval)
            bestRootErr = float("inf")
            for rootMidi in scaleRootsMidi:
                pg  = cls.fromMask(bestTSName, bestMaskName, low, high,
                                   scaleRoot=rootMidi,
                                   pitchUnit='midi',
                                   referenceAHz=referenceAHz)
                pcs = sorted(set(round(m % interval, 6) for m in pg))
                if not pcs:
                    continue
                err = error(tgtNorm, pcs, interval)
                if err < bestRootErr:
                    bestRootErr   = err
                    bestScaleRoot = rootMidi

        if applyMask:
            return cls.fromMask(bestTSName, bestMaskName, low, high,
                                scaleRoot=bestScaleRoot,
                                pitchUnit='midi',
                                referenceAHz=referenceAHz)
        return cls.fromTuningSystem(bestTSName, low, high,
                                    referenceAHz=referenceAHz)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def findClosestTuningSystem(
        self,
        possibleSystems: list[str] | None = None,
    ) -> list[tuple[float, str]]:
        """Rank TuningSystem candidates by pitch class correlation."""
        if not self:
            raise ValueError("PitchGrid.findClosestTuningSystem: grid is empty")

        systemNames = possibleSystems or list(TUNING_SYSTEMS.keys())
        midiList    = list(self)
        ratings: list[tuple[float, str]] = []

        for name in systemNames:
            ts       = TUNING_SYSTEMS.get(name)
            if ts is None:
                continue
            interval = ts.repeatIntervalSemitones or 12.0
            gridPCs  = sorted(set(round(m % interval, 6) for m in midiList))
            sysPCs   = ts.pitchClasses
            if not gridPCs or not sysPCs:
                continue
            mn       = gridPCs[0]
            norm     = [round(p - mn, 6) for p in gridPCs]
            sMin     = sysPCs[0]
            sNorm    = [round(p - sMin, 6) for p in sysPCs]
            e = sum(
                min(_circDist(p, q, interval) ** 2 for q in sNorm)
                for p in norm
            ) / len(norm)
            ratings.append((round(e, 8), name))

        return sorted(ratings)

    def findClosestMask(
        self,
        tuningSystemName: str = "edo12",
        possibleMasks: list[str] | None = None,
    ) -> list[tuple[float, str]]:
        """Rank ScaleMask candidates within *tuningSystemName* by correlation."""
        if not self:
            raise ValueError("PitchGrid.findClosestMask: grid is empty")

        ts = TUNING_SYSTEMS.get(tuningSystemName)
        if ts is None:
            raise KeyError(f"PitchGrid.findClosestMask: unknown system '{tuningSystemName}'")

        interval = ts.repeatIntervalSemitones or 12.0
        midiList = list(self)
        gridPCs  = sorted(set(round(m % interval, 6) for m in midiList))
        mn       = gridPCs[0] if gridPCs else 0.0
        gridNorm = [round(p - mn, 6) for p in gridPCs]

        maskNames = possibleMasks or list(ts.scaleMasks.keys())
        ratings: list[tuple[float, str]] = []

        for mName in maskNames:
            mask = ts.scaleMasks.get(mName)
            if mask is None:
                continue
            maskPCs = mask.pitchClasses(ts)
            if not maskPCs:
                continue
            mMin     = maskPCs[0]
            maskNorm = [round(p - mMin, 6) for p in maskPCs]
            e = sum(
                min(_circDist(p, q, interval) ** 2 for q in maskNorm)
                for p in gridNorm
            ) / len(gridNorm)
            ratings.append((round(e, 8), mName))

        return sorted(ratings)

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def toHzList(self) -> list[float]:
        """Return all pitches as Hz using self.referenceAHz."""
        return [mtof(m, self.referenceAHz) for m in self.sorted()]

    def toMidiList(self) -> list[float]:
        """Return sorted MIDI floats."""
        return self.sorted()

    # ------------------------------------------------------------------
    # MIDI export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/pitchGrid.mid",
        *,
        noteDurationSec: float = 2.0,
        dynamicdB: float = 80.0,
        bpm: float = 60.0,
        pitchBendRange: int = 4096,
    ) -> str:
        """Export the grid as a chromatic sequence, one note per pitch."""
        from GreasyPidgin.TemporalObject import TemporalObject
        from GreasyPidgin.Exporters import MidiExporter

        container = TemporalObject(0.0, data={"bpm": bpm})
        cur = 0.0
        for midiFloat in self.sorted():
            anchor = round(midiFloat)
            diff   = midiFloat - anchor
            container.addChild(TemporalObject(
                cur, noteDurationSec,
                data={
                    "pitchMidi":  float(anchor),
                    "pitchwheel": (diff, diff),
                    "dynamicdB":  dynamicdB,
                    "bpm":        bpm,
                },
            ))
            cur += noteDurationSec

        name = (
            f"PitchGrid_{self.tuningSystemName}"
            + (f"_{self.maskName}" if self.maskName else "")
        )
        if not path.endswith(".mid"):
            path = path + name + ".mid"

        container.export(MidiExporter(path, pitchBendRange=pitchBendRange,
                                      trackName=name))
        return path

    def makeChordFromTopNote(
        self,
        topNote: float | str,
        primaryIntervals: list[int] = [1, 7, 9],
        numPrimaryNotes: int = 4,
        numMaxNotes: int = 8,
        clusterChance: float = 0.1,
        minPitch: float | str = 48.0,
        clusterIntervals: list[float] = [-2, -1, 1, 2],
        *,
        pitchUnit: str = 'midi',
        referenceAHz: float = 440.0,
    ) -> list:
        """
        Build a chord downward from a top note using this PitchGrid as a sieve.

        Returns a list of pitches in *pitchUnit*, ready to pass directly
        to a Phonon constructor.

        Algorithm
        ---------
        1. Starting from *topNote*, walk downward by random intervals from
           *primaryIntervals*, quantising each candidate to the grid.
           No range enforcement during construction.
        2. For each primary note, with probability *clusterChance*, add a
           neighbour offset by a random value from *clusterIntervals*
           (quantised and different from the primary note itself).
        3. Force all pitches into [minPitch, topNote] via octave shifts
           before returning.
        4. Return *topNote* guaranteed first, followed by a random sample
           of the remaining notes up to *numMaxNotes* total, all converted
           back to *pitchUnit*.

        Parameters
        ----------
        topNote : float | str
            Highest note of the chord. Interpreted according to pitchUnit.
        primaryIntervals : list[int]
            Semitone intervals to step downward from each primary note.
        numPrimaryNotes : int
            Number of primary notes to generate below the top note.
        numMaxNotes : int
            Maximum total notes in the chord (including topNote).
        clusterChance : float
            Probability [0, 1] that each primary note gets a cluster neighbour.
        minPitch : float | str
            Lowest allowed pitch. Interpreted according to pitchUnit.
        clusterIntervals : list[float]
            Offsets (in semitones) to try for cluster neighbours.
            Default [-2, -1, 1, 2] for standard chromatic clusters.
            Use smaller values for microtonal systems, e.g. [-0.5, 0.5].
        pitchUnit : str
            Unit for all pitch inputs and outputs: 'midi' (default), 'hz', 'spn'.
        referenceAHz : float
            Physical A4 — used for Hz / SPN conversion.

        Returns
        -------
        list — pitches in pitchUnit, topNote first.
        """
        from random import choice, random, sample

        # convert all inputs to MIDI — internal arithmetic stays in MIDI
        topMidi = _toMidi(topNote,  referenceAHz, pitchUnit)
        loMidi  = _toMidi(minPitch, referenceAHz, pitchUnit)

        # --- step 1: primary notes (no range enforcement here) ---
        primaryChord = [topMidi]
        for _ in range(numPrimaryNotes):
            candidate = primaryChord[-1] - choice(primaryIntervals)
            primaryChord.append(self.quantise(candidate))
        primaryChord = primaryChord[1:]

        # --- step 2: cluster notes ---
        clusterNotes = []
        for pm in primaryChord:
            if random() < clusterChance:
                candidates         = [pm + iv for iv in clusterIntervals]
                candidatesQ        = set(self.quantise(c) for c in candidates)
                candidatesFiltered = list(candidatesQ - {pm})
                if candidatesFiltered:
                    clusterNotes.append(choice(candidatesFiltered))

        # --- step 3: force into range before output ---
        potentialPitches = [
            forceIntoRangeMidi(p, loMidi, topMidi)
            for p in primaryChord + clusterNotes
        ]

        # --- step 4: assemble and convert back to pitchUnit ---
        n          = min(numMaxNotes - 1, len(potentialPitches))
        chosenMidi = [topMidi] + (sample(potentialPitches, n) if n > 0 else [])

        if pitchUnit == 'hz':
            return [mtof(m, referenceAHz) for m in chosenMidi]
        elif pitchUnit == 'spn':
            from .Pitch import mtospn
            return [mtospn(m) for m in chosenMidi]
        else:
            return chosenMidi

    def parseMidi(self, path: str = "/tmp/", pitchBendRange: int = 4096) -> str:
        """Legacy alias for toMidi()."""
        return self.toMidi(path, pitchBendRange=pitchBendRange)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        if not self:
            return "PitchGrid(empty)"
        preview = [round(m, 3) for m in self.sorted()[:6]]
        more    = "..." if len(self) > 6 else ""
        tsRoot  = round(self.tuningSystemRoot, 3) if self.tuningSystemRoot is not None else None
        sRoot   = round(self.scaleRoot, 3) if self.scaleRoot is not None else None
        return (
            f"PitchGrid\n"
            f"   size          : {len(self)}\n"
            f"   range         : {round(self.lowestPitch,3)} - {round(self.highestPitch,3)} MIDI\n"
            f"   system        : '{self.tuningSystemName}'\n"
            f"   mask          : {self.maskName!r}\n"
            f"   tsRoot (MIDI) : {tsRoot}\n"
            f"   scaleRoot     : {sRoot}\n"
            f"   refA          : {self.referenceAHz} Hz\n"
            f"   preview       : {preview}{' ...' if more else ''}\n"
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _resolveTS(ts: "TuningSystem | str") -> TuningSystem:
    if isinstance(ts, str):
        if ts not in TUNING_SYSTEMS:
            raise KeyError(
                f"PitchGrid: unknown tuning system '{ts}'. "
                f"Available: {list(TUNING_SYSTEMS.keys())}"
            )
        return TUNING_SYSTEMS[ts]
    return ts