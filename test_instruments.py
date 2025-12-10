import pytest

from GreasyPidgin.Instrument import Instrument
from GreasyPidgin.Instruments import (
    STANDARD_INSTRUMENTS,
    get_standard_instrument,
)
from GreasyPidgin.Pitch import note2midi as nm


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

def test_all_palette_entries_are_instruments():
    assert STANDARD_INSTRUMENTS, "palette should not be empty"
    for key, ins in STANDARD_INSTRUMENTS.items():
        assert isinstance(ins, Instrument), f"{key} is not an Instrument"


def test_get_standard_instrument_returns_same_instance():
    fl1 = get_standard_instrument("flute")
    fl2 = get_standard_instrument("flute")
    assert fl1 is fl2           # same shared object
    assert fl1.name == "flute"


def test_get_standard_instrument_unknown_raises():
    with pytest.raises(KeyError):
        get_standard_instrument("this-does-not-exist")


# ---------------------------------------------------------------------------
# A few representative instruments
# ---------------------------------------------------------------------------

def test_flute_properties():
    fl = get_standard_instrument("flute")

    assert fl.name == "flute"
    assert fl.rangeMidi == (nm("c4"), nm("d7"))
    assert fl.lowest_written_midi == nm("c4")
    assert fl.highest_written_midi == nm("d7")

    # non-transposing
    assert fl.transposition_semitones == 0.0
    assert fl.lowest_sounding_midi == fl.lowest_written_midi
    assert fl.highest_sounding_midi == fl.highest_written_midi

    # microtones allowed
    ok, extra = fl.in_range(62.5, allow_microtones=True)  # C4 quarter-sharp
    assert ok is True
    assert extra is None


def test_b_flat_clarinet_transposition():
    cl = get_standard_instrument("b-flat-clarinet")

    # written range
    assert cl.rangeMidi == (nm("e3"), nm("a6"))
    assert cl.transposition_semitones == -2

    # sounding range must be shifted by -2 semitones
    assert cl.lowest_sounding_midi == cl.lowest_written_midi - 2
    assert cl.highest_sounding_midi == cl.highest_written_midi - 2

    # written middle C (c4) should sound as Bb3
    written_c4 = nm("c4")
    sounding = written_c4 + cl.transposition_semitones
    assert sounding == nm("bf3")


def test_piccolo_transposition_up():
    picc = get_standard_instrument("piccolo")

    assert picc.transposition_semitones == 12
    assert picc.lowest_sounding_midi == picc.lowest_written_midi + 12
    assert picc.highest_sounding_midi == picc.highest_written_midi + 12


def test_violin_chords_and_microtones():
    vln = get_standard_instrument("violin")

    assert vln.chordsPossible is True
    assert vln.microTones is True

    # microtonal pitch in range should be accepted when allowed
    p = nm("a4") + 0.5
    ok, extra = vln.in_range(p, allow_microtones=True)
    assert ok is True
    assert extra is None


# ---------------------------------------------------------------------------
# Missing-note handling
# ---------------------------------------------------------------------------

def test_missing_notes_written_and_sounding_consistent():
    fl = get_standard_instrument("flute")

    # from your palette: missing cqs4 and dqf4
    # note2midi('cqs4') = 60.5 -> int(...) = 60 etc.
    expected_written = {int(nm("cqs4")), int(nm("dqf4"))}
    assert fl.missing_notes_written == expected_written

    # sounding notes must be written + transposition
    expected_sounding = {n + int(flv) for n in expected_written
                         for flv in [fl.transposition_semitones]}
    assert fl.missing_notes_sounding == expected_sounding


def test_in_range_respects_missing_notes():
    cl = get_standard_instrument("b-flat-clarinet")

    # choose one of its missing notes
    missing_written = next(iter(cl.missing_notes_written))
    ok, extra = cl.in_range(missing_written)
    assert ok is False
    assert extra is None  # rejected because it's missing, not out of range

    ok2, extra2 = cl.in_range(missing_written, allow_missing_notes=True)
    assert ok2 is True
    assert extra2 is None