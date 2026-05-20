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

import math
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

    'sqs': 1 + 0.5,         # sharp + quarter-sharp
    'sqf': 1 - 0.5,        # flat + quarter-flat
    'fqs': -1 + 0.5,         # sharp + quarter-sharp
    'fqf': -1 -0.5,        # flat + quarter-flat
    'sss': 1 + 1/3,     # sharp + sixth-tone sharp
    'ssf': 1 - 1/3,     # sharp + sixth-tone flat
    'fss': -1 + 1/3,    # flat + sixth-tone sharp
    'fsf': -1 - 1/3,    # flat + sixth-tone flat
    'sts': 1 + 1/6,     # sharp + twelfth-tone sharp
    'stf': 1 - 1/6,     # sharp + twelfth-tone flat
    'fts': -1 + 1/6,    # flat + twelfth-tone sharp
    'ftf': -1 - 1/6,    # flat + twelfth-tone flat
    
}

def spntom(spn: str) -> float:
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
    s = spn.strip().lower()

    # letter: a–g
    # acc: optional accidental: "", "s", "f", "qs", "qf", "ss", "sf", "ts", "tf"
    # octave: signed integer (e.g. -1, 3, 4)
    m = re.fullmatch(r"([a-g])([qsft]{0,3})(-?\d+)", s)
    if not m:
        raise ValueError(f"Cannot parse note name: {spn!r}")

    letter, acc, octave_str = m.groups()
    octave = int(octave_str)

    # Base semitone index within the octave
    base_semitones = _NOTE_OFFSETS[letter]

    # Microtonal offset (may be 0.0 if no accidental)
    if acc not in _ACCIDENTAL_OFFSETS:
        raise ValueError(f"Unknown accidental '{acc}' in note {spn!r}")
    offset = _ACCIDENTAL_OFFSETS[acc]

    # MIDI formula: 12 * (octave + 1) + semitone_index
    return 12.0 * (octave + 1) + base_semitones + offset

def spntof(spn: str, referenceA4: float = 440.0):
    return mtof(spntom(spn))

def ftom(freq: float, referenceA4: float = 440.0) -> float:
    f = float(freq)
    ref = float(referenceA4)

    if f <= 0.0:
        raise ValueError(f"freq must be > 0, got {freq!r}")
    if ref <= 0.0:
        raise ValueError(f"a4 must be > 0, got {referenceA4!r}")

    return 69.0 + 12.0 * (math.log(f / ref, 2))

def mtof(midi: float, referenceA4: float = 440.0) -> float:
    m = float(midi)
    ref = float(referenceA4)

    if ref <= 0.0:
        raise ValueError(f"a4 must be > 0, got {referenceA4!r}")

    return ref * (2.0 ** ((m - 69.0) / 12.0))