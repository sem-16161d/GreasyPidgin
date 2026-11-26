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

from GreasyPidgin.TimeGrid import beatToSec, midiTempoMap
from GreasyPidgin.IterableOperations import ensureList
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Phonon import Phonon
from GreasyPidgin.Envelope import Envelope
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
        noteSelectKey: str | None = None,
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
        noteSelectKey: str | None = None,
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
        noteSelectKey: str | None = None,
    ) -> None:
        """Unfold all Phonons then export to CSV."""
        self._unfoldAll(noteSelectKey)
        self.export(CsvExporter(path))

    def toJson(
        self,
        path: str = "/tmp/gesture.json",
        *,
        noteSelectKey: str | None = None,
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
        self, timeGrid, durationThresholdSec: float = 0.001, parentalStartSec: float = 0.0
    ) -> None:
        """
        Quantise all note times (absolute) to *timeGrid*, then remove any
        children whose duration fell below *durationThresholdSec*.
        """
        super().quantiseTime(timeGrid, parentalStartSec)
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
            Dynamic per Phonon: a number, a marking ('mf', 'pp-f') or an Envelope.
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
        # Phonon times are relative to the Gesture, which already starts at
        # startSec, so the first note lands at 0; startDeltas is only empty
        # when size == 0 (guarded above), in which case the loop below never
        # runs and this value is never actually used
        lastStart = -float(startDeltas[0]) if startDeltas else 0.0

        for i in range(size):
            delta    = float(startDeltas[i % len(startDeltas)])
            duration = durations[i % len(durations)]
            pitch    = pitches[i % len(pitches)]
            dynamic  = dynamics[i % len(dynamics)]
            if not isinstance(dynamic, (str, Envelope, list, tuple)):
                dynamic = float(dynamic)   # markings ('mf', 'pp-f') and envelopes pass through
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
        pitchBendRange: int = 4096,
    ) -> "Gesture":
        """
        Import a MIDI file track as a Gesture of Phonons.

        Each note_on / note_off pair (matched first-in first-out per channel
        and pitch) becomes one Phonon with the note's velocity. Tempo changes
        from ALL tracks are honoured (DAWs put them in track 0); the first
        tempo becomes the Gesture's bpm.

        The pitchwheel value active on a note's channel at its start is added
        as a microtonal offset: bend / pitchBendRange semitones (4096 = the
        exporter's default, +-2 semitones for the full wheel).

        Parameters
        ----------
        path : str
        trackNumber : int
            Which track to read note events from (0-indexed).
        pitches : int | list[int] | None
            None = import all pitches. int or list = filter.
        startOffsetSec : float
            Start of the Gesture; note times are stored relative to it.
        defaultDurationSec : float
            Duration used for notes with no matching note_off.
        pitchBendRange : int
            Pitchwheel units per semitone.

        Example
        -------
        >>> g = Gesture.fromMidiFile('/tmp/melody.mid')
        >>> g.toMidi('/tmp/melody_out.mid')

        >>> # Kick drum only
        >>> g = Gesture.fromMidiFile('/tmp/drums.mid', pitches=36)
        """
        from mido import MidiFile, Message

        pitchSet = None if pitches is None else ({pitches} if isinstance(pitches, int) else set(pitches))
        midiFile = MidiFile(path)
        tpb      = midiFile.ticks_per_beat

        tickToSec, bpm = midiTempoMap(midiFile)

        openNotes: dict[tuple[int, int], list] = {}   # (channel, pitch) -> [(startSec, velocity, bend)]
        bend:      dict[int, float]            = {}   # channel -> semitones
        notes:     list[tuple]                 = []   # (startSec, durSec, midiFloat, velocity)
        tick = 0
        for msg in midiFile.tracks[trackNumber]:
            tick += msg.time
            if not isinstance(msg, Message):
                continue
            if msg.type == 'pitchwheel':
                bend[msg.channel] = msg.pitch / pitchBendRange
            elif msg.type == 'note_on' and msg.velocity > 0:
                if pitchSet is None or msg.note in pitchSet:
                    openNotes.setdefault((msg.channel, msg.note), []).append(
                        (tickToSec(tick), msg.velocity, bend.get(msg.channel, 0.0)))
            elif msg.type in ('note_on', 'note_off'):
                queue = openNotes.get((msg.channel, msg.note))
                if queue:
                    start, vel, b = queue.pop(0)
                    notes.append((start, tickToSec(tick) - start, msg.note + b, vel))
        for (_, note), queue in openNotes.items():
            notes.extend((start, defaultDurationSec, note + b, vel) for start, vel, b in queue)
        notes.sort(key=lambda n: (n[0], n[2]))

        phonons = [
            Phonon(start - startOffsetSec, dur, pitch=midiFloat, dynamic=vel, bpm=bpm,
                   timeUnit='seconds', dynamicUnit='midi', ticksPerBeat=tpb)
            for start, dur, midiFloat, vel in notes
        ]
        g = cls(startOffsetSec, phonons=phonons, bpm=bpm, ticksPerBeat=tpb)
        print(
            f"Gesture.fromMidiFile: {len(phonons)} notes | "
            f"bpm={bpm:.2f} | ticksPerBeat={tpb} | "
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
            + "\n)"
        )