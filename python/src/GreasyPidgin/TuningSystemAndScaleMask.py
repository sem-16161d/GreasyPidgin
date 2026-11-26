"""
TuningSystemAndScaleMask.py

Internal representation
-----------------------
All pitch classes are stored as MIDI float offsets from 0 (the system's
unison, typically C). MIDI float is universal:

    midi = 69 + 12 * log2(hz / 440)

This works for any frequency — BP pitches extend above 127, Studie II
pitches are non-integer floats, historical temperaments have fractional
semitone values. The 88-key range is just a convention.

Three parameters control pitch generation (fully independent):

    referenceAHz : float
        Physical frequency of A4. Used when converting Hz <-> MIDI
        (pitchUnit='hz' inputs, audio output). Does NOT affect pitch class
        arithmetic.
        Default: 440.0 Hz.
        Use 415 for baroque, 466 for high baroque, 432 for alternative tuning.

    tuningSystemRoot : float | str | None
        The written note that becomes index 0 of the pitch class list.
        Pitch classes are rotated so this note is first.
        None = no rotation (system's natural root = C, midi 0 mod interval).

    scaleRoot : float | str | None
        Which note in the tuningSystemRoot-relative list the mask begins on.
        The list is further rotated so this note is at position 0 before
        mask indices are applied.
        None = index 0 of the tuningSystemRoot-shifted list.

Pitch inputs are MIDI floats or SPN strings ('bf3'); PitchGrid constructors
read numbers as Hz with pitchUnit='hz'.

Repeat interval
---------------
    Octave   : repeatIntervalSemitones = 12.0
    Tritave  : repeatIntervalSemitones = 12 * log2(3) ≈ 19.02
    Studie II: repeatIntervalSemitones = None (non-repeating); an equal-step
               system then repeats its step instead (stepSemitones): every
               anchor + k * step is a pitch, with no octave identity

Three constructors
------------------
TuningSystem.fromEDO(n, ...)
    n equal divisions of the octave. Shorthand for fromRatio(2^(1/n), n).

TuningSystem.fromRatio(stepRatio, stepsPerGroup, ...)
    Any equal-division system: EDO, BP, Studie II, Stria.

TuningSystem.fromSemitones(semitones, ...)
    Explicit list of semitone offsets from unison. JI, historical temperaments,
    maqam approximations — anything expressible as a list of interval sizes.

TuningSystem.fromHz(frequencies, referenceHz, ...)
    Empirically measured tunings (gamelan, instrument-specific).

Example
-------
    # E Dorian, tuning rooted on Bb, Werckmeister I, A=419, C3-C6
    TUNING_SYSTEMS["werckmeister1"].generatePitches(
        48, 84,                          # C3=48, C6=84 in MIDI
        tuningSystemRoot = "bf3",    # Bb3 = 58.0
        scaleRoot        = "e4",     # E4  = 64.0
        mask                 = TUNING_SYSTEMS["werckmeister1"].scaleMasks["dorian"],
    )

    # Same call with the original cents verification:
    # pc = [0, 0.9, 1.92, 2.94, 3.9, 4.98, 5.88, 6.96, 7.92, 8.88, 9.96, 10.92]
    # root = 58 (Bb)
    # shifted = sorted([(p - 58) % 12 for p in [58+pc_i for pc_i in pc]])
    # rotated so E (index 6 of shifted) is first
    # dorian mask [0,2,3,5,7,9,10] applied
"""

from __future__ import annotations
import math
from GreasyPidgin.Pitch import spntom, mtof, ftom


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _toMidi(value: float | str, referenceAHz: float = 440.0, pitchUnit: str = 'midi') -> float:
    """
    Convert a pitch value to a MIDI float.

    pitchUnit : 'midi' — value is a MIDI float (default)
                'hz'   — value is a frequency in Hz
                'spn'  — value is a SPN string ('c4', 'bf3', 'dqs4')
    Strings are always read as SPN and, in 'spn' mode, numbers as MIDI,
    so a numeric default (e.g. minPitch=48.0) works in every mode.
    """
    if isinstance(value, str):
        return float(spntom(value))
    if pitchUnit == 'hz':
        return float(ftom(float(value), referenceAHz))
    if pitchUnit in ('midi', 'spn'):
        return float(value)
    raise ValueError(f"unknown pitchUnit '{pitchUnit}' (use 'midi', 'hz' or 'spn')")


def _circDist(a: float, b: float, interval: float) -> float:
    """Circular distance within a repeat interval (in semitones)."""
    d = abs((a - b) % interval)
    return min(d, interval - d)


# ---------------------------------------------------------------------------
# Pitch class manipulation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ScaleMask
# ---------------------------------------------------------------------------

class ScaleMask:
    """
    A named subset of step indices within a TuningSystem.

    indices are applied AFTER tuningSystemRoot + scaleRoot rotation.

    Parameters
    ----------
    name : str
    indices : list[int]
        0-based step indices into the (rotated) pitch class list.
    description : str
    ascending : list[int] | None
        Separate ascending indices for scales with different ascending/
        descending forms (melodic minor, maqamat, ragas).
    """

    def __init__(
        self,
        name: str,
        indices: list[int],
        *,
        description: str = "",
        ascending: list[int] | None = None,
    ) -> None:
        self.name        = str(name)
        self.indices     = list(indices)
        self.description = str(description)
        self.ascending   = list(ascending) if ascending is not None else None

    def pitchClasses(
        self,
        ts: "TuningSystem",
        *,
        useAscending: bool = False,
    ) -> list[float]:
        """Return the MIDI semitone offsets of this mask's steps within *ts*."""
        indices = (
            self.ascending
            if (useAscending and self.ascending is not None)
            else self.indices
        )
        return [ts.pitchClasses[i] for i in indices
                if i < len(ts.pitchClasses)]

    def __repr__(self) -> str:
        asc = f", ascending={self.ascending}" if self.ascending else ""
        return f"ScaleMask({self.name!r}, indices={self.indices}{asc})"


# ---------------------------------------------------------------------------
# TuningSystem
# ---------------------------------------------------------------------------

class TuningSystem:
    """
    An abstract pitch space defined by MIDI semitone offsets from C (= 0).

    Attributes
    ----------
    name : str
    pitchClasses : list[float]
        Semitone offsets from 0, sorted ascending, within one repeat interval.
        For non-repeating systems this is the full finite pitch set.
    repeatIntervalSemitones : float | None
        12.0 = octave, ~19.02 = tritave (BP), None = non-repeating.
    scaleMasks : dict[str, ScaleMask]
    metadata : dict
    """

    def __init__(
        self,
        name: str,
        pitchClasses: list[float],
        *,
        repeatIntervalSemitones: float | None = 12.0,
        scaleMasks: dict[str, ScaleMask] | None = None,
        metadata: dict | None = None,
        stepSemitones: float | None = None,
    ) -> None:
        self.name                    = str(name)
        # equal step of a non-repeating equal-division system (fromRatio);
        # None for systems that are a finite list of pitches
        self.stepSemitones           = float(stepSemitones) if stepSemitones else None
        self.repeatIntervalSemitones = (
            float(repeatIntervalSemitones)
            if repeatIntervalSemitones is not None else None
        )
        # within one repeat interval: a value equal to the interval (e.g. 2/1)
        # is the next period's unison, not an extra pitch class
        ri = self.repeatIntervalSemitones
        self.pitchClasses = sorted({round(float(p) % ri, 10) if ri else float(p) for p in pitchClasses})
        self.scaleMasks = scaleMasks or {}
        self.metadata   = metadata   or {}

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def fromEDO(
        cls,
        n: int,
        *,
        name: str | None = None,
        scaleMasks: dict[str, ScaleMask] | None = None,
        metadata: dict | None = None,
    ) -> "TuningSystem":
        """
        n equal divisions of the octave.

        >>> TuningSystem.fromEDO(12)   # 12-EDO
        >>> TuningSystem.fromEDO(24)   # quarter-tones
        >>> TuningSystem.fromEDO(31)
        """
        step = 12.0 / n
        pc   = [round(i * step, 10) for i in range(n)]
        return cls(
            name or f"edo{n}", pc,
            repeatIntervalSemitones=12.0,
            scaleMasks=scaleMasks,
            metadata=metadata or {"description": f"{n}-tone equal temperament"},
        )

    @classmethod
    def fromRatio(
        cls,
        name: str,
        stepRatio: float,
        stepsPerGroup: int,
        *,
        groupRatio: float | None = None,
        repeatInterval: float | None = None,
        scaleMasks: dict[str, ScaleMask] | None = None,
        metadata: dict | None = None,
    ) -> "TuningSystem":
        """
        Equal-division tuning from a frequency ratio.

        stepRatio : float
            Frequency ratio between adjacent steps.
        stepsPerGroup : int
            Steps per group/period.
        groupRatio : float | None
            Frequency ratio between groups.
            None = auto-derived as stepRatio^stepsPerGroup.
            Set explicitly for Studie II / Stria where groupRatio = stepRatio.
        repeatInterval : float | None | False
            Repeat interval in semitones.
            None  = use groupRatio converted to semitones.
            False = non-repeating.

        Examples
        --------
        >>> TuningSystem.fromRatio("bohlenPierce", 3**(1/13), 13)
        >>> TuningSystem.fromRatio("studieII", 5**(1/5), 5, groupRatio=5**(1/5))
        >>> phi = (1+5**0.5)/2
        >>> TuningSystem.fromRatio("stria", phi, 1, groupRatio=phi, repeatInterval=False)
        """
        if groupRatio is None:
            groupRatio = stepRatio ** stepsPerGroup

        # convert ratios to semitones: semitones = 12 * log2(ratio)
        stepSemitones  = 12.0 * math.log2(stepRatio)
        groupSemitones = 12.0 * math.log2(groupRatio)

        pc = [round(i * stepSemitones, 10) for i in range(stepsPerGroup)]

        if repeatInterval is None:
            repeatIntervalSemitones = groupSemitones
        elif repeatInterval is False:
            repeatIntervalSemitones = None
        else:
            repeatIntervalSemitones = float(repeatInterval)

        return cls(
            name, pc,
            repeatIntervalSemitones=repeatIntervalSemitones,
            scaleMasks=scaleMasks,
            metadata=metadata,
            stepSemitones=stepSemitones if repeatIntervalSemitones is None else None,
        )

    @classmethod
    def fromSemitones(
        cls,
        name: str,
        semitones: list[float],
        *,
        repeatInterval: float | None = None,
        scaleMasks: dict[str, ScaleMask] | None = None,
        metadata: dict | None = None,
    ) -> "TuningSystem":
        """
        Tuning from explicit semitone offsets from unison.

        Suitable for JI, historical temperaments, maqam approximations.
        Unison (0.0) is added automatically if absent.
        The repeat interval is the last value if it is >= 12.0 (that value
        is then the boundary, not a pitch), otherwise the octave (12.0),
        unless overridden.

        Examples
        --------
        # Werckmeister I (cents / 100 = semitones)
        >>> TuningSystem.fromSemitones("werckmeister1",
        ...     [0, 0.9, 1.92, 2.94, 3.9, 4.98, 5.88,
        ...      6.96, 7.92, 8.88, 9.96, 10.92])

        # Ptolemy's JI major (ratio → semitones via 12*log2)
        >>> import math
        >>> ji = [12*math.log2(r) for r in [1,9/8,5/4,4/3,3/2,5/3,15/8]]
        >>> TuningSystem.fromSemitones("JI_major", ji)
        """
        pc = sorted(set(float(s) for s in semitones))
        if pc[0] != 0.0:
            pc.insert(0, 0.0)

        if repeatInterval is None:
            if pc[-1] >= 12.0:
                # last value IS the repeat boundary (e.g. 2/1 ratio list)
                repeatIntervalSemitones = float(pc[-1])
                pc = [p for p in pc if p < repeatIntervalSemitones]
            else:
                repeatIntervalSemitones = 12.0
        else:
            repeatIntervalSemitones = float(repeatInterval)

        return cls(
            name, pc,
            repeatIntervalSemitones=repeatIntervalSemitones,
            scaleMasks=scaleMasks,
            metadata=metadata,
        )

    @classmethod
    def fromHz(
        cls,
        name: str,
        frequencies: list[float],
        referenceHz: float,
        *,
        repeatIntervalHz: float | None = None,
        scaleMasks: dict[str, ScaleMask] | None = None,
        metadata: dict | None = None,
    ) -> "TuningSystem":
        """
        Tuning from explicit Hz values (empirically measured).

        Frequencies are converted to semitone offsets from referenceHz
        using the standard MIDI formula.

        Examples
        --------
        >>> TuningSystem.fromHz("slendro",
        ...     [260.4, 295.2, 325.0, 390.5, 433.2],
        ...     referenceHz=260.4)
        """
        freqs = sorted(float(f) for f in frequencies)
        pc    = [12.0 * math.log2(f / referenceHz) for f in freqs]

        repeatIntervalSemitones = (
            12.0 * math.log2(repeatIntervalHz / referenceHz)
            if repeatIntervalHz is not None else None
        )

        return cls(
            name, pc,
            repeatIntervalSemitones=repeatIntervalSemitones,
            scaleMasks=scaleMasks,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Pitch generation
    # ------------------------------------------------------------------

    def generatePitches(
        self,
        lowestPitch: float | str,
        highestPitch: float | str,
        *,
        referenceAHz: float = 440.0,
        tuningSystemRoot: float | str | None = None,
        scaleRoot: float | str | None = None,
        mask: "ScaleMask | None" = None,
        useAscending: bool = False,
    ) -> list[float]:
        """
        Generate MIDI float values within [lowestPitch, highestPitch].

        Algorithm
        ---------
        1. Generate the full chromatic list of this tuning system in the
           register, anchored on tuningSystemRoot.
        2. If scaleRoot given, find its index in that list.
        3. If mask given, sieve: keep only pitches whose position relative
           to scaleRoot index is in the mask indices (mod nSteps).
        4. Return the surviving pitches.

        No interval arithmetic — just a sieve through the generated list.

        Parameters
        ----------
        lowestPitch, highestPitch : float | str
            Register bounds as MIDI float or SPN string.
        referenceAHz : float
            Used only for SPN → MIDI conversion.
        tuningSystemRoot : float | str | None
            The note that anchors the tuning system (index 0 of pitch classes).
            None = C (midi 0 mod interval).
        scaleRoot : float | str | None
            The note where the mask sieve starts.
            None = start from index 0.
        mask : ScaleMask | None
            Sieve pattern. None = return full chromatic.
        useAscending : bool
            Use ascending mask form if available.

        Example
        -------
        # E Dorian in Werckmeister I, tuning rooted on C, E4-F5
        >>> ts.generatePitches(
        ...     "e4", "f5",
        ...     tuningSystemRoot = "c4",
        ...     scaleRoot        = "e4",
        ...     mask                 = ts.scaleMasks["dorian"],
        ... )
        # Produces: E(63.90) F#(65.88) G(66.96) A(68.88) B(70.92) C#(72.90) D(73.92)
        """
        _EPS = 1e-6
        low  = _toMidi(lowestPitch,  referenceAHz)
        high = _toMidi(highestPitch, referenceAHz)

        nSteps   = len(self.pitchClasses)

        # --- step 1: determine the absolute MIDI anchor ---
        # anchor = the absolute MIDI note that pc[0]=0.0 corresponds to.
        if tuningSystemRoot is not None:
            anchor = _toMidi(tuningSystemRoot, referenceAHz)
        else:
            anchor = 0.0  # C, MIDI 0

        # --- step 2: generate full chromatic list in register ---
        chromatic: list[tuple[float, int]] = []  # (midiValue, pcIndex)
        def keep(midi, i):
            if low - _EPS <= midi <= high + _EPS:
                chromatic.append((round(midi, 8), i))

        if self.repeatIntervalSemitones is not None or self.stepSemitones is not None:
            # repeating: midi = anchor + g*interval + pc[i] for every period g;
            # non-repeating equal steps: midi = anchor + k*step, step index k mod nSteps
            if self.repeatIntervalSemitones is not None:
                interval, classes = self.repeatIntervalSemitones, self.pitchClasses
            else:
                interval, classes = self.stepSemitones, [0.0]
            gMin = math.floor((low  - anchor) / interval) - 1
            gMax = math.ceil( (high - anchor) / interval) + 1
            for g in range(gMin, gMax + 1):
                for i, p in enumerate(classes):
                    keep(anchor + g * interval + p, i if classes is self.pitchClasses else g % nSteps)
        else:
            # non-repeating finite set: each pitch exactly once
            for i, p in enumerate(self.pitchClasses):
                keep(anchor + p, i)
        chromatic.sort(key=lambda x: x[0])

        if not chromatic:
            return []

        # --- step 3: find scaleRoot index in the chromatic list ---
        if scaleRoot is not None:
            srPitch  = _toMidi(scaleRoot, referenceAHz)
            # find the position in chromatic nearest to srPitch
            srPos   = min(range(len(chromatic)),
                         key=lambda i: abs(chromatic[i][0] - srPitch))
            # the pc index of the scale root
            srPCIdx = chromatic[srPos][1]
        else:
            srPos   = 0
            srPCIdx = chromatic[0][1]

        # --- step 4: sieve using mask ---
        if mask is None:
            return [m for m, _ in chromatic]

        indices = (
            mask.ascending
            if (useAscending and mask.ascending is not None)
            else mask.indices
        )
        maskSet = set(indices)

        result = []
        for midi, pcIdx in chromatic:
            # position of this pitch relative to scaleRoot (mod nSteps)
            relPos = (pcIdx - srPCIdx) % nSteps
            if relPos in maskSet:
                result.append(midi)
        return result

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def midiToHz(self, midi: float, referenceAHz: float = 440.0) -> float:
        return mtof(midi, referenceAHz)

    def hzToMidi(self, hz: float, referenceAHz: float = 440.0) -> float:
        return ftom(hz, referenceAHz)

    def pitchClassOf(self, midi: float) -> float | None:
        """MIDI pitch class within the repeat interval. None if non-repeating."""
        if self.repeatIntervalSemitones is None:
            return None
        return midi % self.repeatIntervalSemitones

    # ------------------------------------------------------------------
    # ScaleMask management
    # ------------------------------------------------------------------

    def addMask(self, mask: ScaleMask) -> None:
        self.scaleMasks[mask.name] = mask

    def addMasks(self, masks: list[ScaleMask]) -> None:
        for m in masks:
            self.addMask(m)

    def __repr__(self) -> str:
        ri = (f"{self.repeatIntervalSemitones:.4f} semitones"
              if self.repeatIntervalSemitones else "non-repeating")
        return (
            f"TuningSystem({self.name!r}, "
            f"steps={len(self.pitchClasses)}, "
            f"repeat={ri}, "
            f"masks={list(self.scaleMasks.keys())})"
        )


# ---------------------------------------------------------------------------
# Predefined tuning systems
# ---------------------------------------------------------------------------

TUNING_SYSTEMS: dict[str, TuningSystem] = {}

def _reg(ts: TuningSystem) -> TuningSystem:
    TUNING_SYSTEMS[ts.name] = ts
    return ts


# ------------------------------------------------------------------
# Equal divisions of the octave
# ------------------------------------------------------------------

edo12 = _reg(TuningSystem.fromEDO(12))
edo24 = _reg(TuningSystem.fromEDO(24))
edo31 = _reg(TuningSystem.fromEDO(31))
edo53 = _reg(TuningSystem.fromEDO(53))
edo72 = _reg(TuningSystem.fromEDO(72))


# ------------------------------------------------------------------
# Non-octave systems
# ------------------------------------------------------------------

_reg(TuningSystem.fromRatio("bohlenPierce", 3**(1/13), 13,
    metadata={"description": "Bohlen-Pierce, tritave repeat (~19.02 semitones)"}))

_reg(TuningSystem.fromRatio("studieII", 5**(1/5), 5,
    groupRatio=5**(1/5), repeatInterval=False,
    metadata={"description": "Stockhausen Studie II, self-similar 5^(1/5)",
              "source": "Karlheinz Stockhausen, Studie II (1954)"}))

_phi = (1 + 5**0.5) / 2
_reg(TuningSystem.fromRatio("stria", _phi, 1,
    groupRatio=_phi, repeatInterval=False,
    metadata={"description": "Chowning Stria, golden ratio phi",
              "source": "John Chowning, Stria (1977)"}))


# ------------------------------------------------------------------
# Historical temperaments (semitone offsets = cents / 100)
# ------------------------------------------------------------------

_reg(TuningSystem.fromSemitones("werckmeister1",
    [0, 0.90, 1.92, 2.94, 3.90, 4.98, 5.88, 6.96, 7.92, 8.88, 9.96, 10.92],
    metadata={"description": "Werckmeister I (III)"}))

_reg(TuningSystem.fromSemitones("werckmeister2",
    [0, 0.82, 1.96, 2.94, 3.92, 4.98, 5.88, 6.94, 7.84, 8.90, 10.04, 10.86],
    metadata={"description": "Werckmeister II (IV)"}))

_reg(TuningSystem.fromSemitones("werckmeister3",
    [0, 0.96, 2.04, 3.00, 3.96, 5.04, 6.00, 7.02, 7.92, 9.00, 10.02, 10.98],
    metadata={"description": "Werckmeister III (V)"}))

_reg(TuningSystem.fromSemitones("werckmeister4",
    [0, 0.90, 1.87, 2.98, 3.95, 4.98, 5.95, 6.98, 7.92, 8.93, 10.00, 10.97],
    metadata={"description": "Werckmeister IV (VI)"}))

_reg(TuningSystem.fromSemitones("kirnberger2",
    [0, 0.90, 2.04, 2.94, 3.86, 4.98, 5.92, 7.02, 7.92, 8.95, 9.96, 10.88],
    metadata={"description": "Kirnberger II"}))

_reg(TuningSystem.fromSemitones("kirnberger3",
    [0, 0.90, 1.95, 2.94, 3.86, 4.98, 5.90, 6.97, 7.92, 8.92, 9.96, 10.88],
    metadata={"description": "Kirnberger III"}))

_reg(TuningSystem.fromSemitones("meantoneQC",
    [0, 0.76, 1.93, 3.10, 3.86, 5.03, 5.79, 6.97, 8.14, 8.90, 10.07, 10.83],
    metadata={"description": "Quarter-comma meantone"}))

_reg(TuningSystem.fromSemitones("pythagorean",
    [0, 1.14, 2.04, 2.94, 4.08, 4.98, 6.12, 7.02, 8.16, 9.06, 9.96, 11.10],
    metadata={"description": "Pythagorean tuning"}))

_reg(TuningSystem.fromSemitones("zeta12",
    [0, 1.39, 2.04, 2.67, 3.47, 4.98, 6.37, 7.02, 7.65, 8.41, 9.69, 10.49],
    metadata={"description": "Zeta-12: Margo Schulter, Centaur-inspired JI"}))


# ------------------------------------------------------------------
# Just intonation (ratios → semitones via 12*log2)
# ------------------------------------------------------------------

def _jiSemitones(*ratios: float) -> list[float]:
    return [round(12.0 * math.log2(r), 8) for r in ratios]

_reg(TuningSystem.fromSemitones("JI_5limit_major",
    _jiSemitones(1, 9/8, 5/4, 4/3, 3/2, 5/3, 15/8),
    repeatInterval=12.0,
    metadata={"description": "Ptolemy's intense diatonic / 5-limit JI major"}))

_reg(TuningSystem.fromSemitones("JI_7limit",
    _jiSemitones(1, 9/8, 7/6, 9/7, 3/2, 7/4, 15/8),
    repeatInterval=12.0,
    metadata={"description": "7-limit JI with harmonic seventh"}))

_reg(TuningSystem.fromSemitones("harmonicSeries8_16",
    _jiSemitones(8/8, 9/8, 10/8, 11/8, 12/8, 13/8, 14/8, 15/8, 16/8),
    repeatInterval=12.0 * math.log2(2),
    metadata={"description": "Harmonic series partials 8-16"}))


# ------------------------------------------------------------------
# Maqam approximations (24-EDO)
# ------------------------------------------------------------------

def _edo24steps(*steps: int) -> list[float]:
    return [round(s * 0.5, 8) for s in steps]

_reg(TuningSystem.fromSemitones("maqamRast",
    _edo24steps(0, 4, 7, 10, 14, 18, 21),
    repeatInterval=12.0,
    metadata={"description": "Maqam Rast — 24-EDO approximation"}))

_reg(TuningSystem.fromSemitones("maqamBayati",
    _edo24steps(0, 3, 6, 10, 14, 18, 21),
    repeatInterval=12.0,
    metadata={"description": "Maqam Bayati — 24-EDO approximation"}))

_reg(TuningSystem.fromSemitones("maqamHijaz",
    _edo24steps(0, 2, 8, 10, 14, 16, 20),
    repeatInterval=12.0,
    metadata={"description": "Maqam Hijaz — 24-EDO approximation"}))


# ------------------------------------------------------------------
# Empirically measured
# ------------------------------------------------------------------

_reg(TuningSystem.fromHz("slendro_approx",
    [260.4, 295.2, 325.0, 390.5, 433.2], 260.4, repeatIntervalHz=2 * 260.4,
    metadata={"description": "Approximate Javanese Sléndro"}))

_reg(TuningSystem.fromHz("pelog_approx",
    [260.4, 277.2, 309.4, 347.6, 390.5, 416.2, 463.5], 260.4, repeatIntervalHz=2 * 260.4,
    metadata={"description": "Approximate Javanese Pélog"}))

_reg(TuningSystem.fromSemitones("AstridsBontempi",
    [c/100 for c in [
        0,19,21,114,119,208,210,318,322,397,415,
        508,514,621,621,702,718,819,820,928,935,
        1029,1035,1124,1129,
    ]],
    metadata={"description": "Bontempi organ of Astrid Ribeiro Albuquerque Wendt"}))


# ------------------------------------------------------------------
# ScaleMasks — edo12 (same indices apply to all 12-note systems)
# ------------------------------------------------------------------

_DIATONIC_MASKS = [
    # Church modes
    ScaleMask("ionian",        [0,2,4,5,7,9,11],    description="Major scale"),
    ScaleMask("dorian",        [0,2,3,5,7,9,10]),
    ScaleMask("phrygian",      [0,1,3,5,7,8,10]),
    ScaleMask("lydian",        [0,2,4,6,7,9,11]),
    ScaleMask("mixolydian",    [0,2,4,5,7,9,10]),
    ScaleMask("aeolian",       [0,2,3,5,7,8,10],    description="Natural minor"),
    ScaleMask("locrian",       [0,1,3,5,6,8,10]),

    # Harmonic minor modes
    ScaleMask("harmonicMinor",      [0,2,3,5,7,8,11],  description="HM mode 1"),
    ScaleMask("locrianSharp6",      [0,1,3,5,6,9,10],  description="HM mode 2"),
    ScaleMask("ionianSharp5",       [0,2,4,5,8,9,11],  description="HM mode 3"),
    ScaleMask("dorianSharp4",       [0,2,3,6,7,9,10],  description="HM mode 4"),
    ScaleMask("phrygianDominant",   [0,1,4,5,7,8,10],  description="HM mode 5"),
    ScaleMask("lydianSharp2",       [0,3,4,6,7,9,11],  description="HM mode 6"),
    ScaleMask("ultraLocrian",       [0,1,3,4,6,8,9],   description="HM mode 7"),

    # Melodic minor modes (ascending form throughout)
    ScaleMask("melodicMinor",       [0,2,3,5,7,9,11],
              ascending=[0,2,3,5,7,9,11],              description="MM mode 1"),
    ScaleMask("dorianFlat2",        [0,1,3,5,7,9,10],  description="MM mode 2"),
    ScaleMask("lydianAugmented",    [0,2,4,6,8,9,11],  description="MM mode 3"),
    ScaleMask("lydianDominant",     [0,2,4,6,7,9,10],  description="MM mode 4"),
    ScaleMask("mixolydianFlat6",    [0,2,4,5,7,8,10],  description="MM mode 5"),
    ScaleMask("locrianSharp2",      [0,2,3,5,6,8,10],  description="MM mode 6"),
    ScaleMask("altered",            [0,1,3,4,6,8,10],  description="MM mode 7 / superlocrian"),

    # Messiaen modes
    ScaleMask("wholeTone",          [0,2,4,6,8,10],    description="Messiaen mode 1"),
    ScaleMask("halfWholeDim",       [0,1,3,4,6,7,9,10],description="Messiaen mode 2"),
    ScaleMask("messiaen3",          [0,2,3,4,6,7,8,10,11]),
    ScaleMask("messiaen4",          [0,1,2,5,6,7,8,11]),
    ScaleMask("messiaen5",          [0,1,5,6,7,11]),
    ScaleMask("messiaen6",          [0,2,4,5,6,8,10,11]),
    ScaleMask("messiaen7",          [0,1,2,3,5,6,7,8,9,11]),

    # Pentatonic
    ScaleMask("majorPentatonic",    [0,2,4,7,9]),
    ScaleMask("minorPentatonic",    [0,3,5,7,10]),

    # Full chromatic
    ScaleMask("chromatic",          list(range(12))),
]

# attach to all 12-note systems
_12NOTE_SYSTEMS = [
    "edo12",
    "werckmeister1","werckmeister2","werckmeister3","werckmeister4",
    "kirnberger2","kirnberger3","meantoneQC","pythagorean","zeta12",
    "JI_5limit_major","JI_7limit","AstridsBontempi",   # 7 / 7 / 24 steps: skipped below
]
for _name in _12NOTE_SYSTEMS:
    if len(TUNING_SYSTEMS[_name].pitchClasses) == 12:   # 12-step indices only fit 12 steps
        for _mask in _DIATONIC_MASKS:
            TUNING_SYSTEMS[_name].addMask(_mask)

# "chromatic" = every step, for every system that has no mask of that name yet
for _ts in TUNING_SYSTEMS.values():
    if "chromatic" not in _ts.scaleMasks:
        _ts.addMask(ScaleMask("chromatic", list(range(len(_ts.pitchClasses)))))

# Bohlen-Pierce masks
TUNING_SYSTEMS["bohlenPierce"].addMasks([
    ScaleMask("lambda",    [0,1,2,4,5,7,8,9,11,12],
              description="BP Lambda mode (most consonant)"),
    ScaleMask("walker",    [0,2,3,5,6,8,9,11,12],
              description="BP Walker mode"),
    ScaleMask("chromatic", list(range(13))),
])