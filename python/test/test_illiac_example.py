import sys
from pathlib import Path

import mido
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "illiac_suite_4"))
import illiac4_constrained
import illiac4_original
from illiac_common import (EIGHTHS_PER_TABLE, INTERVAL_ORDER, VOICES, anyParallel,
                           isTriad, stageOf, writeScore)


def allowedSteps(stage):
    return {s for i in INTERVAL_ORDER[:stage + 1] for s in (i, -i)}


def checkTables(pitches):
    assert len(pitches) == len(VOICES)
    for (_, _, (low, high)), voice in zip(VOICES, pitches):
        assert len(voice) == len(INTERVAL_ORDER) * EIGHTHS_PER_TABLE + 1
        assert all(low <= p <= high for p in voice)
        for i in range(1, len(voice)):
            assert voice[i] - voice[i - 1] in allowedSteps(stageOf(i))


@pytest.mark.parametrize("seed", range(5))
def test_original_follows_tables(seed):
    checkTables(illiac4_original.compose(seed))


@pytest.mark.parametrize("seed", range(5))
def test_constrained_follows_tables_and_rules(seed):
    pitches, _ = illiac4_constrained.compose(seed)
    checkTables(pitches)
    chords = list(zip(*pitches))
    assert all(isTriad(c) for c in chords)
    assert not any(anyParallel(a, b) for a, b in zip(chords, chords[1:]))


def test_first_table_is_only_unison():
    for pitches in (illiac4_original.compose(0), illiac4_constrained.compose(0)[0]):
        assert all(len(set(v[:EIGHTHS_PER_TABLE])) == 1 for v in pitches)


def test_score_files(tmp_path):
    pitches, _ = illiac4_constrained.compose(0)
    writeScore(pitches, str(tmp_path / "x"), "t")
    tracks = mido.MidiFile(str(tmp_path / "x.mid")).tracks
    assert len(tracks) == len(VOICES)
    for track, voice in zip(tracks, pitches):
        played = [m.note for m in track if m.type == "note_on" and m.velocity > 0]
        tied = [p for i, p in enumerate(voice) if i == 0 or p != voice[i - 1]]
        assert played == tied
    m21 = pytest.importorskip("music21")
    score = m21.converter.parse(str(tmp_path / "x.musicxml"))
    assert len(score.parts) == len(VOICES)
    assert len(score.parts[0].getElementsByClass("Measure")) == 27   # 26 bars of tables + final bar
