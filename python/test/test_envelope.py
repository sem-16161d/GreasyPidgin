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
