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
