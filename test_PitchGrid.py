# test_pitchgrid.py

import numbers
import pytest

from .PitchGrid import PitchGrid
from .Pitch import note2midi


# --------------------------------------------------------------------
# Basic construction & type checking
# --------------------------------------------------------------------

def test_pitchgrid_init_accepts_numeric():
    pg = PitchGrid([60, 61.5, 72])
    assert isinstance(pg, PitchGrid)
    assert pg.check_types(expected_type=numbers.Number)
    # grid is a set, so membership tests
    assert 60 in pg
    assert 61.5 in pg
    assert 72 in pg


def test_pitchgrid_init_rejects_non_numeric():
    with pytest.raises(TypeError):
        PitchGrid(["c4", 60])  # mix of string and number should fail


# --------------------------------------------------------------------
# from_notes
# --------------------------------------------------------------------

def test_from_notes_with_strings_and_numbers():
    pg = PitchGrid.from_notes(["c4", "bf3", 60])

    vals = sorted(pg)
    expected = sorted({
        note2midi("c4"),
        note2midi("bf3"),
        float(60),
    })

    assert vals == expected
    assert pg.name is None  # default name


def test_from_notes_with_name_and_none():
    pg = PitchGrid.from_notes(None, name="mygrid")
    # should be empty but still a PitchGrid
    assert isinstance(pg, PitchGrid)
    assert len(pg) == 0
    assert pg.name == "mygrid"


# --------------------------------------------------------------------
# from_range
# --------------------------------------------------------------------

def test_from_range_basic_semitones():
    pg = PitchGrid.from_range(60, 64, 1.0, "range_test")

    vals = sorted(pg)
    assert vals == [60.0, 61.0, 62.0, 63.0, 64.0]
    assert pg.name == "range_test"


def test_from_range_reversed_input():
    # high < low: should be swapped internally
    pg = PitchGrid.from_range(64, 60, step=1.0)

    vals = sorted(pg)
    assert vals == [60.0, 61.0, 62.0, 63.0, 64.0]


def test_from_range_step_error():
    with pytest.raises(ValueError):
        PitchGrid.from_range(60, 64, step=0)  # invalid step


# --------------------------------------------------------------------
# from_pitch_classes
# --------------------------------------------------------------------

def test_from_pitch_classes_with_root_string():
    # major triad on C
    pcs = [0.0, 4.0, 7.0]
    root = "c4"          # defines pc 0
    min_midi = note2midi("c4")
    max_midi = note2midi("c5")

    pg = PitchGrid.from_pitch_classes(
        pcs=pcs,
        root=root,
        min_midi=min_midi,
        max_midi=max_midi,
        name="C_major"
    )

    vals = sorted(pg)
    expected = sorted([
        note2midi("c4"),
        note2midi("e4"),
        note2midi("g4"),
        note2midi("c5"),
    ])

    assert vals == expected
    assert pg.name == "C_major"


def test_from_pitch_classes_with_root_midi():
    pcs = [0.0, 4.0, 7.0]
    root_midi = note2midi("d3")  # now 0 = D
    min_midi = root_midi
    max_midi = root_midi + 12.0  # one octave

    pg = PitchGrid.from_pitch_classes(
        pcs=pcs,
        root=root_midi,
        min_midi=min_midi,
        max_midi=max_midi
    )

    vals = sorted(pg)
    # Expected: D, F#, A, D (one octave up)
    expected = sorted([
        root_midi,                  # D
        root_midi + 4.0,            # F#
        root_midi + 7.0,            # A
        root_midi + 12.0,           # D up
    ])

    assert vals == expected


def test_from_pitch_classes_invalid_root_type():
    with pytest.raises(TypeError):
        PitchGrid.from_pitch_classes(
            pcs=[0, 4, 7],
            root=["not", "valid"],  # invalid type
            min_midi=60,
            max_midi=72
        )

