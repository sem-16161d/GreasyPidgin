"""
Python adaption of Pitch.lsp from Michael Edwards' slippery chicken 
https://michael-edwards.org/sc/ 
m@michael-edwards.org

Python adaptation:
  by Sem Ribeiro Albuquerque Wendt
  https://www.16161d.net
  sem@16161d.net

last updated: 08.12.2025
"""


import re

# Basic semitone offsets within an octave (C = 0, …, B = 11)
_NOTE_OFFSETS = {
    "c": 0,
    "d": 2,
    "e": 4,
    "f": 5,
    "g": 7,
    "a": 9,
    "b": 11,
}

# Microtonal accidentals and their offsets in semitones
_ACCIDENTAL_OFFSETS = {
    "":   0.0,          # natural
    "s":  1.0,          # sharp
    "f": -1.0,          # flat
    "qs":  0.5,         # quarter-sharp
    "qf": -0.5,         # quarter-flat
    "ss":  1.0 / 3.0,   # sixth-tone sharp
    "sf": -1.0 / 3.0,   # sixth-tone flat
    "ts":  1.0 / 6.0,   # twelfth-tone sharp
    "tf": -1.0 / 6.0,   # twelfth-tone flat
}


def note2midi(note: str) -> float:
    """
    Convert a note name like 'c4', 'bf3', 'cqs4', 'C-1' into a MIDI value.

    The result is a float, because microtonal accidentals are supported.

    Accidentals:
        s   = sharp        (fs3  -> F♯3)
        f   = flat         (bf3  -> B♭3)
        qs  = quarter-sharp (cqs4 -> +0.5 semitones)
        qf  = quarter-flat  (dqf4 -> −0.5 semitones)
        ss  = sixth-tone sharp   (+1/3 semitone)
        sf  = sixth-tone flat    (−1/3 semitone)
        ts  = twelfth-tone sharp (+1/6 semitone)
        tf  = twelfth-tone flat  (−1/6 semitone)

    Examples:
        note2midi("c4")   -> 60.0
        note2midi("bf3")  -> 58.0
        note2midi("cqs4") -> 60.5
        note2midi("C-1")  -> 0.0
    """
    s = note.strip().lower()

    # letter: a–g
    # acc: optional accidental: "", "s", "f", "qs", "qf", "ss", "sf", "ts", "tf"
    # octave: signed integer (e.g. -1, 3, 4)
    m = re.fullmatch(r"([a-g])([qsft]{0,2})(-?\d+)", s)
    if not m:
        raise ValueError(f"Cannot parse note name: {note!r}")

    letter, acc, octave_str = m.groups()
    octave = int(octave_str)

    # Base semitone index within the octave
    base_semitones = _NOTE_OFFSETS[letter]

    # Microtonal offset (may be 0.0 if no accidental)
    if acc not in _ACCIDENTAL_OFFSETS:
        raise ValueError(f"Unknown accidental '{acc}' in note {note!r}")
    offset = _ACCIDENTAL_OFFSETS[acc]

    # MIDI formula: 12 * (octave + 1) + semitone_index
    return 12.0 * (octave + 1) + base_semitones + offset