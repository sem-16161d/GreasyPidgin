# Phonon.py
"""
Phonon — a musical note-event.

Extends TemporalObject with pitch vocabulary (midi / hz / spn),
dynamic, and chord / sequence support.

Pitch is stored as a list of chord slots (self.chordSlots): one slot for a
chord, one single-pitch slot per note for a sequence, one slot per chord for
a chord sequence. Slots are evenly spaced over the duration. Dynamic is
stored as envelopes. Call unfold() to resolve them into TemporalObject
children, then export.

A glissando (glissando()) is stored in data["glissandoMidi"] for analysis
and in data["pitchwheel"] for MIDI export.
"""

from collections import Counter

from GreasyPidgin.Normalisation import scale
from GreasyPidgin.Pitch import ftom, spntom
from GreasyPidgin.Dynamics import parseDynamicMarking
from GreasyPidgin.TimeGrid import beatToSec, secToBeat
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Exporters import MidiExporter, JsonExporter, CsvExporter, MusicXmlExporter

# noteSelectKey used by unfold() when none is given, per chordOrSeq
_DEFAULT_SELECT = {"seq": "seq", "s": "seq", "chord": "chord", "c": "chord",
                   "chordSeq": "chordSeq", "cs": "chordSeq"}

# dB <-> MIDI velocity calibration for dynamicUnit='midi'
_MIN_DB, _MAX_DB, _MIN_VEL, _MAX_VEL = 20.0, 120.0, 1, 127


class Phonon(TemporalObject):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        startTime: float = 0.0,
        duration: float = 0.0,
        pitch: float | int | str | list | tuple = 0,
        dynamic: float | int | list | tuple | Envelope | str = 64,
        bpm: float = 60.0,
        *,
        timeUnit: str = 'seconds',      # 's' / 'beats' / 'b'
        pitchUnit: str = 'midi',        # 'hz' / 'spn'
        dynamicUnit: str = 'midi',      # 'dB'
        chordOrSeq: str = 'seq',        # 'chord'/'c' / 'chordSeq'/'cs'
        autoSortChords: bool = True,
        ticksPerBeat: int = 480,
        envelopes: dict | None = None,
        referenceA: float = 440,
        lyric: str | None = None,
    ) -> None:
        startTimeSec, durationSec = self._toSeconds(startTime, duration, timeUnit, bpm)
        super().__init__(
            startTimeSec=startTimeSec,
            durationSec=durationSec,
            envelopes=envelopes,
            data={"bpm": bpm, "ticksPerBeat": ticksPerBeat},
        )
        self._updateBeats()

        self.pitchUnit      = pitchUnit
        self.autoSortChords = autoSortChords
        self.referenceA     = referenceA
        self.chordOrSeq     = chordOrSeq

        # allPitches     : flat list of every MIDI value, in order
        # chordSlots     : list of chords (lists of MIDI values), evenly spaced
        # pitchEnvelopes : one step Envelope per voice, x in seconds (analysis)
        self.allPitches:     list[float]       = []
        self.chordSlots:     list[list[float]] = []
        self.pitchEnvelopes: list[Envelope]    = []
        self._parsePitch(pitch, pitchUnit, chordOrSeq)

        # dynamic: envelopes["dynamic"] (dB) and, if time-varying,
        # envelopes["aftertouch"] (velocity units) for MIDI export
        self._parseDynamic(dynamic, dynamicUnit, durationSec)

        if lyric is not None:
            self.setLyric(lyric)

    def _updateBeats(self) -> None:
        bpm = float(self.data.get("bpm", 60.0))
        self.startTimeBeats = secToBeat(self.startTimeSec, bpm)
        self.durationBeats  = secToBeat(self.durationSec, bpm)
        self.endTimeBeats   = self.startTimeBeats + self.durationBeats

    @staticmethod
    def _toSeconds(startTime: float, duration: float, timeUnit: str, bpm: float) -> tuple[float, float]:
        match timeUnit:
            case 'seconds' | 's':
                return float(startTime), float(duration)
            case 'beats' | 'b':
                return beatToSec(startTime, bpm), beatToSec(duration, bpm)
            case _:
                raise ValueError(
                    f"Phonon: '{timeUnit}' is not a valid timeUnit. Use 's', 'seconds', 'b', or 'beats'."
                )

    # ------------------------------------------------------------------
    # Pitch parsing
    # ------------------------------------------------------------------

    def _toMidi(self, p: float | int | str, pitchUnit: str) -> float:
        """Convert a single pitch value to MIDI float."""
        if isinstance(p, str):
            return float(spntom(p))
        match pitchUnit:
            case 'midi': return float(p)
            case 'hz':   return float(ftom(p, self.referenceA))
            case 'spn':  return float(spntom(str(p)))
            case _:
                raise ValueError(f"Phonon: unknown pitchUnit '{pitchUnit}'")

    def _parsePitch(self, pitch, pitchUnit: str, chordOrSeq: str) -> None:
        """
        Populate allPitches, chordSlots and pitchEnvelopes.

        seq / s          single value or flat list -> one pitch per slot
        chord / c        flat list -> one slot, all pitches held together
        chordSeq / cs    list of chords (an empty chord is a rest)
        """
        toMidi = lambda p: self._toMidi(p, pitchUnit)
        sortChord = sorted if self.autoSortChords else list
        flat = list(pitch) if isinstance(pitch, (list, tuple)) else [pitch]

        match chordOrSeq:
            case 'seq' | 's' | 'chord' | 'c':
                if any(isinstance(p, (list, tuple)) for p in flat):
                    raise ValueError(
                        "Phonon: nested pitch list passed to seq/chord mode. "
                        "Use chordOrSeq='cs' for chord sequences."
                    )
                pitches = [toMidi(p) for p in flat]
                if chordOrSeq in ('seq', 's'):
                    self.chordSlots = [[p] for p in pitches]
                else:
                    self.chordSlots = [sortChord(pitches)]
            case 'chordSeq' | 'cs':
                if not isinstance(pitch, (list, tuple)):
                    raise ValueError("Phonon: chordSeq requires a list of chords (nested list).")
                self.chordSlots = [
                    sortChord([toMidi(p) for p in slot]) if isinstance(slot, (list, tuple)) else [toMidi(slot)]
                    for slot in pitch
                ]
            case _:
                raise ValueError(
                    f"Phonon: unknown chordOrSeq '{chordOrSeq}'. "
                    "Use 'seq'/'s', 'chord'/'c', or 'chordSeq'/'cs'."
                )

        self.allPitches = [p for chord in self.chordSlots for p in chord]
        if not self.allPitches:
            raise ValueError("Phonon: pitch is empty")
        self.pitchEnvelopes = self._voiceEnvelopes()

    def _voiceEnvelopes(self) -> list[Envelope]:
        """One step envelope per voice (voice v = v-th pitch of each chord),
        x in seconds; slots where a voice is missing are skipped."""
        dur      = self.durationSec
        slotDur  = dur / len(self.chordSlots)
        nVoices  = max(len(c) for c in self.chordSlots)
        envs     = []
        for v in range(nVoices):
            pts = [(i * slotDur, c[v]) for i, c in enumerate(self.chordSlots) if v < len(c)]
            if len(pts) == 1 or dur == 0:
                pts = [pts[0], (dur, pts[0][1])]
            envs.append(Envelope(pts, curves=["step"] * (len(pts) - 1)))
        return envs

    # ------------------------------------------------------------------
    # Dynamic parsing
    # ------------------------------------------------------------------

    def _parseDynamic(self, dynamic, dynamicUnit: str, durationSec: float) -> None:
        """
        Parse dynamic input.

        A single value       -> data["dynamicdB"] (note-on velocity) and a
                                flat envelopes["dynamic"].
        A list or Envelope   -> time-varying: envelopes["dynamic"] in dB and
                                envelopes["aftertouch"] in MIDI velocity units
                                (channel aftertouch on export); the note-on
                                velocity is the first value. A list is spread
                                evenly over the duration, an Envelope keeps its
                                own shape and curves, stretched over the duration.
        A marking string     -> 'pp', 'mf', ... (flat) or a hairpin 'pp-mp',
                                'ff>mp' (time-varying), always velocity-scale;
                                the text is kept in data["dynamicMarking"].

        dynamicUnit 'midi' values are velocities (1..127), mapped to 20..120 dB
        with a calibration the exporter uses to map them back exactly. 'dB'
        values use the exporter's 0..100 dB -> 0..127 velocity window.
        """
        if isinstance(dynamic, str):
            self.data["dynamicMarking"] = dynamic.strip()
            parsed      = parseDynamicMarking(dynamic)
            dynamic     = list(parsed) if isinstance(parsed, tuple) else parsed
            dynamicUnit = 'midi'

        match dynamicUnit:
            case 'midi':
                toDB  = lambda v: scale(v, _MIN_VEL, _MAX_VEL, _MIN_DB, _MAX_DB, clipToRange=True)
                toVel = lambda dB: scale(dB, _MIN_DB, _MAX_DB, _MIN_VEL, _MAX_VEL, clipToRange=True)
                self.data.update(minDb=_MIN_DB, maxDb=_MAX_DB, minVelocity=_MIN_VEL, maxVelocity=_MAX_VEL)
            case 'dB':
                toDB  = float
                toVel = lambda dB: scale(dB, 0.0, 100.0, 0.0, 127.0, clipToRange=True)
                for k in ("minDb", "maxDb", "minVelocity", "maxVelocity"):
                    self.data.pop(k, None)
            case _:
                raise ValueError(f"Phonon: unknown dynamicUnit '{dynamicUnit}'")

        # breakpoints (timeSec, value in dynamicUnit) and their curves
        if isinstance(dynamic, Envelope):
            pts, curves = dynamic._sorted_points_and_curves()
            pts = [(x * durationSec, dynamic._y_from_norm(y, False)) for x, y in pts]
        elif isinstance(dynamic, (list, tuple)):
            if not dynamic:
                raise ValueError("Phonon: dynamic list is empty")
            n = len(dynamic)
            pts = [(i * durationSec / (n - 1) if n > 1 else 0.0, float(v)) for i, v in enumerate(dynamic)]
            curves = None
        else:
            pts, curves = [(0.0, float(dynamic))], None

        timeVarying = len(pts) > 1
        if not timeVarying:
            pts = [pts[0], (durationSec, pts[0][1])]
        dBPts = [(t, toDB(v)) for t, v in pts]

        self.data["dynamicdB"] = dBPts[0][1]
        self.envelopes["dynamic"] = Envelope(dBPts, autosort=False, curves=curves)
        if timeVarying:
            self.envelopes["aftertouch"] = Envelope(
                [(t, toVel(dB)) for t, dB in dBPts], autosort=False, curves=curves)
        else:
            self.envelopes.pop("aftertouch", None)

    # ------------------------------------------------------------------
    # Pitch selection helpers
    # ------------------------------------------------------------------

    def calculatePitch(self, key: str = 'all') -> list[float]:
        """
        Return a subset of allPitches by selection key.

        Keys: 'all', 'lowest', 'highest', 'mostCommon', 'leastCommon', 'chord'/'allSet'
        """
        counts = Counter(round(p, 6) for p in self.allPitches)
        match key:
            case 'all':             return list(self.allPitches)
            case 'chord' | 'allSet': return sorted(set(self.allPitches))
            case 'lowest':          return [min(self.allPitches)]
            case 'highest':         return [max(self.allPitches)]
            case 'mostCommon':      return [counts.most_common(1)[0][0]]
            case 'leastCommon':     return [counts.most_common()[-1][0]]
            case _:
                raise ValueError(f"Phonon.calculatePitch: unknown key '{key}'")

    # ------------------------------------------------------------------
    # Glissando
    # ------------------------------------------------------------------

    def glissando(
        self,
        startPitch: float | int | str,
        endPitch: float | int | str,
        pitchUnit: str | None = None,
    ) -> None:
        """
        Record a glissando from startPitch to endPitch.

        - data["pitchMidi"]     = anchor note (nearest 12-EDO semitone of startPitch)
        - data["pitchwheel"]    = (startSemOffset, endSemOffset) from the anchor,
                                  read by MidiExporter for a moving pitchwheel
        - data["glissandoMidi"] = (startMidi, endMidi) for analysis / scores
        """
        unit      = pitchUnit or self.pitchUnit
        startMidi = self._toMidi(startPitch, unit)
        endMidi   = self._toMidi(endPitch, unit)
        anchor    = round(startMidi)
        self.data["pitchMidi"]     = float(anchor)
        self.data["pitchwheel"]    = (startMidi - anchor, endMidi - anchor)
        self.data["glissandoMidi"] = (startMidi, endMidi)

    # ------------------------------------------------------------------
    # Dynamic markings / lyrics
    # ------------------------------------------------------------------

    def setDynamicMarking(self, text: str | None) -> None:
        """
        Re-set the dynamic from a marking ('pp', 'mf', ...) or a hairpin
        ('pp-mp', 'ff>mp'). None only clears the stored label, not the
        velocity / envelope.
        """
        if text is None:
            self.data.pop("dynamicMarking", None)
            return
        self._parseDynamic(text, dynamicUnit='midi', durationSec=self.durationSec)

    def getDynamicMarking(self) -> str | None:
        return self.data.get("dynamicMarking")

    def setLyric(self, text: str | None, offsetSec: float = 0.0) -> None:
        """
        Attach a lyric syllable; unfold() puts it on the first resolved note
        (offsetSec from that note's start). None clears it.
        """
        if text is None:
            self.data.pop("lyric", None)
            self.data.pop("lyricOffsetSec", None)
            return
        self.data["lyric"]          = str(text)
        self.data["lyricOffsetSec"] = float(offsetSec)

    def getLyric(self) -> str | None:
        return self.data.get("lyric")

    # ------------------------------------------------------------------
    # Quantisation
    # ------------------------------------------------------------------

    def quantiseTime(self, grid, parentalStartSec: float = 0.0) -> None:
        """
        Snap this note's absolute start and end to *grid* as one event.
        Leaves from an earlier unfold() are dropped (export unfolds again),
        so the quantised times are not lost on the next export.
        """
        self.children = [c for c in self.children if isinstance(c, Phonon)]
        for c in self.children:
            c.quantiseTime(grid, parentalStartSec=parentalStartSec + self.startTimeSec)
        start = float(grid.quantise(parentalStartSec + self.startTimeSec))
        end   = float(grid.quantise(parentalStartSec + self.endTimeSec))
        self.startTimeSec = start - parentalStartSec
        self.setDuration(max(end, start) - start)
        self._updateBeats()

    # ------------------------------------------------------------------
    # Unfold: resolve pitch + dynamic into TemporalObject children
    # ------------------------------------------------------------------

    def _leaf(self, startSec: float, durSec: float, pitchMidi: float, pitchwheel=None) -> TemporalObject:
        anchor = round(pitchMidi)
        diff   = pitchMidi - anchor
        return TemporalObject(startSec, durSec, data={
            "pitchMidi":    float(anchor),
            "pitchwheel":   pitchwheel if pitchwheel is not None else (diff, diff),
            "dynamicdB":    float(self.data.get("dynamicdB", 80.0)),
            "bpm":          float(self.data.get("bpm", 60.0)),
            "ticksPerBeat": int(self.data.get("ticksPerBeat", 480)),
        })

    def unfold(self, noteSelectKey: str | None = None) -> None:
        """
        Resolve pitch and dynamic into TemporalObject children, ready for export.

        Phonon children are unfolded recursively first; earlier leaves are replaced.

        noteSelectKey
            None (default) — follows chordOrSeq: 'seq', 'chord' or 'chordSeq'
            'seq'          — one note per slot, lowest (first) voice only
            'chordSeq'     — every pitch of every slot, slots in time
            'chord' / 'allSet' / 'all' / 'lowest' / 'highest' /
            'mostCommon' / 'leastCommon' — calculatePitch(key), held for
                             the full duration
        """
        key = noteSelectKey or _DEFAULT_SELECT.get(self.chordOrSeq, 'seq')
        for child in self.children:
            if isinstance(child, Phonon):
                child.unfold(noteSelectKey)

        dur     = self.durationSec
        slotDur = dur / len(self.chordSlots)
        if "glissandoMidi" in self.data:
            leaves = [self._leaf(0.0, dur, self.data["pitchMidi"], tuple(self.data["pitchwheel"]))]
        elif key == 'seq':
            leaves = [self._leaf(i * slotDur, slotDur, c[0]) for i, c in enumerate(self.chordSlots) if c]
        elif key == 'chordSeq':
            leaves = [self._leaf(i * slotDur, slotDur, p) for i, c in enumerate(self.chordSlots) for p in c]
        else:
            leaves = [self._leaf(0.0, dur, p) for p in self.calculatePitch(key)]

        # lyric on the first note
        if leaves and "lyric" in self.data:
            leaves[0].annotations.append((float(self.data.get("lyricOffsetSec", 0.0)), self.data["lyric"]))
        cal = {k: self.data[k] for k in ("minDb", "maxDb", "minVelocity", "maxVelocity") if k in self.data}
        passthrough = {k: v for k, v in self.envelopes.items() if k not in ("pitchwheel", "dynamic")}
        for leaf in leaves:
            leaf.data.update(cal)
            # full-duration notes carry the CC / aftertouch envelopes and the
            # marking; slicing an envelope across sub-notes isn't implemented
            if abs(leaf.startTimeSec) < 1e-9 and abs(leaf.durationSec - dur) < 1e-9:
                leaf.envelopes.update(passthrough)
                if "dynamicMarking" in self.data:
                    leaf.data["dynamicMarking"] = self.data["dynamicMarking"]

        self.children = [c for c in self.children if isinstance(c, Phonon)] + leaves
        self._refresh()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/out.mid",
        *,
        noteSelectKey: str | None = None,
        trackName: str = "track",
        parseEnvelopes: bool = True,
        perNoteTracks: bool = False,
        pitchBendRange: int = 4096,
        pitchwheelResolution: int = 50,
        channel: int = 0,
    ) -> None:
        """Unfold pitches then export to MIDI."""
        self.unfold(noteSelectKey)
        self.export(MidiExporter(
            path,
            trackName=trackName,
            parseEnvelopes=parseEnvelopes,
            perNoteTracks=perNoteTracks,
            pitchBendRange=pitchBendRange,
            pitchwheelResolution=pitchwheelResolution,
            channel=channel,
        ))

    def toXml(self, path: str = "/tmp/out.xml", *, noteSelectKey: str | None = None,
              title: str = "GreasyPidgin Score", timeSignature: str = "4/4") -> None:
        """Unfold pitches then export to MusicXML."""
        self.unfold(noteSelectKey)
        self.export(MusicXmlExporter(path, title=title, timeSignature=timeSignature))

    def toCsv(self, path: str = "/tmp/out.csv", *, noteSelectKey: str | None = None) -> None:
        """Unfold pitches then export to CSV."""
        self.unfold(noteSelectKey)
        self.export(CsvExporter(path))

    def toJson(self, path: str = "/tmp/out.json", *, noteSelectKey: str | None = None) -> None:
        """Unfold pitches then export to JSON."""
        self.unfold(noteSelectKey)
        self.export(JsonExporter(path))

    def parseMidi(self, folder="/tmp/", trackname="auto", perNoteTracks=True, noteSelectKey='lowest') -> None:
        """Legacy alias for toMidi(). Use toMidi() in new code."""
        name = noteSelectKey if trackname == 'auto' else trackname
        self.toMidi(folder + noteSelectKey + ".mid", noteSelectKey=noteSelectKey,
                    trackName=name, perNoteTracks=perNoteTracks)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Phonon(\n"
            f"   id           : {self.id}\n"
            f"   start        : {self.startTimeSec:.3f}s  ({self.startTimeBeats:.3f} beats)\n"
            f"   duration     : {self.durationSec:.3f}s  ({self.durationBeats:.3f} beats)\n"
            f"   bpm          : {self.data.get('bpm', '?')}\n"
            f"   dynamicMark  : {self.data.get('dynamicMarking')!r}\n"
            f"   lyric        : {self.data.get('lyric')!r}\n"
            f"   chordOrSeq   : {self.chordOrSeq}\n"
            f"   allPitches   : {sorted(set(round(p, 3) for p in self.allPitches))}\n"
            f"   lowest       : {self.calculatePitch('lowest')}\n"
            f"   highest      : {self.calculatePitch('highest')}\n"
            f"   voices       : {len(self.pitchEnvelopes)}\n"
            f"   envelopes    : {list(self.envelopes.keys())}\n"
            f"   children     : {len(self.children)}\n"
            f")"
        )
