import random
import statistics

import pytest

from GreasyPidgin import CellularAutomaton, CellularRules, MarkovChain, RQQ, TimeGrid
from GreasyPidgin.TimeGrid import Rest


def test_rest_only_rqq_has_no_onsets():
    assert RQQ(1, [Rest(1)]).startsBeats == []
    assert RQQ(2, [Rest(1), Rest(1)]).startsBeats == []
    assert RQQ(5, [1, 1, Rest(1), 2]).startsBeats == [0, 1, 3]


def test_from_rqq_leaves_input_alone():
    r = RQQ(2, [1, 1])
    assert TimeGrid.fromRQQ(r, startTimeSec=3, bpm=120).sorted() == [3, 3.5]
    assert r.startOffsetBeats == 0 and r.bpm == 60


def test_density_with_leaning_hits_expected_count():
    random.seed(0)
    assert 40 < statistics.mean(len(TimeGrid.fromDensity(0, 10, 5, leaning=-0.5)) for _ in range(30)) < 60


def test_density_curve_starts_at_grid_start():
    tg = TimeGrid([10, 10.5, 11, 11.5], startTimeSec=10, endTimeSec=12)
    assert tg.getDensityCurve(1, 1)["density"] == [1, 3, 2]


def test_sample_keeps_span():
    assert TimeGrid.series(0, 1, 8).sample(3).endTimeSec == 8


def test_self_similarity_range_and_speed():
    assert TimeGrid.series(0, 0.5, 32).getSelfSimilarity() == 1
    assert 0 <= TimeGrid.fromDensity(0, 60, 20).getSelfSimilarity() <= 1


def test_euclid_patterns():
    assert TimeGrid.fromEuclidean(3, 8).sorted() == [0, 3, 6]
    assert TimeGrid.fromEuclidean(5, 8).sorted() == [0, 2, 3, 5, 6]


def test_ca_restart_drops_later_generations():
    ca = CellularAutomaton(rules=CellularRules.elementaryWolfram(30))
    ca.gen0fromSingleCell(9)
    ca.iterate(6)
    ca.iterate(2, startIndex=1)
    assert sorted(ca.generations) == [0, 1, 2, 3]


def test_ca_errors():
    with pytest.raises(ValueError):
        CellularAutomaton().iterate(1)
    with pytest.raises(ValueError):
        CellularAutomaton(rules=CellularRules.elementaryWolfram(30)).gen0fromInteger(-5)


def test_markov_none_is_a_symbol():
    m = MarkovChain()
    m.generateRulesFromList([60, None, 62, None, 60, 62], order=1)
    assert len(m.getNElements(seed=60, n=8)) == 9
