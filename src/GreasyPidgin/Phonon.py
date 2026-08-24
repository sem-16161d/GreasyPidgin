# Phonon.py
"""
Phonon — a musical note-event.

Extends TemporalObject with pitch vocabulary (midi / hz / spn),
dynamic, and chord / sequence support.

Pitch and dynamic are stored as envelopes and raw lists on the Phonon.
Call unfold() to resolve them into TemporalObject children, then export.

A glissando envelope (self.envelopes["glissando"]) is descriptive/analytical
only — it does not affect MIDI export.
"""

from GreasyPidgin.IterableOperations import flatten, isNested
from GreasyPidgin.Normalisation import scale
from GreasyPidgin.Pitch import ftom, spntom
from GreasyPidgin.TimeGrid import beatToSec, secToBeat
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Exporters import MidiExporter, JsonExporter, CsvExporter, MusicXmlExporter


class Phonon(TemporalObject):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        startTime: float = 0.0,
        duration: float = 0.0,
        pitch: float | int | str | list | tuple = 0,
        dynamic: float | int | list | tuple | Envelope = 64,
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

        # --- time ---
        startTimeSec, durationSec = self._toSeconds(startTime, duration, timeUnit, bpm)

        super().__init__(
            startTimeSec=startTimeSec,
            durationSec=durationSec,
            envelopes=envelopes,
            data={
                "bpm":          bpm,
                "ticksPerBeat": ticksPerBeat,
            },
        )

        # store beat-domain mirrors
        self.startTimeBeats = secToBeat(startTimeSec, bpm)
        self.durationBeats  = secToBeat(durationSec, bpm)
        self.endTimeBeats   = self.startTimeBeats + self.durationBeats

        # store construction params (needed by unfold and glissando)
        self.pitchUnit      = pitchUnit
        self.autoSortChords = autoSortChords
        self.referenceA     = referenceA
        self.chordOrSeq     = chordOrSeq

        # --- pitch ---
        # allPitches: flat list of all MIDI values mentioned
        # pitchEnvelopes: one Envelope per voice, x in [0, durationSec]
        self.allPitches:     list[float]    = []
        self.pitchEnvelopes: list[Envelope] = []
        self._parsePitch(pitch, pitchUnit, chordOrSeq, referenceA)

        # --- dynamic ---
        # stored as self.envelopes["dynamic"] (time-varying)
        # if time-varying (list or Envelope) also stored as
        # self.envelopes["aftertouch"] for MIDI export
        self._parseDynamic(dynamic, dynamicUnit, durationSec)

        # --- lyric ---
        if lyric is not None:
            self.setLyric(lyric)

    # ------------------------------------------------------------------
    # Time formatting
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Clone override — TemporalObject.clone() uses object.__new__ which
    # bypasses __init__, so Phonon-specific fields must be copied here.
    # ------------------------------------------------------------------

    def clone(self):
        import copy
        obj = super().clone()  # copies all TemporalObject fields
        obj.pitchUnit      = self.pitchUnit
        obj.autoSortChords = self.autoSortChords
        obj.referenceA     = self.referenceA
        obj.chordOrSeq     = self.chordOrSeq
        obj.startTimeBeats = self.startTimeBeats
        obj.durationBeats  = self.durationBeats
        obj.endTimeBeats   = self.endTimeBeats
        obj.allPitches     = list(self.allPitches)
        obj.pitchEnvelopes = [copy.deepcopy(e) for e in self.pitchEnvelopes]
        return obj

    def _toSeconds(
        self,
        startTime: float,
        duration: float,
        timeUnit: str,
        bpm: float,
    ) -> tuple[float, float]:
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

    def _parsePitch(
        self,
        pitch,
        pitchUnit: str,
        chordOrSeq: str,
        referenceA: float,
    ) -> None:
        """
        Populate self.allPitches and self.pitchEnvelopes.

        seq / s
            Single value or flat list → one voice, pitches evenly spaced in time.
        chord / c
            Flat list → multiple simultaneous voices, each held for full duration.
        chordSeq / cs
            Nested list of chords → each chord slot evenly spaced in time,
            variable number of voices per slot is allowed.
        """
        dur = self.durationSec

        match chordOrSeq:

            case 'seq' | 's':
                pitches = self._flattenPitchInput(pitch, pitchUnit)
                self.allPitches = pitches
                # one envelope spanning the full duration
                if len(pitches) == 1:
                    pts = [(0.0, pitches[0]), (dur, pitches[0])]
                else:
                    step = dur / len(pitches)
                    pts  = [(i * step, p) for i, p in enumerate(pitches)]
                self.pitchEnvelopes = [Envelope(pts).rescale([0, dur])]

            case 'chord' | 'c':
                pitches = self._flattenPitchInput(pitch, pitchUnit)
                if self.autoSortChords:
                    pitches = sorted(pitches)
                self.allPitches = pitches
                # one flat envelope per voice
                self.pitchEnvelopes = [
                    Envelope([(0.0, p), (dur, p)]).rescale([0, dur])
                    for p in pitches
                ]

            case 'chordSeq' | 'cs':
                if not isinstance(pitch, (list, tuple)):
                    raise ValueError(
                        "Phonon: chordSeq requires a list of chords (nested list)."
                    )
                # normalise: each element must itself be a list/tuple of pitches
                chords: list[list[float]] = []
                for slot in pitch:
                    if isinstance(slot, (list, tuple)):
                        chord = [self._toMidi(p, pitchUnit) for p in slot]
                    else:
                        chord = [self._toMidi(slot, pitchUnit)]
                    if self.autoSortChords:
                        chord = sorted(chord)
                    chords.append(chord)

                self.allPitches = list(set(
                    p for chord in chords for p in chord
                ))

                # collect one time-position per chord slot
                nSlots   = len(chords)
                slotDur  = dur / nSlots
                slotTimes = [i * slotDur for i in range(nSlots)]

                # find the maximum number of voices across all slots
                maxVoices = max(len(c) for c in chords)

                # build one envelope per voice track; pad short chords with None
                voiceTracks: list[list[tuple[float, float]]] = [
                    [] for _ in range(maxVoices)
                ]
                for t, chord in zip(slotTimes, chords):
                    for v in range(maxVoices):
                        if v < len(chord):
                            voiceTracks[v].append((t, chord[v]))
                        # if this slot has fewer voices than maxVoices,
                        # that voice simply has no point here — the envelope
                        # will interpolate across the gap

                self.pitchEnvelopes = [
                    Envelope(pts).rescale([0, dur])
                    for pts in voiceTracks
                    if len(pts) >= 2  # need at least 2 points for an envelope
                ]
                # single-point voices (only appeared once) stored as flat env
                for pts in voiceTracks:
                    if len(pts) == 1:
                        t, p = pts[0]
                        self.pitchEnvelopes.append(
                            Envelope([(0.0, p), (dur, p)]).rescale([0, dur])
                        )

            case _:
                raise ValueError(
                    f"Phonon: unknown chordOrSeq '{chordOrSeq}'. "
                    "Use 'seq'/'s', 'chord'/'c', or 'chordSeq'/'cs'."
                )

    def _flattenPitchInput(
        self, pitch, pitchUnit: str
    ) -> list[float]:
        """Convert any flat pitch input (single value or flat list) to MIDI floats."""
        if isinstance(pitch, (list, tuple)):
            if isNested(pitch):
                raise ValueError(
                    "Phonon: nested pitch list passed to seq/chord mode. "
                    "Use chordOrSeq='cs' for chord sequences."
                )
            return [self._toMidi(p, pitchUnit) for p in pitch]
        return [self._toMidi(pitch, pitchUnit)]

    # ------------------------------------------------------------------
    # Dynamic parsing
    # ------------------------------------------------------------------

    def _parseDynamic(
        self,
        dynamic: float | int | list | tuple | Envelope,
        dynamicUnit: str,
        durationSec: float,
    ) -> None:
        """
        Parse dynamic input into self.envelopes["dynamic"].

        A single value → flat envelope → stored as data["dynamicdB"].
        A list or Envelope → time-varying → stored as envelopes["dynamic"]
                             AND envelopes["aftertouch"] for MIDI export.
        """
        mindB    = 20.0
        maxdB    = 120.0
        minVelo  = 10
        maxVelo  = 127

        def toDB(val: float) -> float:
            match dynamicUnit:
                case 'midi': return scale(val, minVelo, maxVelo, mindB, maxdB)
                case 'dB':   return float(val)
                case _: raise ValueError(f"Phonon: unknown dynamicUnit '{dynamicUnit}'")

        if isinstance(dynamic, Envelope):
            env = dynamic.rescale([0, durationSec])
            self.envelopes["dynamic"]    = env
            self.envelopes["aftertouch"] = env
            # no single dB value — leave dynamicdB out of data

        elif isinstance(dynamic, (list, tuple)):
            pts = [(i * durationSec / (len(dynamic) - 1) if len(dynamic) > 1 else 0.0,
                    toDB(v))
                   for i, v in enumerate(dynamic)]
            if len(dynamic) == 1:
                pts = [(0.0, toDB(dynamic[0])), (durationSec, toDB(dynamic[0]))]
            env = Envelope(pts).rescale([0, durationSec])
            self.envelopes["dynamic"]    = env
            self.envelopes["aftertouch"] = env

        else:
            # single value → flat, used as velocity only
            dB = toDB(float(dynamic))
            self.data["dynamicdB"] = dB
            self.envelopes["dynamic"] = Envelope(
                [(0.0, dB), (durationSec, dB)]
            ).rescale([0, durationSec])

    # ------------------------------------------------------------------
    # Pitch selection helpers
    # ------------------------------------------------------------------

    def calculatePitch(self, key: str = 'all') -> list[float]:
        """
        Return a subset of allPitches by selection key.

        Keys: 'all', 'lowest', 'highest', 'mostCommon', 'leastCommon', 'chord'/'allSet'
        """
        if not self.allPitches:
            return [0.0]
        match key:
            case 'all':
                return list(self.allPitches)
            case 'chord' | 'allSet':
                return sorted(set(self.allPitches))
            case 'lowest':
                return [min(self.allPitches)]
            case 'highest':
                return [max(self.allPitches)]
            case 'mostCommon':
                return [Envelope(self.allPitches).most_common_y()]
            case 'leastCommon':
                return [Envelope(self.allPitches).least_common_y()]
            case _:
                raise ValueError(f"Phonon.calculatePitch: unknown key '{key}'")

    # ------------------------------------------------------------------
    # Glissando  (analytical / descriptive only)
    # ------------------------------------------------------------------

    def glissando(
        self,
        startPitch: float | int | str,
        endPitch: float | int | str,
        pitchUnit: str | None = None,
    ) -> None:
        """
        Record a glissando from startPitch to endPitch.

        Two things are stored:
        - self.data["pitchwheel"] = (startSemOffset, endSemOffset)
          Both are semitone offsets from the anchor note (nearest 12-EDO
          semitone of startPitch). MidiExporter reads this to emit a moving
          pitchwheel and correct annotations.
        - self.envelopes["glissando"] = raw (startMidi, endMidi) as a tuple
          (not an Envelope) for analytical / score-rendering use.
        """
        unit      = pitchUnit or self.pitchUnit
        startMidi = self._toMidi(startPitch, unit)
        endMidi   = self._toMidi(endPitch,   unit)
        anchor    = round(startMidi)

        startSem  = startMidi - anchor
        endSem    = endMidi   - anchor

        # for MIDI export: semitone offsets as a plain tuple (no Envelope)
        self.data["pitchwheel"] = (startSem, endSem)

        # set anchor as the MIDI note that will fire on note_on
        self.data["pitchMidi"]  = float(anchor)

        # for analytical use: raw MIDI values stored directly
        self.envelopes["glissando"] = (startMidi, endMidi)

    # ------------------------------------------------------------------
    # Lyrics
    # ------------------------------------------------------------------

    def setLyric(self, text: str | None, offsetSec: float = 0.0) -> None:
        """
        Attach a lyric syllable to this Phonon.

        The lyric is carried through unfold() onto the first note-leaf
        this Phonon resolves to — the note's onset, which is also where
        a syllable is conventionally notated under a melisma (when a
        Phonon unfolds into several sequential notes via noteSelectKey
        'seq' / 'chordSeq'). MidiExporter then emits it as a MIDI
        'lyrics' meta-event, via the same leaf.annotations mechanism
        used for other time-stamped text.

        Parameters
        ----------
        text : str | None
            The lyric syllable / word. Pass None to clear a previously
            set lyric.
        offsetSec : float
            Offset in seconds from the resolved leaf's own start time
            (default 0.0 — exactly at the note onset).
        """
        if text is None:
            self.data.pop("lyric", None)
            self.data.pop("lyricOffsetSec", None)
            return
        self.data["lyric"]          = str(text)
        self.data["lyricOffsetSec"] = float(offsetSec)

    def getLyric(self) -> str | None:
        """Return this Phonon's lyric text, or None if unset."""
        return self.data.get("lyric")

    def _attachLyric(self, newChildren: list) -> None:
        """Append this Phonon's lyric (if any) onto the first resolved leaf."""
        lyric = self.data.get("lyric")
        if lyric is None or not newChildren:
            return
        offsetSec = float(self.data.get("lyricOffsetSec", 0.0))
        newChildren[0].annotations.append((offsetSec, lyric))

    # ------------------------------------------------------------------
    # Unfold: resolve pitch + dynamic into TemporalObject children
    # ------------------------------------------------------------------

    def unfold(self, noteSelectKey: str = 'lowest') -> None:
        """
        Resolve this Phonon's pitch and dynamic description into
        TemporalObject children, ready for export.

        Any existing children that are themselves Phonons are unfolded
        recursively first. Non-Phonon children are left untouched.

        Parameters
        ----------
        noteSelectKey : str
            How to select pitches from allPitches for non-envelope modes.
            Used only when chordOrSeq is 'seq' or 'chord'.
            One of: 'all', 'lowest', 'highest', 'mostCommon', 'leastCommon',
            'chord'/'allSet', 'seq', 'chordSeq'.
        """
        # recurse into any Phonon children first
        for child in self.children:
            if isinstance(child, Phonon):
                child.unfold(noteSelectKey)

        bpm          = float(self.data.get("bpm", 60.0))
        ticksPerBeat = int(self.data.get("ticksPerBeat", 480))
        dynamicdB    = float(self.data.get("dynamicdB", 80.0))

        newChildren: list[TemporalObject] = []

        # --- glissando guard ---
        # If glissando() was called, self.data already has the correct
        # pitchMidi (anchor) and pitchwheel (startSem, endSem).
        # Create a single leaf that inherits this directly — do not
        # recompute pitch from allPitches.
        if "pitchwheel" in self.data and "glissando" in self.envelopes:
            newChildren.append(TemporalObject(
                0.0, self.durationSec,
                data={
                    "pitchMidi":    self.data["pitchMidi"],
                    "pitchwheel":   self.data["pitchwheel"],
                    "dynamicdB":    dynamicdB,
                    "bpm":          bpm,
                    "ticksPerBeat": ticksPerBeat,
                },
            ))
            self._attachLyric(newChildren)
            self.children = (
                [c for c in self.children if isinstance(c, Phonon)]
                + newChildren
            )
            self._refresh()
            return

        match noteSelectKey:

            case 'seq':
                env      = self.pitchEnvelopes[0]
                nPitches = len(env.points)
                slotDur  = self.durationSec / nPitches
                for i, (xNorm, _) in enumerate(env.points):
                    pitchMidi = env.getValue(xNorm, normalizedX=True)
                    anchor    = round(pitchMidi)
                    diff      = pitchMidi - anchor
                    start     = i * slotDur
                    newChildren.append(TemporalObject(
                        start, slotDur,
                        data={
                            "pitchMidi":    float(anchor),
                            "pitchwheel":   (diff, diff),
                            "dynamicdB":    dynamicdB,
                            "bpm":          bpm,
                            "ticksPerBeat": ticksPerBeat,
                        },
                    ))

            case 'chordSeq':
                nSlots  = len(self.pitchEnvelopes[0].points) if self.pitchEnvelopes else 0
                slotDur = self.durationSec / nSlots if nSlots else self.durationSec
                for voice, env in enumerate(self.pitchEnvelopes):
                    for i, (xNorm, _) in enumerate(env.points):
                        pitchMidi = env.getValue(xNorm, normalizedX=True)
                        anchor    = round(pitchMidi)
                        diff      = pitchMidi - anchor
                        start     = i * slotDur
                        newChildren.append(TemporalObject(
                            start, slotDur,
                            data={
                                "pitchMidi":    float(anchor),
                                "pitchwheel":   (diff, diff),
                                "dynamicdB":    dynamicdB,
                                "bpm":          bpm,
                                "ticksPerBeat": ticksPerBeat,
                            },
                        ))

            case _:
                # chord / lowest / highest / mostCommon / leastCommon / all
                for pitchMidi in self.calculatePitch(noteSelectKey):
                    anchor = round(pitchMidi)
                    diff   = pitchMidi - anchor
                    newChildren.append(TemporalObject(
                        0.0, self.durationSec,
                        data={
                            "pitchMidi":    float(anchor),
                            "pitchwheel":   (diff, diff),
                            "dynamicdB":    dynamicdB,
                            "bpm":          bpm,
                            "ticksPerBeat": ticksPerBeat,
                        },
                    ))

        self._attachLyric(newChildren)

        # replace only the non-Phonon children (Phonons were already unfolded)
        self.children = (
            [c for c in self.children if isinstance(c, Phonon)]
            + newChildren
        )
        self._refresh()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/out.mid",
        *,
        noteSelectKey: str = 'lowest',
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

    def toXml(
        self,
        path: str = "/tmp/out.xml",
        *,
        noteSelectKey: str = 'lowest',
        title: str = "GreasyPidgin Score",
    ) -> None:
        """Unfold pitches then export to MusicXML."""
        self.unfold(noteSelectKey)
        self.export(MusicXmlExporter(path, title=title))

    def toCsv(
        self,
        path: str = "/tmp/out.csv",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold pitches then export to CSV."""
        self.unfold(noteSelectKey)
        self.export(CsvExporter(path))

    def toJson(
        self,
        path: str = "/tmp/out.json",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold pitches then export to JSON."""
        self.unfold(noteSelectKey)
        self.export(JsonExporter(path))

    # ------------------------------------------------------------------
    # Legacy
    # ------------------------------------------------------------------

    def parseMidi(self, folder="/tmp/", trackname="auto", perNoteTracks=True, noteSelectKey='lowest') -> None:
        """Legacy alias for toMidi(). Use toMidi() in new code."""
        name = noteSelectKey if trackname == 'auto' else trackname
        self.toMidi(folder + noteSelectKey + ".mid", noteSelectKey=noteSelectKey, trackName=name, perNoteTracks=perNoteTracks)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        bpm = self.data.get("bpm", "?")
        return (
            f"Phonon(\n"
            f"   id           : {self.id}\n"
            f"   start        : {self.startTimeSec:.3f}s  "
            f"({self.startTimeBeats:.3f} beats)\n"
            f"   duration     : {self.durationSec:.3f}s  "
            f"({self.durationBeats:.3f} beats)\n"
            f"   bpm          : {bpm}\n"
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
