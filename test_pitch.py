import pytest
from .Pitch import note2midi


# -------------------------------
# Basic diatonic notes
# -------------------------------
def test_basic_notes():
    assert note2midi("c4") == 60.0       # middle C
    assert note2midi("d4") == 62.0
    assert note2midi("e4") == 64.0
    assert note2midi("B3") == 59.0       # case-insensitive


# -------------------------------
# Sharps and flats
# -------------------------------
def test_sharps_and_flats():
    assert note2midi("fs4") == 66.0      # F#4
    assert note2midi("bf3") == 58.0      # B♭3
    assert note2midi("cs4") == 61.0
    assert note2midi("ef4") == 63.0


# -------------------------------
# Quarter-tone accidentals
# -------------------------------
def test_quarter_tones():
    assert note2midi("cqs4") == 60.5
    assert note2midi("cqf4") == 59.5     # C quarter-flat = 60 - 0.5


# -------------------------------
# Sixth-tone accidentals
# -------------------------------
def test_sixth_tones():
    assert pytest.approx(note2midi("css4"), rel=1e-6) == 60 + (1/3)
    assert pytest.approx(note2midi("csf4"), rel=1e-6) == 60 - (1/3)


# -------------------------------
# Twelfth-tone accidentals
# -------------------------------
def test_twelfth_tones():
    assert pytest.approx(note2midi("cts4"), rel=1e-6) == 60 + (1/6)
    assert pytest.approx(note2midi("ctf4"), rel=1e-6) == 60 - (1/6)


# -------------------------------
# Octave boundaries
# -------------------------------
def test_octaves():
    assert note2midi("c0") == 12.0
    assert note2midi("c1") == 24.0
    assert note2midi("c-1") == 0.0


# -------------------------------
# Invalid inputs
# -------------------------------
def test_invalid_format():
    with pytest.raises(ValueError):
        note2midi("not_a_note")

    with pytest.raises(ValueError):
        note2midi("h4")          # invalid letter

    with pytest.raises(ValueError):
        note2midi("cxx4")        # unknown accidental

    with pytest.raises(ValueError):
        note2midi("c")           # missing octave


# -------------------------------
# Edge cases
# -------------------------------
def test_spacing_and_case():
    assert note2midi("  C4  ") == 60.0
    assert note2midi("bf3") == note2midi("BF3")