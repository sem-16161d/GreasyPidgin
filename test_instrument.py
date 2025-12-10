import sys
import pytest
from pathlib import Path

from .Instrument import Instrument

ROOT = Path(__file__).resolve().parents[1]  # go up one level
sys.path.insert(0, str(ROOT))

@pytest.fixture
def testInstrument():
    # NOTE: if your __init__ doesn’t handle missing_notes=None yet,
    # change it to something like:
    #   if missing_notes is None: missing_notes = set()
    return Instrument(
        'piano',                 # name
        (21, 108),               # rangeMidi  (A0–C8)
        2,                       # numSystems
        ['treble', 'bass'],      # initClefs
        ['treble', 'bass'],      # possibleClefs
        True,                    # chordsPossible
        False,                   # microTones
        ('ppppp', 'fffff'),      # writtenDynamicRange
        (50, 96),                # physicalDynamicRangedB
        0,                       # transposition_semitones
        None,                    # missing_notes
        1                        # midi_program
    )

def test_slots_basic(testInstrument):
    ins = testInstrument

    assert ins.name == "piano"
    assert ins.numSystems == 2

    # pitch behaviour
    assert ins.rangeMidi == (21, 108)
    assert ins.lowest_written_midi == 21
    assert ins.highest_written_midi == 108
    assert ins.lowest_sounding_midi == 21
    assert ins.highest_sounding_midi == 108

    assert ins.chordsPossible is True
    assert ins.microTones is False

    # missing notes
    # if missing_notes=None -> empty sets
    assert isinstance(ins.missing_notes_written, set)
    assert isinstance(ins.missing_notes_sounding, set)

    # dynamics
    assert ins.writtenDynamicRange == ('ppppp', 'fffff')
    assert ins.actualDynamicRange == (50, 96)

    # clefs
    assert ins.initClefs == ['treble', 'bass']
    assert ins.possibleClefs == ['treble', 'bass']

    # MIDI settings
    assert ins.transposition_semitones == 0.0
    assert ins.midi_program == 1

# ---------------------------------------------------------------------------
# in_range tests
# ---------------------------------------------------------------------------

def test_in_range_written_inside(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(60)  # middle C
    assert ok is True
    assert extra is None


def test_in_range_written_low_border(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(21)  # lowest note
    assert ok is True
    assert extra is None


def test_in_range_written_too_low(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(20)
    assert ok is False
    assert extra == 0   # 0 = too low


def test_in_range_written_too_high(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(109)
    assert ok is False
    assert extra == 1   # 1 = too high


def test_in_range_sounding_flag(testInstrument):
    """With transposition 0, written and sounding ranges are identical."""
    ins = testInstrument
    ok_w, _ = ins.in_range(60, sounding=False)
    ok_s, _ = ins.in_range(60, sounding=True)
    assert ok_w is True
    assert ok_s is True


def test_in_range_microtones_rejected_when_not_supported(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(60.5)  # quarter tone
    assert ok is False
    # special case: rejected because of microtone -> extra is None
    assert extra is None


def test_in_range_microtones_allowed_with_flag(testInstrument):
    ins = testInstrument
    ok, extra = ins.in_range(60.5, allow_microtones=True)
    # still in numerical range -> accepted
    assert ok is True
    assert extra is None


def test_in_range_missing_notes(testInstrument):
    """Check behaviour when a missing note is specified.

    We manually mark 60 as a missing *written* note.
    """
    ins = testInstrument
    ins.missing_notes_written = {60}
    ins.missing_notes_sounding = {60}  # because transposition_semitones == 0

    ok, extra = ins.in_range(60)
    assert ok is False
    assert extra is None  # rejected due to missing note, not range

    ok2, extra2 = ins.in_range(60, allow_missing_notes=True)
    assert ok2 is True
    assert extra2 is None

# ---------------------------------------------------------------------------
# force_in_range tests
# ---------------------------------------------------------------------------

def test_force_in_range_inside_returns_same(testInstrument):
    ins = testInstrument
    val = ins.force_in_range(60)
    assert val == pytest.approx(60.0)


def test_force_in_range_too_low_octave_up(testInstrument):
    ins = testInstrument
    # 9 semitones below piano -> should move up one or more octaves
    val = ins.force_in_range(12)
    low, high = ins._get_range(sounding=False)
    assert low <= val <= high
    # and pitch class should be same as original (mod 12)
    assert (val - 12) % 12 == pytest.approx(0.0)


def test_force_in_range_too_high_octave_down(testInstrument):
    ins = testInstrument
    val = ins.force_in_range(120)
    low, high = ins._get_range(sounding=False)
    assert low <= val <= high
    assert (val - 120) % 12 == pytest.approx(0.0)


def test_force_in_range_preserves_microtone_offset(testInstrument):
    ins = testInstrument
    # allow microtones so we can check preservation
    original = 120.5
    val = ins.force_in_range(
        original,
        allow_microtones=True,
    )
    low, high = ins._get_range(sounding=False)
    assert low <= val <= high
    # same fractional part
    frac_original = original - int(original)
    frac_result = val - int(val)
    assert frac_result == pytest.approx(frac_original)

# ---------------------------------------------------------------------------
# Behaviour with transposition
# ---------------------------------------------------------------------------

def test_transposition_affects_sounding_range():
    """Create a transposing instrument and check sounding range shifts."""
    ins = Instrument(
        name='clarinet_in_bb',
        rangeMidi=(60, 80),
        numSystems=1,
        initClefs=['treble'],
        possibleClefs=['treble'],
        chordsPossible=True,
        microTones=True,
        writtenDynamicRange=('pp', 'ff'),
        physicalDynamicRangedB=(50, 96),
        transposition_semitones=-2,
        missing_notes=None,
        midi_program=72,
    )

    assert ins.lowest_written_midi == 60
    assert ins.highest_written_midi == 80
    assert ins.lowest_sounding_midi == 58   # 60 - 2
    assert ins.highest_sounding_midi == 78  # 80 - 2

    # 60 is fine as written:
    ok_w, _ = ins.in_range(60, sounding=False)
    assert ok_w is True

    # but as sounding pitch it’s too high (above 78):
    ok_s, hi_lo = ins.in_range(80, sounding=True)
    assert ok_s is False
    assert hi_lo == 1