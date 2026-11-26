import os
import subprocess
import sys

import numpy as np
import pytest

from GreasyPidgin import Gesture, Phonon, TemporalObject, TimeGrid, spntof
from GreasyPidgin.Ensemble import Ensemble
from GreasyPidgin.Normalisation import scale
from GreasyPidgin.Perceptron import Perceptron


def test_time_grid_relative_times():
    tg = TimeGrid([0, 1, 3])
    assert tg.toRelativeTimes() == [1, 2]
    assert isinstance(tg.getSelfSimilarity(), float)


def test_spntof_uses_reference():
    assert spntof("a4", 443) == pytest.approx(443)


def test_ids_unique_across_subclasses():
    ids = [Phonon().id, Gesture().id, TemporalObject().id]
    assert len(set(ids)) == 3


def test_scale_reversed_input_range():
    assert scale(0, 1, 0, 0, 10) == 10
    assert scale(1, 1, 0, 0, 10) == 0


def test_ensemble_get_player():
    assert Ensemble(["flute"]).getPlayer("flute").name == "flute"
    assert Ensemble(["flute"]).getPlayer("oboe") is None


def test_perceptron_identity_learns():
    p = Perceptron(learning_rate=0.05, n_iterations=2000)
    p.fit(np.array([[1.0], [2.0]]), np.array([2.0, 4.0]))
    assert p.predict(np.array([3.0])) == pytest.approx(6.0, abs=0.1)


def test_from_lists_start_offset_applied_once():
    g = Gesture.fromLists(2, startOffset=2.0, startDeltas=1.0, durations=0.5, pitches=[60])
    assert [round(leaf.startTimeSec, 6) for leaf in g.flatten()] == [2.0, 3.0]


def test_import_does_not_load_pyplot():
    code = "import GreasyPidgin, sys; print('matplotlib.pyplot' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
    assert out.stdout.strip().endswith("False")
