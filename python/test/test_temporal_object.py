import time

from GreasyPidgin import Phonon, Phrase
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Grid import Grid
from GreasyPidgin.TemporalObject import TemporalObject as TO


def test_overlap_min_duration_trims_long_note():
    p = TO(0, 0, [TO(0, 5), TO(0.05, 1)])
    p.resolveChildOverlaps(minDurationSec=0.1)
    a, b = p.children
    assert a.durationSec == 0.1 and a.endTimeSec <= b.startTimeSec


def test_clone_keeps_subclass_attributes():
    phrase = Phrase(0, {0: None, 1: Phonon(0, 1, 60)}, {"s": Envelope([(0, 1), (1, 1)])})
    copy = phrase.clone()
    assert copy.voices.keys() == phrase.voices.keys() and copy.id != phrase.id
    assert copy.children[0] is not phrase.children[0]


def test_stretch_container_scales_children():
    c = TO(0, 0, [TO(1, 1)])
    c.stretchTime(2)
    assert c.durationSec == 4
    assert [(l.startTimeSec, l.durationSec) for l in c.flatten()] == [(2, 2)]


def test_quantise_container_keeps_its_start():
    g = TO(10, 0, [TO(0.2, 0.7)])
    g.quantiseTime(Grid([0, 10, 10.5, 11]))
    assert g.startTimeSec == 10
    assert [(l.startTimeSec, l.endTimeSec) for l in g.flatten()] == [(10, 11)]


def test_add_child_is_not_quadratic():
    t = time.time()
    c = TO(0)
    for i in range(400):
        c.addChild(TO(i * 0.1, 0.1))
    assert time.time() - t < 1.0
    assert abs(c.durationSec - 40) < 1e-9
