# Gesture.py
"""
Gesture — a collection of Phonons forming a musical unit.

A Gesture is a TemporalObject whose children are Phonons (or other Gestures).
On export, all Phonon children are unfolded recursively before the tree is
flattened and handed to an exporter.

Construction
------------
    Gesture(startTimeSec, phonons=[p1, p2], bpm=120)
    Gesture.fromLists(size=8, startDeltas=[0.5], durations=[1.0], ...)
    Gesture.fromMidiFile('/tmp/in.mid')
"""

from GreasyPidgin.TimeGrid import beatToSec, secToBeat
from GreasyPidgin.IterableOperations import ensureList
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Phonon import Phonon
from GreasyPidgin.Exporters import MidiExporter, JsonExporter, CsvExporter, MusicXmlExporter


class Gesture(TemporalObject):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        startTimeSec: float = 0.0,
        phonons: list[Phonon] | None = None,
        durationSec: float = 0.0,
        *,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
    ) -> None:
        super().__init__(
            startTimeSec=float(startTimeSec),
            durationSec=float(durationSec),
            data={
                "bpm":          bpm,
                "ticksPerBeat": ticksPerBeat,
            },
        )

        if phonons:
            for p in phonons:
                if not isinstance(p, (Phonon, Gesture)):
                    raise TypeError(
                        f"Gesture: expected Phonon or Gesture, got {type(p).__name__}"
                    )
                # propagate tempo to children that haven't set their own
                if "bpm" not in p.data:
                    p.data["bpm"] = bpm
                if "ticksPerBeat" not in p.data:
                    p.data["ticksPerBeat"] = ticksPerBeat
                self.children.append(p)

            # if no explicit duration, derive from children
            if durationSec == 0.0:
                self._refresh()

    # ------------------------------------------------------------------
    # Unfold all Phonon children recursively
    # ------------------------------------------------------------------

    def _unfoldAll(self, noteSelectKey: str) -> None:
        """
        Recursively unfold every Phonon (or nested Gesture) in the tree
        before export.
        """
        for child in self.children:
            if isinstance(child, Gesture):
                child._unfoldAll(noteSelectKey)
            elif isinstance(child, Phonon):
                child.unfold(noteSelectKey)

    # ------------------------------------------------------------------
    # Dynamic markings
    # ------------------------------------------------------------------

    def setDynamicMarkings(self, markings: list[str]) -> None:
        """
        Assign dynamic markings ('pp', 'mf', 'pp-mp', ...) to this
        Gesture's direct Phonon children, one per Phonon, in child order.

        Nested Gesture children are skipped — call setDynamicMarkings()
        on them individually. If there are fewer markings than Phonon
        children the remaining children are left unset; extra markings
        beyond the number of children are ignored.

        Example
        -------
        >>> g = Gesture.fromLists(size=4, pitches=[60, 62, 64, 65])
        >>> g.setDynamicMarkings(["pp", "pp-mp", "mf", "f"])
        >>> g.toMidi("/tmp/out.mid")
        """
        phononChildren = [c for c in self.children if isinstance(c, Phonon)]
        for phonon, marking in zip(phononChildren, markings):
            phonon.setDynamicMarking(marking)

    def getDynamicMarkings(self) -> list[str | None]:
        """Return the dynamic marking (or None) of each direct Phonon child, in order."""
        return [c.getDynamicMarking() for c in self.children if isinstance(c, Phonon)]

    # ------------------------------------------------------------------
    # Lyrics
    # ------------------------------------------------------------------

    def setLyrics(self, lyrics: list[str], *, offsetSec: float = 0.0) -> None:
        """
        Assign lyrics to this Gesture's direct Phonon children, one per
        Phonon, in child order (Phonon.setLyric under the hood).

        Nested Gesture children are skipped — call setLyrics() on them
        individually. If there are fewer lyrics than Phonon children the
        remaining children are left unset; extra lyrics beyond the number
        of children are ignored.

        Example
        -------
        >>> g = Gesture.fromLists(size=4, pitches=[60, 62, 64, 65])
        >>> g.setLyrics(["la", "la", "la", "la"])
        >>> g.toMidi("/tmp/out.mid")
        """
        phononChildren = [c for c in self.children if isinstance(c, Phonon)]
        for phonon, text in zip(phononChildren, lyrics):
            phonon.setLyric(text, offsetSec=offsetSec)

    def getLyrics(self) -> list[str | None]:
        """Return the lyric (or None) of each direct Phonon child, in order."""
        return [c.getLyric() for c in self.children if isinstance(c, Phonon)]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/gesture.mid",
        *,
        bpm: float | None = None,
        noteSelectKey: str = 'lowest',
        trackName: str = "gesture",
        parseEnvelopes: bool = True,
        perNoteTracks: bool = False,
        pitchBendRange: int = 4096,
        pitchwheelResolution: int = 50,
        channel: int = 0,
    ) -> None:
        """Unfold all Phonons then export to MIDI."""
        # allow explicit bpm override — also write it into data so
        # MidiExporter always finds it regardless of how the Gesture was built
        if bpm is not None:
            self.data["bpm"] = float(bpm)
        elif "bpm" not in self.data or not self.data["bpm"]:
            self.data["bpm"] = float(getattr(self, "bpm", 60.0))
        self._unfoldAll(noteSelectKey)
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
        path: str = "/tmp/gesture.xml",
        *,
        noteSelectKey: str = 'lowest',
        title: str = "GreasyPidgin Score",
        timeSignature: str = "4/4",
    ) -> None:
        """Unfold all Phonons then export to MusicXML."""
        self._unfoldAll(noteSelectKey)
        self.export(MusicXmlExporter(path, title=title, timeSignature=timeSignature))

    def toCsv(
        self,
        path: str = "/tmp/gesture.csv",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold all Phonons then export to CSV."""
        self._unfoldAll(noteSelectKey)
        self.export(CsvExporter(path))

    def toJson(
        self,
        path: str = "/tmp/gesture.json",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold all Phonons then export to JSON."""
        self._unfoldAll(noteSelectKey)
        self.export(JsonExporter(path))

    # ------------------------------------------------------------------
    # Legacy
    # ------------------------------------------------------------------

    def parseMidi(self, path="/tmp/gesture.mid", trackname="gesture", *, parseEnvelopes=True, perNoteTracks=False, pitchBendRange=4096, procedureKey='lowest') -> None:
        """Legacy alias for toMidi(). Use toMidi() in new code."""
        self.toMidi(path, noteSelectKey=procedureKey, trackName=trackname, parseEnvelopes=parseEnvelopes, perNoteTracks=perNoteTracks, pitchBendRange=pitchBendRange)

    # ------------------------------------------------------------------
    # Quantisation (with short-note pruning)
    # ------------------------------------------------------------------

    def quantiseTime(
        self, timeGrid, durationThresholdSec: float = 0.001
    ) -> None:
        """
        Quantise all leaf times to *timeGrid*, then remove any children
        whose duration fell below *durationThresholdSec*.
        """
        super().quantiseTime(timeGrid)
        self.children = [
            c for c in self.children
            if c.durationSec > durationThresholdSec
        ]
        self._refresh()

    # ------------------------------------------------------------------
    # Factory: from parallel lists
    # ------------------------------------------------------------------

    @classmethod
    def fromLists(
        cls,
        size: int = 0,
        startOffset: float = 0.0,
        startDeltas: list | float = 0.5,
        durations: list | float = 1.0,
        pitches: list = None,
        dynamics: list | float = 64,
        *,
        timeUnit: str = 'seconds',
        pitchUnit: str = 'midi',
        dynamicUnit: str = 'midi',
        chordOrSeq: str = 'chord',
        autoSortChords: bool = True,
        bpm: float = 60.0,
        ticksPerBeat: int = 480,
        referenceA: float = 440,
    ) -> "Gesture":
        """
        Build a Gesture from parallel lists of musical parameters.

        All lists are cycled modulo their length, so short lists act as
        repeating patterns. A single value is treated as a list of length 1.

        Parameters
        ----------
        size : int
            Number of Phonons to generate.
        startOffset : float
            Absolute start time of the first event.
        startDeltas : list | float
            Inter-onset times (delta between consecutive start times).
        durations : list | float
            Duration of each Phonon.
        pitches : list
            Pitch value(s) per Phonon. Each element is passed directly
            to Phonon's pitch argument (can be single value or list).
        dynamics : list | float
            Dynamic value per Phonon.
        """
        if not isinstance(size, int) or size < 0:
            raise ValueError(
                f"Gesture.fromLists: size must be a non-negative int, got {size!r}"
            )

        if pitches is None:
            pitches = [0]

        startDeltas = ensureList(startDeltas)
        durations   = ensureList(durations)
        pitches     = ensureList(pitches)
        dynamics    = ensureList(dynamics)

        if size > 0:
            for name, values in (
                ("startDeltas", startDeltas),
                ("durations",   durations),
                ("pitches",     pitches),
                ("dynamics",    dynamics),
            ):
                if not values:
                    raise ValueError(
                        f"Gesture.fromLists: {name} must not be empty when size > 0 "
                        f"(each parallel list is cycled modulo its length, so an "
                        f"empty list has nothing to cycle through)"
                    )

        # startSec is only for the Gesture's own absolute startTimeSec
        # (below) -- it must NOT be used as the base for the per-Phonon
        # accumulation that follows. Each Phonon does its own single
        # beats<->seconds conversion via timeUnit=timeUnit, bpm=bpm
        # (exactly like `duration` is passed through unconverted above).
        # Using this already-converted-to-seconds startSec as that base
        # instead of the raw startOffset silently double-converts it --
        # invisible when bpm happens to be 60 (beatToSec(beatToSec(x,60),60)
        # == x), but for any other bpm it corrupts every note's timing and
        # compounds as deltas accumulate across notes.
        if timeUnit in ('beats', 'b'):
            startSec = beatToSec(startOffset, bpm)
        else:
            startSec = float(startOffset)

        phonons: list[Phonon] = []
        # so first note lands at startOffset (which Phonon then converts to
        # startSec itself); startDeltas is only empty when size == 0
        # (guarded above), in which case the loop below never runs and
        # this value is never actually used
        lastStart = startOffset - float(startDeltas[0]) if startDeltas else startOffset

        for i in range(size):
            delta    = float(startDeltas[i % len(startDeltas)])
            duration = durations[i % len(durations)]
            pitch    = pitches[i % len(pitches)]
            dynamic  = float(dynamics[i % len(dynamics)])
            start    = lastStart + delta
            lastStart = start

            p = Phonon(
                startTime=start,
                duration=duration,
                pitch=ensureList(pitch),
                dynamic=dynamic,
                bpm=bpm,
                timeUnit=timeUnit,
                pitchUnit=pitchUnit,
                dynamicUnit=dynamicUnit,
                chordOrSeq=chordOrSeq,
                autoSortChords=autoSortChords,
                ticksPerBeat=ticksPerBeat,
                referenceA=referenceA,
            )
            phonons.append(p)

        return cls(startSec, phonons=phonons, bpm=bpm, ticksPerBeat=ticksPerBeat)

    # ------------------------------------------------------------------
    # Factory: from MIDI file
    # ------------------------------------------------------------------

    @classmethod
    def fromMidiFile(
        cls,
        path: str,
        trackNumber: int = 0,
        *,
        pitches: int | list[int] | None = None,
        startOffsetSec: float = 0.0,
        defaultDurationSec: float = 0.1,
    ) -> "Gesture":
        """
        Import a MIDI file track as a Gesture of Phonons.

        Each note_on / note_off pair becomes one Phonon. Tempo and
        ticksPerBeat are read from the file and preserved on the Gesture
        so re-export produces a correctly timed MIDI file.

        Tempo is searched across ALL tracks (DAWs typically place
        set_tempo in track 0 regardless of note track).

        Pitchwheel messages are read and applied as microtonal offsets
        (stored in Phonon.data["pitchwheel"]). Velocity is converted
        to dynamicdB.

        Parameters
        ----------
        path : str
        trackNumber : int
            Which track to read note events from (0-indexed).
        pitches : int | list[int] | None
            None = import all pitches. int or list = filter.
        startOffsetSec : float
            Additional time offset for the whole Gesture. Note times
            are stored relative to this offset.
        defaultDurationSec : float
            Duration used for notes with no matching note_off.

        Example
        -------
        >>> g = Gesture.fromMidiFile('/tmp/melody.mid')
        >>> g.toMidi('/tmp/melody_out.mid')

        >>> # Kick drum only
        >>> g = Gesture.fromMidiFile('/tmp/drums.mid', pitches=36)
        """
        from mido import MidiFile, MetaMessage, Message, tempo2bpm, tick2second
        from GreasyPidgin.Normalisation import scale

        # normalise pitch filter
        if pitches is None:
            pitchSet = None
        elif isinstance(pitches, int):
            pitchSet = {pitches}
        else:
            pitchSet = set(pitches)

        midiFile     = MidiFile(path)
        ticksPerBeat = midiFile.ticks_per_beat
        tempo        = 500000   # MIDI default = 120 bpm
        bpm          = 120.0

        # search ALL tracks for first tempo marking
        found_tempo = False
        for track in midiFile.tracks:
            for msg in track:
                if isinstance(msg, MetaMessage) and msg.type == 'set_tempo':
                    tempo       = msg.tempo
                    bpm         = float(tempo2bpm(tempo))
                    found_tempo = True
                    break
            if found_tempo:
                break

        # --- pass 1: collect all events with absolute times ---
        noteOnQueue:   list[tuple[float, int, int]] = []  # (timeSec, pitch, velocity)
        noteOffQueue:  list[tuple[float, int]]      = []  # (timeSec, pitch)
        pitchwheelMap: dict[float, float]           = {}  # timeSec → bend semitones
        currentTick  = 0

        for msg in midiFile.tracks[trackNumber]:
            if not isinstance(msg, Message):
                continue

            currentTick += msg.time
            timeSec = round(tick2second(currentTick, ticksPerBeat, tempo), 6)

            if msg.type == 'pitchwheel':
                # store as semitone offset: bend / 4096 semitones (standard range)
                pitchwheelMap[timeSec] = msg.pitch / 4096.0

            elif msg.type == 'note_on' and msg.velocity > 0:
                if pitchSet is None or msg.note in pitchSet:
                    noteOnQueue.append((timeSec, msg.note, msg.velocity))

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                noteOffQueue.append((timeSec, msg.note))

        # --- pass 2: match note_on → note_off, build Phonons ---
        # velocity → dB: scale 1-127 → 20-100 dB
        def velTodB(vel: int) -> float:
            return float(scale(vel, 1, 127, 20.0, 100.0))

        # find the pitchwheel bend active at a given time
        # (last pitchwheel message at or before timeSec)
        sortedBendTimes = sorted(pitchwheelMap.keys())
        def bendAt(timeSec: float) -> float:
            active = 0.0
            for t in sortedBendTimes:
                if t <= timeSec:
                    active = pitchwheelMap[t]
                else:
                    break
            return active

        phonons: list[Phonon] = []
        noteOffRemaining = list(noteOffQueue)

        for startSec, pitch, velocity in noteOnQueue:
            # find earliest note_off for this pitch
            endSec = None
            for i, (offTime, offPitch) in enumerate(noteOffRemaining):
                if offPitch == pitch and offTime >= startSec:
                    endSec = offTime
                    noteOffRemaining.pop(i)
                    break

            dur        = (endSec - startSec) if endSec is not None else defaultDurationSec
            dynamicdB  = velTodB(velocity)
            bend       = bendAt(startSec)
            midiFloat  = float(pitch) + bend   # fractional MIDI if pitchwheel active

            # time relative to startOffsetSec
            relStart = startSec - startOffsetSec

            p = Phonon(
                relStart, dur,
                pitch=midiFloat,
                dynamic=dynamicdB,
                bpm=bpm,
                timeUnit='seconds',
                dynamicUnit='dB',
                ticksPerBeat=ticksPerBeat,
            )
            phonons.append(p)
            print(p)
        g = cls(
            startOffsetSec,
            phonons=phonons,
            bpm=bpm,
            ticksPerBeat=ticksPerBeat,
        )
        print(
            f"Gesture.fromMidiFile: {len(phonons)} notes | "
            f"bpm={bpm:.2f} | ticksPerBeat={ticksPerBeat} | "
            f"dur={g.durationSec:.3f}s"
            + (f" | pitches={sorted(pitchSet)}" if pitchSet else "")
        )
        return g

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        bpm = self.data.get("bpm", "?")
        return (
            f"Gesture(\n"
            f"   id       : {self.id}\n"
            f"   start    : {self.startTimeSec:.3f}s\n"
            f"   duration : {self.durationSec:.3f}s\n"
            f"   end      : {self.endTimeSec:.3f}s\n"
            f"   bpm      : {bpm}\n"
            f"   children : {len(self.children)}"
            + (f" {[type(c).__name__ for c in self.children]}" if self.children else "")
            + f"\n)"
        )