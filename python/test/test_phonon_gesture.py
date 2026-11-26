import mido
import pytest

from GreasyPidgin import Gesture, Phonon, TimeGrid
from GreasyPidgin.Envelope import Envelope


def onsets(path):
    mf = mido.MidiFile(path)
    tempo = next(m.tempo for m in mf.tracks[0] if m.type == "set_tempo")
    t, out = 0.0, []
    for m in mido.merge_tracks(mf.tracks):
        t += mido.tick2second(m.time, mf.ticks_per_beat, tempo)
        if m.type == "note_on" and m.velocity > 0:
            out.append((round(t, 3), m.note, m.velocity))
    return out


def test_default_unfold_follows_chord_or_seq(tmp_path):
    Phonon(0, 3, [60, 62, 64]).toMidi(str(tmp_path / "s.mid"))
    assert [n for _, n, _ in onsets(tmp_path / "s.mid")] == [60, 62, 64]


def test_chord_seq_keeps_voice_slots():
    p = Phonon(0, 4, [[60, 64, 67], [62], [], [65, 69]], chordOrSeq='cs')
    p.unfold()
    assert sorted((c.startTimeSec, c.data["pitchMidi"]) for c in p.children) == [
        (0, 60), (0, 64), (0, 67), (1, 62), (3, 65), (3, 69)]


def test_glissando_exports_json(tmp_path):
    p = Phonon(0, 1, 60)
    p.glissando(60, 62)
    p.toJson(str(tmp_path / "g.json"))
    assert p.data["glissandoMidi"] == (60, 62)


def test_gesture_tempo_applies_to_all_notes(tmp_path):
    Gesture(0, [Phonon(1.0, 0.5, 60)], bpm=120).toMidi(str(tmp_path / "b.mid"))
    assert onsets(tmp_path / "b.mid")[0][0] == 1.0


def test_midi_velocity_round_trip(tmp_path):
    Gesture.fromLists(3, pitches=[60], dynamics=[20, 64, 127]).toMidi(str(tmp_path / "a.mid"))
    Gesture.fromMidiFile(str(tmp_path / "a.mid")).toMidi(str(tmp_path / "b.mid"))
    assert [v for *_, v in onsets(tmp_path / "b.mid")] == [20, 64, 127]


def test_midi_import_tempo_changes_and_channels(tmp_path):
    mf = mido.MidiFile(ticks_per_beat=480)
    mf.tracks.append(mido.MidiTrack([
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60), time=0),
        mido.Message("note_on", note=60, velocity=90, time=0),
        mido.Message("note_off", note=60, time=480),
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0),
        mido.Message("note_on", note=62, velocity=90, channel=1, time=0),
        mido.Message("note_on", note=62, velocity=50, channel=2, time=0),
        mido.Message("note_off", note=62, channel=2, time=240),
        mido.Message("note_off", note=62, channel=1, time=480),
    ]))
    mf.save(tmp_path / "t.mid")
    g = Gesture.fromMidiFile(str(tmp_path / "t.mid"))
    assert [(c.startTimeSec, c.durationSec) for c in g.children] == [(0, 1), (1, 0.25), (1, 0.75)]


def test_hairpin_aftertouch_in_velocity_units(tmp_path):
    Phonon(0, 1, 60, dynamic="pp-ff").toMidi(str(tmp_path / "h.mid"))
    at = [m.value for m in mido.MidiFile(tmp_path / "h.mid") if m.type == "aftertouch"]
    assert (at[0], at[-1]) == (33, 112)


def test_envelope_dynamic_sets_velocity(tmp_path):
    Phonon(0, 4, 60, dynamic=Envelope([(0, 20), (2, 127), (4, 60)])).toMidi(str(tmp_path / "e.mid"))
    assert onsets(tmp_path / "e.mid")[0][2] == 20


def test_quantise_survives_earlier_unfold(tmp_path):
    g = Gesture.fromLists(2, startDeltas=0.33, durations=0.3, pitches=[60])
    g.toMidi(str(tmp_path / "a.mid"))
    g.quantiseTime(TimeGrid.series(0, 0.25, 20))
    g.toMidi(str(tmp_path / "b.mid"))
    assert [t for t, *_ in onsets(tmp_path / "b.mid")] == [0, 0.25]


def test_from_lists_accepts_markings():
    assert Gesture.fromLists(2, pitches=[60], dynamics=["pp", "mf-ff"]).getDynamicMarkings() == ["pp", "mf-ff"]


def test_empty_pitch_raises():
    with pytest.raises(ValueError):
        Phonon(0, 1, [])


def test_nested_gesture_quantise_uses_absolute_time():
    outer = Gesture(10, [Gesture(2, [Phonon(0.3, 1, 60)])])
    outer.quantiseTime(TimeGrid.series(0, 0.5, 40))
    assert [leaf.startTimeSec for leaf in outer.flatten()] == [12.5]
