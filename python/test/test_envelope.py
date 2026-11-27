import pytest
import numpy as np

from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Grid import Grid


def test_empty_envelope_has_attributes():
    e = Envelope()
    assert e.points == [] and e.x_range is None and e.reducedEnv is None
    assert "pointsNorm=[]" in repr(e)


def test_reduce_keeps_ends_and_extrema_in_original_units():
    e = Envelope([0, 1, 0, 0.5, 0, 1])
    r = e.reduceEnvPoints(numMinima=1, numMaxima=1, resolution=51)
    xs = [r._x_from_norm(x) for x, _ in r.points]
    assert r is e.reducedEnv and len(r.points) == 4
    assert xs[0] == 0 and xs[-1] == 5 and r.x_range == (0, 5)


def test_render_includes_end():
    assert Envelope([0, 1])._internalRenderNorm(5) == [0, 0.25, 0.5, 0.75, 1]


def test_map_to_empty_grid():
    assert Envelope([0, 1]).mapToGrid(Grid(), Grid.series(0, 1, 128)) == []


def test_numpy_input():
    assert Envelope(np.array([0.0, 1.0, 0.0])).getValue(1) == 1


def test_stats_match_curve_on_flat_range():
    e = Envelope([0, 1]).rescale(new_y_range=(3, 3))
    assert e.getValue(1) == 3 and e.mean_y() == 3


def test_with_bounds_keeps_x_range():
    assert Envelope([7]).withBounds(0, 10).x_range == (0, 0)


def test_reverse_is_retrograde_and_keeps_curve_shapes():
    row = Envelope([60, 62, 61, 65, 64])
    assert [row.reverse().getValue(x, True, False) for x in (0, 0.25, 0.5, 0.75, 1)] == [64, 65, 61, 62, 60]
    e = Envelope([[0, 60], [1, 72], [3, 55], [4, 67]], curves=["exp", "easeIn", 2.5])
    r = e.reverse()
    assert r.getCurves() == [-2.5, "easeOut", "log"]
    assert all(abs(e.getValue(x, False, False) - r.getValue(4 - x, False, False)) < 1e-9 for x in (0, 0.3, 1.7, 2.2, 3.9))
    assert e.getValue(1.5, False, False) == e.reverse().reverse().getValue(1.5, False, False)


def test_inverse_mirrors_around_first_value_center_or_number():
    row = Envelope([60, 62, 61, 65, 64])
    xs = (0, 0.25, 0.5, 0.75, 1)
    assert [row.inverse().getValue(x, True, False) for x in xs] == [60, 58, 59, 55, 56]
    assert [row.inverse("center").getValue(x, True, False) for x in xs] == [65, 63, 64, 60, 61]
    assert [row.inverse(0).getValue(x, True, False) for x in xs] == [-60, -62, -61, -65, -64]
    assert row.inverse(overwriteOriginal=True) is row and row.getValue(1, True, False) == 56
    with pytest.raises(ValueError):
        row.inverse("up")
