# tests/test_pitchgrid.py

import math
import numbers
import pytest

from .PitchGrid import (
    PitchGrid,
    _edo_pitch_classes,
    EDO_SYSTEMS,
    PARTCH_43,
    HISTORICAL_EUROPEAN_TUNINGS,
    NON_EUROPEAN_TUNINGS,
    SCALE_MASKS_22SRUTI,
    SCALE_MASKS_12TET,
    get_system_pitch_classes,
    get_sruti_mask,
)
from .Pitch import note2midi


# ----------------------------------------------------------------------
# __init__ and basic behaviour
# ----------------------------------------------------------------------

def test_pitchgrid_init_with_numeric_values():
    g = PitchGrid([60, 61.5, 62.0], name="test")
    assert isinstance(g, PitchGrid)
    assert g.name == "test"
    assert all(isinstance(v, numbers.Number) for v in g)
    # grid is a set → membership test
    assert 60 in g
    assert 61.5 in g


def test_pitchgrid_init_rejects_non_numeric():
    with pytest.raises(TypeError):
        PitchGrid(["c4", 60])


# ----------------------------------------------------------------------
# from_notes
# ----------------------------------------------------------------------

def test_from_notes_mixed_input():
    g = PitchGrid.from_notes(["c4", "d4", 64, "ef4"], name="mixed")
    assert isinstance(g, PitchGrid)
    assert g.name == "mixed"

    # Check a few known values
    c4 = note2midi("c4")
    d4 = note2midi("d4")
    ef4 = note2midi("ef4")
    assert c4 in g
    assert d4 in g
    assert 64.0 in g  # numeric passed through
    assert ef4 in g


def test_from_notes_none():
    g = PitchGrid.from_notes(None, name="empty")
    assert isinstance(g, PitchGrid)
    assert g.name == "empty"
    # underlying set should be empty
    assert len(g) == 0


# ----------------------------------------------------------------------
# from_pitch_classes
# ----------------------------------------------------------------------

def test_from_pitch_classes_simple_triads():
    pcs = [0, 4, 7]  # major triad
    # use C4 as root, and a modest range
    min_midi = note2midi("c3")
    max_midi = note2midi("c5")
    g = PitchGrid.from_pitch_classes(
        pcs=pcs,
        root="c4",
        min_midi=min_midi,
        max_midi=max_midi,
        name="c_major_triad"
    )

    assert isinstance(g, PitchGrid)
    assert g.name == "c_major_triad"
    # must contain c4, e4, g4
    c4 = note2midi("c4")
    e4 = note2midi("e4")
    g4 = note2midi("g4")
    assert c4 in g
    assert e4 in g
    assert g4 in g

    # everything should be in range
    assert all(min_midi <= x <= max_midi for x in g)


def test_from_pitch_classes_root_as_midi():
    pcs = [0, 3, 7]  # minor triad
    root_midi = note2midi("d4")
    g = PitchGrid.from_pitch_classes(
        pcs, root=root_midi,
        min_midi=root_midi - 12,
        max_midi=root_midi + 12,
        name="d_minor_triad",
    )
    assert isinstance(g, PitchGrid)
    assert g.name == "d_minor_triad"


# ----------------------------------------------------------------------
# from_range
# ----------------------------------------------------------------------

def test_from_range_basic_semis():
    g = PitchGrid.from_range(low_midi=60, high_midi=64, step=1.0, name="range")
    assert isinstance(g, PitchGrid)
    assert g.name == "range"
    # with series logic high is inclusive-ish → 60,61,62,63,64
    for m in [60.0, 61.0, 62.0, 63.0, 64.0]:
        assert m in g
    assert len(g) == 5


def test_from_range_reversed_bounds():
    g = PitchGrid.from_range(low_midi=64, high_midi=60, step=1.0)
    for m in [60.0, 61.0, 62.0, 63.0, 64.0]:
        assert m in g


def test_from_range_invalid_step():
    with pytest.raises(ValueError):
        PitchGrid.from_range(low_midi=60, high_midi=64, step=0.0)


# ----------------------------------------------------------------------
# fromChurchModes
# ----------------------------------------------------------------------

@pytest.mark.parametrize("mode", SCALE_MASKS_12TET.keys())
def test_fromChurchModes_all_modes(mode):
    min_midi = note2midi("c3")
    max_midi = note2midi("c5")
    g = PitchGrid.fromChurchModes(
        mode=mode,
        root="c4",
        min_midi=min_midi,
        max_midi=max_midi,
    )
    assert isinstance(g, PitchGrid)
    # every pitch class should come from the mask
    pcs = SCALE_MASKS_12TET[mode]
    root_midi = note2midi("c4")
    for v in g:
        pc = (v - root_midi) % 12.0
        # allow small float error
        assert any(abs(pc - p) < 1e-6 for p in pcs)


def test_fromChurchModes_unknown():
    with pytest.raises(KeyError):
        PitchGrid.fromChurchModes(
            mode="does_not_exist",
            root="c4",
            min_midi=60,
            max_midi=72,
        )


# ----------------------------------------------------------------------
# from_sruti_raga
# ----------------------------------------------------------------------

def test_from_sruti_raga_abhogi():
    min_midi = note2midi("c3")
    max_midi = note2midi("c5")
    g = PitchGrid.from_sruti_raga(
        raga_name="abhogi",
        root="c4",
        min_midi=min_midi,
        max_midi=max_midi,
    )
    assert isinstance(g, PitchGrid)
    pcs = get_sruti_mask("abhogi")
    root_midi = note2midi("c4")
    for v in g:
        pc = (v - root_midi) % 12.0
        assert any(abs(pc - p) < 1e-6 for p in pcs)


def test_from_sruti_raga_unknown():
    with pytest.raises(KeyError):
        PitchGrid.from_sruti_raga(
            raga_name="nonexistent_raga",
            root="c4",
            min_midi=60,
            max_midi=72,
        )


# ----------------------------------------------------------------------
# _edo_pitch_classes / EDO_SYSTEMS
# ----------------------------------------------------------------------

def test__edo_pitch_classes_12():
    pcs = _edo_pitch_classes(12)
    assert len(pcs) == 12
    # step should be approx 1 semitone
    steps = [pcs[i+1] - pcs[i] for i in range(11)]
    for s in steps:
        assert math.isclose(s, 1.0, rel_tol=1e-6, abs_tol=1e-6)
    assert math.isclose(pcs[0], 0.0, abs_tol=1e-6)
    assert math.isclose(pcs[-1], 11.0, abs_tol=1e-6)


def test_EDO_SYSTEMS_keys_and_lengths():
    assert set(EDO_SYSTEMS.keys()) == {
        "edo11", "edo12", "edo22", "edo24", "edo53", "edo72"
    }
    assert len(EDO_SYSTEMS["edo12"]) == 12
    assert len(EDO_SYSTEMS["edo22"]) == 22
    assert len(EDO_SYSTEMS["edo24"]) == 24
    assert len(EDO_SYSTEMS["edo53"]) == 53
    assert len(EDO_SYSTEMS["edo72"]) == 72


# ----------------------------------------------------------------------
# PARTCH_43
# ----------------------------------------------------------------------

def test_PARTCH_43_length_and_range():
    assert len(PARTCH_43) == 43
    # should span close to 0..12
    assert min(PARTCH_43) >= 0.0
    assert max(PARTCH_43) <= 12.0


# ----------------------------------------------------------------------
# HISTORICAL_EUROPEAN_TUNINGS / NON_EUROPEAN_TUNINGS
# ----------------------------------------------------------------------

def test_historical_european_tunings_have_12_pcs():
    for name, pcs in HISTORICAL_EUROPEAN_TUNINGS.items():
        assert len(pcs) == 12
        assert all(0.0 <= x < 12.0 for x in pcs), f"{name} out of range"


def test_non_european_shruti_has_expected_keys():
    shruti = NON_EUROPEAN_TUNINGS["ShrutiJustIntonation"]
    # spot-check a few known swaras
    assert pytest.approx(shruti["Sa"], rel=1e-6) == 0.0
    assert "Ri2" in shruti
    assert "Ga2" in shruti
    assert "Ma1" in shruti
    assert "Dha2" in shruti
    assert "Ni4" in shruti
    assert all(0.0 <= v < 12.0 for v in shruti.values())


# ----------------------------------------------------------------------
# SCALE_MASKS_22SRUTI / get_sruti_mask
# ----------------------------------------------------------------------

def test_scale_masks_22sruti_abhogi_matches_shruti():
    shruti = NON_EUROPEAN_TUNINGS["ShrutiJustIntonation"]
    abhogi_pcs = SCALE_MASKS_22SRUTI["abhogi"]
    expected = [shruti[k] for k in ("Sa", "Ri2", "Ga2", "Ma1", "Dha2")]
    assert len(abhogi_pcs) == len(expected)
    for got, exp in zip(abhogi_pcs, expected):
        assert math.isclose(got, exp, rel_tol=1e-6, abs_tol=1e-6)


def test_get_sruti_mask_ok_and_fail():
    pcs = get_sruti_mask("abhogi")
    assert isinstance(pcs, list)
    assert len(pcs) > 0

    with pytest.raises(KeyError):
        get_sruti_mask("nonexistent_raga")


# ----------------------------------------------------------------------
# get_system_pitch_classes
# ----------------------------------------------------------------------

def test_get_system_pitch_classes_edo_and_historical():
    # edo
    pcs12 = get_system_pitch_classes("edo12")
    assert pcs12 == EDO_SYSTEMS["edo12"]

    # historical
    w3 = get_system_pitch_classes("werckmeister3")
    assert w3 == HISTORICAL_EUROPEAN_TUNINGS["werckmeister3"]

    # partch
    p = get_system_pitch_classes("partch43")
    assert p == PARTCH_43


def test_get_system_pitch_classes_unknown():
    with pytest.raises(KeyError):
        get_system_pitch_classes("made_up_system")


# ----------------------------------------------------------------------
# SCALE_MASKS_12TET sanity
# ----------------------------------------------------------------------

def test_scale_masks_12tet_structure():
    # 7 notes per scale (church modes)
    for mode, pcs in SCALE_MASKS_12TET.items():
        assert len(pcs) == 7, f"{mode} should have 7 scale degrees"
        assert all(0 <= p < 12 for p in pcs)