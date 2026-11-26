import pytest

from GreasyPidgin import Gesture, GreasyPidgin, Phonon, Phrase
from GreasyPidgin.Ensemble import Ensemble
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Instruments import STANDARD_INSTRUMENTS
from GreasyPidgin.Perceptron import Perceptron


def test_microtonal_missing_notes_are_detected():
    assert STANDARD_INSTRUMENTS["flute"].in_range(60.5) == (False, None)
    assert STANDARD_INSTRUMENTS["flute"].in_range(61) == (True, None)


def test_force_in_range_rounds_microtones_when_not_allowed():
    rec = STANDARD_INSTRUMENTS["sopranino-recorder"]
    assert rec.force_in_range(66.5) == 66


def test_ensemble_numbers_duplicate_names():
    e = Ensemble(["flute", "flute", "oboe"])
    assert e.players == ["flute", "flute_2", "oboe"]
    assert e.getPlayer("flute_2") is e["flute_2"]


def test_phrase_time_unit_beats():
    p = Phrase(0, {0: None, 1: Phonon(0, 1, 60)}, {"s": Envelope([(0, 1), (2, 1)])}, bpm=120, timeUnit='beats')
    assert [c.startTimeSec for c in p.children] == [0, 1]


def test_phrase_stretches_gesture_to_its_slot():
    g = Gesture(0, [Phonon(0, 1, 60), Phonon(1, 1, 62)])
    p = Phrase(0, {0: None, 1: g}, {"s": Envelope([(0, 1), (1, 0)])})
    assert [(l.startTimeSec, l.endTimeSec) for l in p.flatten()] == [(0, 0.5), (0.5, 1)]


def test_greasypidgin_rejects_non_dynamicgrid():
    with pytest.raises(TypeError):
        GreasyPidgin(dynamicGrid=[1, 2])


def test_perceptron_rejects_unknown_activation():
    with pytest.raises(ValueError):
        Perceptron(activationFunction="sigmoid")
