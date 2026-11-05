import mido
import pytest

import GreasyPidgin as gp
from GreasyPidgin import Gesture, MarkovChain, Phonon
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.GreasyPidgin import GreasyPidgin


def test_top_level_object_builds():
    # README install check: print(GreasyPidgin())
    assert gp.GreasyPidgin is GreasyPidgin
    assert "GREASY" in repr(GreasyPidgin())


def test_instances_do_not_share_state():
    a, b = GreasyPidgin("a"), GreasyPidgin("b")
    assert a.timeGrid is not b.timeGrid
    assert a.ensemble is not b.ensemble


def test_temporal_objects_become_children():
    assert len(GreasyPidgin(temporalObjects=[Phonon()]).children) == 1


def test_envelope_modifier_returns_copy():
    env = Envelope([0, 1, 0])
    before = env.getValue(0.5)
    out = env.withBounds(minEnv=10, maxEnv=20)
    assert out is not env
    assert env.getValue(0.5) == before
    assert out.getValue(0.5) == pytest.approx(10 + before * 10)  # squeezed between floor 10 and ceiling 20


def test_markov_follows_only_learned_transitions():
    m = MarkovChain()
    m.generateRulesFromList([1, 2, 1, 2], order=1, wrap=True)
    assert set(m.getNElements(seed=1, n=6)) <= {1, 2}


def test_gesture_writes_midi(tmp_path):
    path = tmp_path / "g.mid"
    Gesture.fromLists(3, pitches=[60, 62, 64], bpm=120).toMidi(str(path))
    notes = [m for m in mido.MidiFile(str(path)) if m.type == "note_on" and m.velocity > 0]
    assert [m.note for m in notes] == [60, 62, 64]
