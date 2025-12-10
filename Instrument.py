"""
Python adaption of Instrument.lsp from Michael Edwards' slippery chicken 
https://michael-edwards.org/sc/ 
m@michael-edwards.org

by Sem Ribeiro Albuquerque Wendt
https://www.16161d.net
sem@16161d.net

last updated: 08.12.2025
"""

class Instrument:
####################################################################################################
    def __init__(
        self,
        name: str = 'dummy',
        rangeMidi: tuple[float, float] = (0, 127),
        numSystems: int = 1,
        initClefs: list[str] | None = None,
        possibleClefs: list[str] | None = None,
        chordsPossible: bool = True,
        microTones: bool = True,
        writtenDynamicRange: tuple[str, str] = ('ppppp', 'fffff'),
        physicalDynamicRangedB: tuple[float, float] = (60.0, 100.0),
        # see: https://www.researchgate.net/figure/Dynamic-range-of-the-sound-power-of-orchestral-musical-instruments-from-5_fig4_228446442
        transposition_semitones: float = 0.0,
        missing_notes: set[float] | None = None,
        midi_program: int = 1,
    ):
        self.name = name
        self.numSystems = numSystems

        # --- clefs -----------------------------------------------------------
        self.possibleClefs = possibleClefs or ['treble', 'bass']
        self.initClefs = initClefs or ['treble']

        # --- pitch behaviour -------------------------------------------------
        self.rangeMidi = tuple(rangeMidi)
        self.chordsPossible = chordsPossible
        self.microTones = microTones

        # allow for different tunings of instruments
        # (e.g. historical pitch or "B instrument but tuned down X cents")
        self.transposition_semitones = float(transposition_semitones)

        self.lowest_written_midi, self.highest_written_midi = self.rangeMidi
        self.lowest_sounding_midi = self.lowest_written_midi + self.transposition_semitones
        self.highest_sounding_midi = self.highest_written_midi + self.transposition_semitones

        # missing notes (stored as *sounding* MIDI)
        # --------------------------------------------------------------------
        # avoid mutable default: use set() if None
        if missing_notes is None:
            missing_notes = set()
        else:
            missing_notes = set(missing_notes)

        # these are the *written* midi notes as given by the user
        self.missing_notes_written = {int(m) for m in missing_notes}

        # convert to sounding midi by applying transposition
        self.missing_notes_sounding = {
            m + self.transposition_semitones for m in self.missing_notes_written
        }

        # --- dynamic behaviour ----------------------------------------------
        self.writtenDynamicRange = tuple(writtenDynamicRange)
        # physicalDynamicRangedB: (min_dB, max_dB)
        self.actualDynamicRange = tuple(float(x) for x in physicalDynamicRangedB)

        self.midi_program = int(midi_program)

    # ----------------------------------------------------------------------
    # range logic (MIDI-based)
    # ----------------------------------------------------------------------
    def _get_range(self, sounding: bool):
        if sounding:
            return self.lowest_sounding_midi, self.highest_sounding_midi
        return self.lowest_written_midi, self.highest_written_midi

    def in_range(
        self,
        midi: float | int,
        *,
        sounding: bool = False,
        allow_microtones: bool = False,
        allow_missing_notes: bool = False,
    ):
        """
        Check whether a MIDI pitch is in this instrument's range.

        Returns (in_range: bool, extra):
          - If out of range, extra is 0 (too low) or 1 (too high).
          - If rejected only because of microtones or missing notes,
            extra is None.
        """
        if midi is None:
            raise ValueError("in_range: midi cannot be None")

        midi = float(midi)
        is_micro = not midi.is_integer()

        # microtone handling
        if is_micro and not (self.microTones or allow_microtones):
            return False, None

        low, high = self._get_range(sounding=sounding)

        # missing notes handling (compare against *sounding* midi)
        midi_rounded = int(round(midi))
        if (not allow_missing_notes) and midi_rounded in self.missing_notes_sounding:
            return False, None

        too_low = midi < low
        too_high = midi > high

        if too_low:
            return False, 0
        if too_high:
            return False, 1
        return True, None

    def force_in_range(
        self,
        midi: float | int,
        *,
        sounding: bool = False,
        allow_microtones: bool = False,
        allow_missing_notes: bool = False,
    ):
        """
        Force a MIDI pitch into range by octave transposition.

        Keeps microtonal offset if present.
        """
        midi = float(midi)
        in_r, direction = self.in_range(
            midi,
            sounding=sounding,
            allow_microtones=allow_microtones,
            allow_missing_notes=allow_missing_notes,
        )
        if in_r:
            return midi

        # direction: 0 = too low, 1 = too high, None = special (missing / micro)
        # if None, assume “too low” as a simple default.
        too_low = (direction == 0) or (direction is None)
        step = 12.0 if too_low else -12.0

        candidate = midi
        for _ in range(16):  # safety guard
            candidate += step
            ok, _ = self.in_range(
                candidate,
                sounding=sounding,
                allow_microtones=allow_microtones,
                allow_missing_notes=allow_missing_notes,
            )
            if ok:
                return candidate

        # If nothing worked, just clamp to nearest bound.
        low, high = self._get_range(sounding=sounding)
        return max(low, min(high, candidate))