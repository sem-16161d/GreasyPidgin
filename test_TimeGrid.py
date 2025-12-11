import math
import pytest

from GreasyPidgin.TimeGrid import TimeGrid  # or `from TimeGrid import TimeGrid`


# ---------------------------------------------------------------------------
# Constructor behaviour
# ---------------------------------------------------------------------------

def test_init_beats_only_default_subdivision():
    tg = TimeGrid(durationBeats=4, bpm=120, possibleSubdivision=[1])

    # durations
    assert tg.durationBeats == pytest.approx(4.0)
    assert tg.durationSec == pytest.approx(4 * 60.0 / 120.0)  # 2.0s

    # subdivision [1] → whole beats 0,1,2,3,4
    assert tg.possibleSubdivision == [1]
    assert 0.0 in tg
    assert 1.0 in tg
    assert 2.0 in tg
    assert 3.0 in tg
    assert 4.0 in tg
    # nothing beyond 4
    assert all(0.0 <= x <= 4.0 for x in tg)


def test_init_seconds_only():
    tg = TimeGrid(durationSec=3.0, bpm=60, possibleSubdivision=[1])
    # 3 seconds at 60 bpm = 3 beats
    assert tg.durationSec == pytest.approx(3.0)
    assert tg.durationBeats == pytest.approx(3.0)
    assert max(tg) == pytest.approx(3.0)


def test_init_both_matching_no_warning():
    # durationSec = 2s, bpm = 120 → 4 beats, so matching
    tg = TimeGrid(durationSec=2.0, durationBeats=4.0, bpm=120, possibleSubdivision=[1])

    assert tg.durationSec == pytest.approx(2.0)
    assert tg.durationBeats == pytest.approx(4.0)


def test_init_both_mismatch_warns_and_uses_larger():
    # durationSec=2, bpm=60 → beats_from_sec = 2
    # durationBeats=3 → mismatch, should warn and use 3 beats (the larger)
    with pytest.warns(UserWarning) as rec:
        tg = TimeGrid(durationSec=2.0, durationBeats=3.0, bpm=60, possibleSubdivision=[1])

    assert len(rec) == 1
    assert tg.durationBeats == pytest.approx(3.0)
    assert tg.durationSec == pytest.approx(3.0)  # 3 beats at 60 bpm = 3s


def test_init_requires_some_duration():
    with pytest.raises(ValueError):
        TimeGrid(durationSec=None, durationBeats=None)


# ---------------------------------------------------------------------------
# Subdivision / internal sub-grids
# ---------------------------------------------------------------------------

def test_multiple_subdivisions_union():
    tg = TimeGrid(durationBeats=1.0, bpm=120, possibleSubdivision=[2, 3])

    # We should have two sub-grids recorded
    assert set(tg.grids.keys()) == {2, 3}

    g2 = tg.grids[2]
    g3 = tg.grids[3]

    # [2] → 0, 0.5, 1.0
    assert g2 == {0.0, 0.5, 1.0}

    # [3] → 0, 1/3, 2/3, 1.0 (within float tolerance)
    assert len(g3) == 4
    assert 0.0 in g3

    one_third = 1.0 / 3.0
    two_thirds = 2.0 / 3.0

    assert any(x == pytest.approx(one_third, rel=1e-9) for x in g3)
    assert any(x == pytest.approx(two_thirds, rel=1e-9) for x in g3)
    assert any(x == pytest.approx(1.0) for x in g3)

    # Union grid (TimeGrid itself) should contain all unique points
    # {0, 1/3, 0.5, 2/3, 1}
    assert len(tg) == 5
    for v in g2.union(g3):
        assert v in tg


def test_subdivision_must_be_positive():
    # trigger _make_single_subdivision_grid indirectly by bad subdiv
    tg = TimeGrid(durationBeats=1.0, possibleSubdivision=[1])
    with pytest.raises(ValueError):
        tg._make_single_subdivision_grid(0)


# ---------------------------------------------------------------------------
# Time conversion helpers
# ---------------------------------------------------------------------------

def test_beat_to_sec_and_sec_to_beat_roundtrip():
    tg = TimeGrid(durationBeats=4, bpm=120, possibleSubdivision=[1])

    # 1 beat at 120 bpm = 0.5 seconds
    s = tg.beat_to_sec(1.0)
    assert s == pytest.approx(0.5)

    b = tg.sec_to_beat(s)
    assert b == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# extend_to_beat
# ---------------------------------------------------------------------------

def test_extend_to_beat():
    tg = TimeGrid(durationBeats=1.0, bpm=120, possibleSubdivision=[2])  # 0,0.5,1.0
    assert tg.durationBeats == pytest.approx(1.0)
    assert max(tg) == pytest.approx(1.0)

    tg.extend_to_beat(3.0)

    assert tg.durationBeats == pytest.approx(3.0)
    # now subdivision[2] over 3 beats → 0..3 in steps of 0.5
    g2 = tg.grids[2]
    assert max(g2) == pytest.approx(3.0)
    assert 2.5 in g2
    assert 3.0 in g2

    # union grid updated too
    assert max(tg) == pytest.approx(3.0)


def test_extend_to_beat_no_op_if_inside():
    tg = TimeGrid(durationBeats=2.0, bpm=120, possibleSubdivision=[1])
    before_points = set(tg)
    tg.extend_to_beat(1.5)  # already covered
    assert set(tg) == before_points
    assert tg.durationBeats == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Quantisation in beats
# ---------------------------------------------------------------------------

def test_quantize_beat_union_grid():
    tg = TimeGrid(durationBeats=4.0, bpm=120, possibleSubdivision=[1])  # 0..4

    # halfway between 1 and 2 is 1.5 → either is equally close;
    # but for something like 1.49 → 1, 1.51 → 2
    assert tg.quantize_beat(1.49) == pytest.approx(1.0)
    assert tg.quantize_beat(1.51) == pytest.approx(2.0)


def test_quantize_beat_specific_subdivision():
    tg = TimeGrid(durationBeats=1.0, bpm=120, possibleSubdivision=[2, 3])
    # grid[2] has {0, 0.5, 1}, grid[3] has {0, 1/3, 2/3, 1}

    # near 0.4:
    q2 = tg.quantize_beat(0.4, subdivision=2)  # closer to 0.5
    q3 = tg.quantize_beat(0.4, subdivision=3)  # closer to 1/3 ~ 0.333...

    assert q2 == pytest.approx(0.5)
    assert q3 == pytest.approx(1.0 / 3.0)


def test_quantize_beat_invalid_subdivision_raises():
    tg = TimeGrid(durationBeats=1.0, bpm=120, possibleSubdivision=[2])
    with pytest.raises(KeyError):
        tg.quantize_beat(0.3, subdivision=3)


# ---------------------------------------------------------------------------
# Quantisation in seconds
# ---------------------------------------------------------------------------

def test_quantize_sec_roundtrip_with_union_grid():
    # durationBeats=4, bpm=60 → 4 seconds
    tg = TimeGrid(durationBeats=4.0, bpm=60, possibleSubdivision=[1])

    raw_sec = 1.8  # near beat 1.8 → nearest whole beat is 2
    q_sec = tg.quantize_sec(raw_sec)
    # beat 2 at 60 bpm is 2 seconds
    assert q_sec == pytest.approx(2.0)


def test_quantize_sec_with_subdivision():
    # durationBeats=1, bpm=60, subdiv=[2] → beats: 0, 0.5, 1.0
    tg = TimeGrid(durationBeats=1.0, bpm=60, possibleSubdivision=[2])

    # sec ↔ beat: 1 beat = 1 second
    raw_sec = 0.6  # near 0.5 beat
    q_sec = tg.quantize_sec(raw_sec, subdivision=2)
    assert q_sec == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Misc edge / sanity checks
# ---------------------------------------------------------------------------

def test_timegrid_is_grid_subclass():
    tg = TimeGrid(durationBeats=1.0, possibleSubdivision=[1])
    # basic set-like behaviour
    assert isinstance(tg, set)
    assert 0.0 in tg
    assert 1.0 in tg