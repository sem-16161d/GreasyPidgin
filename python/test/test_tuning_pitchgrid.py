import random

import numpy as np
import pytest

from GreasyPidgin import PitchGrid, TuningSystem, TUNING_SYSTEMS
from GreasyPidgin.IterableOperations import flatten, isNested
from GreasyPidgin.Normalisation import normaliseValues, scale
from GreasyPidgin.Pitch import mtospn, spntom


def test_scale_numpy_and_curved_below_range():
    assert scale(np.int64(5), 0, 10, 0, 1) == 0.5
    assert scale(-1, 0, 10, 0, 1, 0.5) == pytest.approx(-(0.1 ** 0.5))


def test_normalise_any_iterable():
    assert normaliseValues(np.array([1.0, 3.0, 2.0])) == [0, 1, 0.5]


def test_flatten_keeps_strings():
    assert list(flatten(["c4", ["d4", ("e4",)]])) == ["c4", "d4", "e4"]
    assert not isNested([])


def test_non_repeating_equal_steps():
    stria = sorted(PitchGrid.fromTuningSystem("stria", 48, 84))
    assert len(stria) == 5 and stria[1] - stria[0] == pytest.approx(12 * np.log2((1 + 5 ** 0.5) / 2))


def test_twelve_step_masks_only_on_twelve_step_systems():
    assert set(TUNING_SYSTEMS["JI_5limit_major"].scaleMasks) == {"chromatic"}
    with pytest.raises(KeyError):
        PitchGrid.fromMask("JI_5limit_major", "dorian", 60, 72)


def test_from_semitones_defaults_to_octave():
    assert TuningSystem.fromSemitones("x", [0, 2, 4, 5, 7, 9, 11]).repeatIntervalSemitones == 12


def test_repeat_boundary_is_not_a_pitch_class():
    assert len(TUNING_SYSTEMS["harmonicSeries8_16"].pitchClasses) == 8


def test_gamelan_repeats_by_octave():
    assert len(PitchGrid.fromTuningSystem("slendro_approx", 48, 84)) == 16


def test_mtospn_round_trip():
    assert [mtospn(m) for m in (60, 61, 60.5, 0)] == ["c4", "cs4", "cqs4", "c-1"]
    assert all(abs(spntom(mtospn(m / 6)) - m / 6) < 1e-9 for m in range(768))


def test_chord_spn_and_narrow_range():
    random.seed(1)
    pg = PitchGrid.fromMask("edo12", "ionian", 48, 84)
    assert pg.makeChordFromTopNote("c5", pitchUnit="spn")[0] == "c5"
    chord = pg.makeChordFromTopNote(72, minPitch=66)
    assert all(66 <= p <= 72 for p in chord)


def test_random_contour_changes():
    pg = PitchGrid.fromMask("edo24", "chromatic", 48, 84)
    assert pg.melodicContourFromEnvelope(numNotes=8) != pg.melodicContourFromEnvelope(numNotes=8)
