import numbers
from .QuantisationGrid import Grid
from .Pitch import note2midi  # assuming Pitch.py is in the same package/folder


class PitchGrid(Grid):
    def __init__(self, values=None, name=None):
        super().__init__(values)
        if not self.check_types(expected_type=numbers.Number):
            raise TypeError("PitchGrid expects numeric (MIDI) values only.")
        self.name = name

        # ---- constructors ----
    @classmethod
    def from_notes(cls, notes, name=None):
        """
        Create a PitchGrid from an iterable of note names (and/or MIDI numbers).

        notes can be:
            - strings like "c4", "bf3", "cqs4", ...
            - numeric MIDI values (int/float), which are passed through.
        """
        if notes is None:
            return cls(values=None, name=name)

        midi_vals = []
        for n in notes:
            if isinstance(n, numbers.Number):
                midi_vals.append(float(n))
            else:
                midi_vals.append(note2midi(str(n)))

        return cls(values = midi_vals, name=name)

    @classmethod
    def from_pitch_classes(cls, pcs, root, min_midi, max_midi, name=None):
        """
        Construct a PitchGrid from:
            - pcs: iterable of pitch classes (0–12, may include microtones)
            - root: MIDI number *or* pitch name string ('c4', 'bf3', etc.)
            - min_midi, max_midi: inclusive range boundaries

        Example:
            pcs = [0, 4, 7]      # major triad
            root = "c4"          # defines pc 0
        """

        # ---- normalize root ----
        if isinstance(root, (int, float)):
            root = float(root)
        elif isinstance(root, str):
            root = float(note2midi(root))
        else:
            raise TypeError("root must be a MIDI number or pitch name string")

        # ---- normalize numeric inputs ----
        pcs = [float(x) for x in pcs]
        min_midi = float(min_midi)
        max_midi = float(max_midi)
        rootPC = root%12

        if min_midi > max_midi:
            min_midi, max_midi = [max_midi, min_midi]

        values = []
        for octave in range(12):
            for p in pcs:
                values.append(rootPC+(octave*12)+p)

        values = [v for v in values if v >= min_midi and v <= max_midi]

        return cls(values, name=name)

    @classmethod
    def from_range(cls, low_midi=0, high_midi=127, step=1.0, name=None):
        """
        Create a PitchGrid from a MIDI range [low_midi, high_midi].

        - low_midi, high_midi: numeric MIDI boundaries
        - step: positive float (1.0 = semitones, 0.5 = quarter tones, etc.)
        """
        if step <= 0:
            raise ValueError("step must be > 0")

        low = float(low_midi)
        high = float(high_midi)

        # allow reversed input
        if low > high:
            low, high = high, low

        # Use Grid.series directly
        g = Grid.series(start=low, step=step, size = int((high-low+1)/step))

        # Wrap in PitchGrid
        return cls(g, name=name)
    
    
    @classmethod
    def fromChurchModes(cls, mode, root, min_midi, max_midi, name=None):
        """
        Construct a PitchGrid from a church mode defined in SCALE_MASKS_12TET.

        Parameters
        ----------
        mode : str
            Name of the mode, e.g. 'ionian', 'dorian', 'phrygian', ...
        root : int | float | str
            Root as MIDI number or note name string ('c4', 'bf3', ...).
        min_midi, max_midi : int | float
            Inclusive MIDI boundaries for the grid.
        name : str | None
            Optional name for the PitchGrid. If None, the mode name is used.
        """
        mode_key = str(mode).lower()
        try:
            pcs = SCALE_MASKS_12TET[mode_key]
        except KeyError as exc:
            raise KeyError(f"Unknown church mode: {mode!r}") from exc

        # reuse your from_pitch_classes constructor
        return cls.from_pitch_classes(
            pcs=pcs,
            root=root,
            min_midi=min_midi,
            max_midi=max_midi,
            name=name or mode_key,
        )

    @classmethod
    def from_sruti_raga(cls, raga_name, root, min_midi, max_midi, name=None):
        """
        Construct a PitchGrid from a 22-Śruti raga mask (e.g. 'abhogi')
        and a root (MIDI or note name).
        """
        pcs = get_sruti_mask(raga_name)
        return cls.from_pitch_classes(pcs, root=root,
                                    min_midi=min_midi,
                                    max_midi=max_midi,
                                    name=name or raga_name)
    


# ---------------------------------------------------------------------------
# Pitch-class libraries
#   - all values are in *semitones* relative to a given root
# ---------------------------------------------------------------------------

def _edo_pitch_classes(n: int):
    """Return N pitch classes for an N-EDO system in semitones from 0–12."""
    if n <= 0:
        raise ValueError("EDO must be > 0")
    step = 12.0 / float(n)
    return [i * step for i in range(n)]


EDO_SYSTEMS = {
    "edo11": _edo_pitch_classes(11),
    "edo12": _edo_pitch_classes(12),
    "edo22": _edo_pitch_classes(22),
    "edo24": _edo_pitch_classes(24),
    "edo53": _edo_pitch_classes(53),
    "edo72": _edo_pitch_classes(72),
}
####################################################################################################
PARTCH_43 = [
    0.0, 0.22, 0.53, 0.84, 1.12, 1.51, 1.65, 1.82, 2.04, 2.31, 
    2.67, 2.94, 3.16, 3.47, 3.86, 4.18, 4.35, 4.71, 4.98, 5.2, 
    5.51, 5.83, 6.18, 6.49, 6.81, 7.02, 7.29, 7.65, 7.83, 8.14,
    8.53, 8.84, 9.06, 9.33, 9.69, 9.96, 10.18, 10.35, 10.49, 10.88, 
    11.16, 11.47, 11.78
]

HISTORICAL_EUROPEAN_TUNINGS = {
    # Each entry: list of 12 pitch classes in semitones relative to tonic.
    # These are *deviations* from 12-TET (or direct semitone positions),
    # e.g. for C-based scale: [0.0, something, ..., < 12.0]
    "werckmeister3": [ 0.0, 0.9, 1.92, 2.94, 3.9, 4.98, 5.88, 6.96, 7.92, 8.88, 9.96, 10.92 ],
    "kirnberger3": [ 0.0, 0.9, 2.03, 2.94, 3.86, 4.98, 5.9, 7.01, 7.92, 8.84, 9.96, 10.88 ],
    "meantoneQuarterComma": [ 0.0, 0.76, 1.93, 3.1, 3.86, 5.03, 5.79, 6.96, 7.72, 8.89, 10.06, 10.82 ]
}


NON_EUROPEAN_TUNINGS  = {
    # accoring to http://www.harmonik.de/harmonik/vtr_pdf/Beitraege9403Glorian.pdf
    "ShrutiJustIntonation": { "Sa": 0.0, # Sa
                             "Ri1": 0.9, "Ri2":1.12, "Ri3":1.82, "Ri4":2.04, #Ri
                             "Ga1": 2.94, "Ga2": 3.16, "Ga3": 3.86, "Ga4": 4.08, #Ga
                             "Ma1": 4.98, "Ma2": 5.2, "Ma3": 5.9, "Ma4": 6.1, #Ma
                             "Pa": 7.02, #Pa
                             "Dha1": 7.92, "Dha2": 8.14, "Dha3": 8.84, "Dha4": 9.06, #Dha
                             "Ni1": 9.96, "Ni2": 10.18, "Ni3": 10.88, "Ni4": 11.1 #Ni
}
}



SCALE_MASKS_22SRUTI = {
    "abhogi": [NON_EUROPEAN_TUNINGS["ShrutiJustIntonation"][k] for k in 
               ("Sa", "Ri2", "Ga2", "Ma1", "Dha2")]
}

def get_sruti_mask(raga_name: str):
        try:
            return SCALE_MASKS_22SRUTI[raga_name]
        except KeyError as exc:
            raise KeyError(f"Unknown 22-Śruti raga mask: {raga_name!r}") from exc

def get_system_pitch_classes(system: str):
    """
    Return a list of pitch classes (in semitones 0–12) for a named system.

    Supported now:
    - 'edo12', 'edo22', 'edo24', 'edo53', 'edo72'
    - 'partch43' (if PARTCH_43_PITCH_CLASSES is filled)
    - any key in HISTORICAL_TUNINGS
    """
    system = system.lower()

    if system in EDO_SYSTEMS:
        return EDO_SYSTEMS[system]

    if system == "partch43":
        if not PARTCH_43:
            raise NotImplementedError("PARTCH 43 pitch classes not filled yet.")
        return PARTCH_43

    if system in HISTORICAL_EUROPEAN_TUNINGS:
        return HISTORICAL_EUROPEAN_TUNINGS[system]

    raise KeyError(f"Unknown pitch-class system: {system!r}")


# ---------------------------------------------------------------------------
# Scale / mode filters (12-TET based for now)
#   values are pitch classes 0–11 relative to root
# ---------------------------------------------------------------------------

SCALE_MASKS_12TET = {
    # classic church modes
    "ionian":    [0, 2, 4, 5, 7, 9, 11],  
    "dorian":    [0, 2, 3, 5, 7, 9, 10],
    "phrygian":  [0, 1, 3, 5, 7, 8, 10],
    "lydian":    [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":[0, 2, 4, 5, 7, 9, 10],
    "aeolian":   [0, 2, 3, 5, 7, 8, 10], 
    "locrian":   [0, 1, 3, 5, 6, 8, 10],
}

