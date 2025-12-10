"""
Python adaption of Standard instrument palette from Michael Edwards' slippery chicken 
https://michael-edwards.org/sc/ 
m@michael-edwards.org

Python adaptation:
  by Sem Ribeiro Albuquerque Wendt
  https://www.16161d.net
  sem@16161d.net

last updated: 08.12.2025
"""

from __future__ import annotations

from .Instrument import Instrument  # adjust to your actual module name
from .Pitch import note2midi as nm

# ---------------------------------------------------------------------------
# Utility: note-name -> MIDI (supports quarter-tones)
# ---------------------------------------------------------------------------

def _missing(*names: str):
    """Helper to build missing-note sets from note-name strings."""
    if not names or (len(names) == 1 and names[0] is None):
        return set()
    return {nm(n) for n in names}


# ---------------------------------------------------------------------------
# Standard Instrument Palette
# ---------------------------------------------------------------------------

STANDARD_INSTRUMENTS: dict = {
    # -----------------------------------------------------------------------
    # Flutes & recorders
    # -----------------------------------------------------------------------
    "piccolo": Instrument(
        name="piccolo",
        rangeMidi=(nm("d4"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=73,
    ),
    "flute": Instrument(
        name="flute",
        rangeMidi=(nm("c4"), nm("d7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing("cqs4", "dqf4"),
        midi_program=74,
    ),
    "alto-flute": Instrument(
        name="alto flute",
        rangeMidi=(nm("c4"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-5,
        missing_notes=_missing("cqs4", "dqf4"),
        midi_program=74,
    ),
    "bass-flute": Instrument(
        name="bass flute",
        rangeMidi=(nm("c4"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],  # clefs-in-c had bass too
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-12,
        missing_notes=_missing("cqs4", "dqf4"),
        midi_program=74,
    ),
    "sopranino-recorder": Instrument(
        name="sopranino recorder",
        rangeMidi=(nm("f4"), nm("g6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=75,
    ),
    "soprano-recorder": Instrument(
        name="soprano recorder",
        rangeMidi=(nm("c4"), nm("d6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=75,
    ),
    "alto-recorder": Instrument(
        name="alto recorder",
        rangeMidi=(nm("f4"), nm("g6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=75,
    ),
    "tenor-recorder": Instrument(
        name="tenor recorder",
        rangeMidi=(nm("c4"), nm("d6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=75,
    ),
    "consort-tenor-recorder": Instrument(
        name="consort tenor recorder",
        rangeMidi=(nm("c4"), nm("a5")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing("cs4", "ds4"),
        midi_program=75,
    ),
    "bass-recorder": Instrument(
        name="bass recorder",
        rangeMidi=(nm("f2"), nm("f4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=75,
    ),

    # -----------------------------------------------------------------------
    # Oboe family
    # -----------------------------------------------------------------------
    "oboe": Instrument(
        name="oboe",
        rangeMidi=(nm("bf3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing("bqf3", "bqs3", "cqs4", "dqf4"),
        midi_program=69,
    ),
    "cor-anglais": Instrument(
        name="cor anglais",
        rangeMidi=(nm("bf3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-7,
        missing_notes=_missing("bqf3", "bqs3", "cqs4", "dqf4"),
        midi_program=70,
    ),
    "oboe-d-amore": Instrument(
        name="oboe d'amore",
        rangeMidi=(nm("bf3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-3,
        missing_notes=_missing("bqf3", "bqs3", "cqs4", "dqf4"),
        midi_program=70,
    ),

    # -----------------------------------------------------------------------
    # Clarinets
    # -----------------------------------------------------------------------
    "e-flat-clarinet": Instrument(
        name="E-flat clarinet",
        rangeMidi=(nm("e3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=3,
        missing_notes=_missing(
            "aqs4", "bqf4", "bqs4", "cqs5", "dqf5",
            "gqf3", "fqs3", "fqf3"
        ),
        midi_program=72,
    ),
    "b-flat-clarinet": Instrument(
        name="B-flat clarinet",
        rangeMidi=(nm("e3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-2,
        missing_notes=_missing(
            "aqs4", "bqf4", "bqs4", "cqs5", "dqf5",
            "gqf3", "fqs3", "fqf3"
        ),
        midi_program=72,
    ),
    "a-clarinet": Instrument(
        name="A clarinet",
        rangeMidi=(nm("e3"), nm("a6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-3,
        missing_notes=_missing(
            "aqs4", "bqf4", "bqs4", "cqs5", "dqf5",
            "gqf3", "fqs3", "fqf3"
        ),
        midi_program=72,
    ),
    "bass-clarinet": Instrument(
        name="bass clarinet",
        rangeMidi=(nm("c3"), nm("g6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],  # clefs-in-c included bass
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-14,
        missing_notes=_missing(
            "aqs4", "bqf4", "bqs4", "cqs5", "dqf5",
            "gqf3", "fqs3", "fqf3", "eqf3",
            "dqs3", "dqf3", "cqs3",
        ),
        midi_program=72,
    ),

    # -----------------------------------------------------------------------
    # Saxophones
    # -----------------------------------------------------------------------
    "sopranino-sax": Instrument(
        name="sopranino saxophone",
        rangeMidi=(nm("bf3"), nm("fs6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=3,
        missing_notes=_missing("gqs4", "gqs5"),
        midi_program=65,
    ),
    "soprano-sax": Instrument(
        name="soprano saxophone",
        rangeMidi=(nm("bf3"), nm("fs6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-2,
        missing_notes=_missing("gqs4", "gqs5"),
        midi_program=65,
    ),
    "alto-sax": Instrument(
        name="alto saxophone",
        rangeMidi=(nm("bf3"), nm("fs6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-9,
        missing_notes=_missing("gqs4", "gqs5"),
        midi_program=66,
    ),
    "tenor-sax": Instrument(
        name="tenor saxophone",
        rangeMidi=(nm("bf3"), nm("fs6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],  # clefs-in-c had bass
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-14,
        missing_notes=_missing("gqs4", "gqs5"),
        midi_program=67,
    ),
    "baritone-sax": Instrument(
        name="baritone saxophone",
        rangeMidi=(nm("bf3"), nm("fs6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],  # clefs-in-c had bass
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-21,
        missing_notes=_missing("gqs4", "gqs5"),
        midi_program=68,
    ),

    # -----------------------------------------------------------------------
    # Bassoon family
    # -----------------------------------------------------------------------
    "bassoon": Instrument(
        name="bassoon",
        rangeMidi=(nm("bf1"), nm("c5")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(
            "bqf1", "bqs1", "cqs2", "dqf2", "dqs2", "eqf2"
        ),
        midi_program=71,
    ),
    "contra-bassoon": Instrument(
        name="contrabassoon",
        rangeMidi=(nm("bf1"), nm("a4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-12,
        missing_notes=_missing(
            "bqf1", "bqs1", "cqs2", "dqf2", "dqs2", "eqf2"
        ),
        midi_program=71,
    ),

    # -----------------------------------------------------------------------
    # Horns, trumpets, trombones, tuba
    # -----------------------------------------------------------------------
    "french-horn": Instrument(
        name="french horn",
        rangeMidi=(nm("f2"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-7,
        missing_notes=_missing(),
        midi_program=61,
    ),
    "french-horn-high": Instrument(
        name="french horn (high)",
        rangeMidi=(nm("g3"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-7,
        missing_notes=_missing(),
        midi_program=61,
    ),
    "french-horn-low": Instrument(
        name="french horn (low)",
        rangeMidi=(nm("f2"), nm("g5")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-7,
        missing_notes=_missing(),
        midi_program=61,
    ),
    "c-trumpet": Instrument(
        name="trumpet in C",
        rangeMidi=(nm("fs3"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=57,
    ),
    "b-flat-trumpet": Instrument(
        name="B-flat trumpet",
        rangeMidi=(nm("fs3"), nm("d6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-2,
        missing_notes=_missing(),
        midi_program=57,
    ),
    "tenor-trombone": Instrument(
        name="tenor trombone",
        rangeMidi=(nm("e2"), nm("bf4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=58,
    ),
    "bass-trombone": Instrument(
        name="bass trombone",
        rangeMidi=(nm("e1"), nm("g4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=58,
    ),
    "tuba": Instrument(
        name="tuba",
        rangeMidi=(nm("d1"), nm("g4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=59,
    ),

    # -----------------------------------------------------------------------
    # Mallet percussion & keyboards
    # -----------------------------------------------------------------------
    "marimba": Instrument(
        name="marimba",
        rangeMidi=(nm("c3"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],  # in SC: (treble) but often bass too
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=13,
    ),
    "vibraphone": Instrument(
        name="vibraphone",
        rangeMidi=(nm("f3"), nm("f6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=12,
    ),
    "accordion": Instrument(
        name="accordion",
        rangeMidi=(nm("e1"), nm("bf7")),
        numSystems=2,
        initClefs=["treble"],
        possibleClefs=["treble", "bass", "double-treble", "double-bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=22,
    ),
    "glockenspiel": Instrument(
        name="glockenspiel",
        rangeMidi=(nm("f3"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=24,
        missing_notes=_missing(),
        midi_program=10,
    ),
    "xylophone": Instrument(
        name="xylophone",
        rangeMidi=(nm("f3"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=14,
    ),
    "celesta": Instrument(
        name="celesta",
        rangeMidi=(nm("c3"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=12,
        missing_notes=_missing(),
        midi_program=9,
    ),
    "crotales": Instrument(
        name="crotales",
        rangeMidi=(nm("c4"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=24,
        missing_notes=_missing(),
        midi_program=10,  # glockenspiel program
    ),

    # -----------------------------------------------------------------------
    # Piano, harpsichord, harp, organ
    # -----------------------------------------------------------------------
    "piano": Instrument(
        name="piano",
        rangeMidi=(nm("a0"), nm("c8")),
        numSystems=2,
        initClefs=["treble", "bass"],
        possibleClefs=["treble", "bass", "double-treble", "double-bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=1,
    ),
    "piano-lh": Instrument(
        name="piano-lh",
        rangeMidi=(nm("a0"), nm("c8")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["treble", "bass", "double-treble", "double-bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=1,
    ),
    "harpsichord": Instrument(
        name="harpsichord",
        rangeMidi=(nm("f1"), nm("f6")),
        numSystems=2,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=7,
    ),
    "harp": Instrument(
        name="harp",
        rangeMidi=(nm("b0"), nm("gs7")),
        numSystems=2,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=47,
    ),
    "organ": Instrument(
        name="organ",
        rangeMidi=(nm("c2"), nm("c7")),
        numSystems=2,
        initClefs=["treble"],
        possibleClefs=["treble", "bass"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=20,
    ),
    "organ-pedals": Instrument(
        name="organ pedals",
        rangeMidi=(nm("c2"), nm("g4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=20,
    ),

    # -----------------------------------------------------------------------
    # Percussion (non-pitched)
    # -----------------------------------------------------------------------
    "percussion": Instrument(
        name="percussion",
        rangeMidi=(nm("d4"), nm("g5")),
        numSystems=1,
        initClefs=["percussion"],
        possibleClefs=["percussion"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=1,
    ),
    "tambourine": Instrument(
        name="tambourine",
        rangeMidi=(nm("b4"), nm("b4")),
        numSystems=1,
        initClefs=["percussion"],
        possibleClefs=["percussion"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=1,
    ),

    # -----------------------------------------------------------------------
    # Guitar, mandolin
    # -----------------------------------------------------------------------
    "guitar": Instrument(
        name="guitar",
        rangeMidi=(nm("e3"), nm("b6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=-12,
        missing_notes=_missing(),
        midi_program=25,
    ),
    "mandolin": Instrument(
        name="mandolin",
        rangeMidi=(nm("g3"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=26,  # steel-string guitar in GM
    ),

    # -----------------------------------------------------------------------
    # Voices
    # -----------------------------------------------------------------------
    "soprano": Instrument(
        name="soprano",
        rangeMidi=(nm("c4"), nm("c6")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "mezzo": Instrument(
        name="mezzo-soprano",
        rangeMidi=(nm("a3"), nm("a5")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "alto-voice": Instrument(  # avoid clash with viola's "alto" clef
        name="alto",
        rangeMidi=(nm("f3"), nm("f5")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "countertenor": Instrument(
        name="countertenor",
        rangeMidi=(nm("e3"), nm("e5")),
        numSystems=1,
        initClefs=["treble-8vb"],
        possibleClefs=["treble-8vb"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "tenor-voice": Instrument(
        name="tenor",
        rangeMidi=(nm("c3"), nm("c5")),
        numSystems=1,
        initClefs=["treble-8vb"],
        possibleClefs=["treble-8vb"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "baritone-voice": Instrument(
        name="baritone",
        rangeMidi=(nm("a2"), nm("a4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),
    "bass-voice": Instrument(
        name="bass",
        rangeMidi=(nm("e2"), nm("e4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass"],
        chordsPossible=False,
        microTones=False,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=54,
    ),

    # -----------------------------------------------------------------------
    # Strings
    # -----------------------------------------------------------------------
    "violin": Instrument(
        name="violin",
        rangeMidi=(nm("g3"), nm("c7")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble"],
        chordsPossible=True,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=41,
    ),
    "viola": Instrument(
        name="viola",
        rangeMidi=(nm("c3"), nm("f6")),
        numSystems=1,
        initClefs=["alto"],
        possibleClefs=["alto", "treble"],
        chordsPossible=True,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=42,
    ),
    "viola-d-amore": Instrument(
        name="viola d'amore",
        rangeMidi=(nm("a2"), nm("f7")),
        numSystems=1,
        initClefs=["alto"],
        possibleClefs=["alto", "treble"],
        chordsPossible=True,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=41,
    ),
    "cello": Instrument(
        name="cello",
        rangeMidi=(nm("c2"), nm("a5")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor", "treble"],
        chordsPossible=True,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=43,
    ),
    "double-bass": Instrument(
        name="double bass",
        rangeMidi=(nm("e2"), nm("g5")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "tenor", "treble"],
        chordsPossible=False,
        microTones=True,
        transposition_semitones=-12,
        missing_notes=_missing(),
        midi_program=44,
    ),
    "bass-guitar": Instrument(
        name="bass guitar",
        rangeMidi=(nm("e2"), nm("g4")),
        numSystems=1,
        initClefs=["bass"],
        possibleClefs=["bass", "treble"],
        chordsPossible=True,
        microTones=False,
        transposition_semitones=-12,
        missing_notes=_missing(),
        midi_program=33,
    ),

    # -----------------------------------------------------------------------
    # Computer (generic)
    # -----------------------------------------------------------------------
    "computer": Instrument(
        name="computer",
        rangeMidi=(nm("C-1"), nm("bf8")),
        numSystems=1,
        initClefs=["treble"],
        possibleClefs=["treble", "bass", "double-treble", "double-bass"],
        chordsPossible=True,
        microTones=True,
        transposition_semitones=0,
        missing_notes=_missing(),
        midi_program=100,  # GM FX 4 (atmosphere)
    ),
}


# ---------------------------------------------------------------------------
# Convenience accessor (like get-standard-ins)
# ---------------------------------------------------------------------------

def get_standard_instrument(name: str) -> Instrument:
    """
    Return a standard Instrument instance by key.

    Keys are the dictionary keys of STANDARD_INSTRUMENTS, e.g.:
      'flute', 'b-flat-clarinet', 'violin', 'piano', 'computer', ...

    Note: this returns the shared instance from the palette. If you want
    to modify it without affecting the palette, make your own copy.
    """
    try:
        return STANDARD_INSTRUMENTS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown standard instrument: {name!r}") from exc