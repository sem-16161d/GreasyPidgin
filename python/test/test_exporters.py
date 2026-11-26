import mido

from GreasyPidgin import Gesture, Phonon


def messages(path):
    t, out = 0, []
    for m in mido.MidiFile(path).tracks[0]:
        t += m.time
        if m.type in ("note_on", "note_off", "pitchwheel"):
            out.append((t, m.type, m.channel, getattr(m, "note", None), getattr(m, "pitch", None)))
    return out


def test_microtonal_chord_gets_one_channel_per_note(tmp_path):
    Phonon(0, 1, [60, 60.5, 64.25], chordOrSeq='c').toMidi(str(tmp_path / "m.mid"))
    msgs = messages(tmp_path / "m.mid")
    ons = [m for m in msgs if m[1] == "note_on"]
    assert len({m[2] for m in ons}) == 3
    for _, _, ch, _, _ in ons:   # the channel's bend comes before its note-on
        bend_i = next(i for i, m in enumerate(msgs) if m[1] == "pitchwheel" and m[2] == ch)
        on_i = next(i for i, m in enumerate(msgs) if m[1] == "note_on" and m[2] == ch)
        assert bend_i < on_i
    assert sorted(m[4] for m in msgs if m[1] == "pitchwheel") == [0, 1024, 2048]


def test_unbent_notes_stay_on_one_channel(tmp_path):
    Gesture.fromLists(4, startDeltas=1, durations=1, pitches=[60, [64, 67]]).toMidi(str(tmp_path / "p.mid"))
    assert {m[2] for m in messages(tmp_path / "p.mid")} == {0}


def test_note_off_before_note_on_at_same_tick(tmp_path):
    Gesture.fromLists(2, startDeltas=1, durations=1, pitches=[60]).toMidi(str(tmp_path / "l.mid"))
    kinds = [m[1] for m in messages(tmp_path / "l.mid") if m[0] == 480 and m[1] != "pitchwheel"]
    assert kinds == ["note_off", "note_on"]


def test_musicxml_writes_microtones(tmp_path):
    Phonon(0, 2, [60.5, 61.5], chordOrSeq='c').toXml(str(tmp_path / "m.xml"))
    assert "quarter-sharp" in (tmp_path / "m.xml").read_text()
