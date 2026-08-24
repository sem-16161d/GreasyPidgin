# Phrase.py
"""
Phrase — a polyphonic musical structure built from a palette of elements.

A Phrase is initialised with:

    elements : dict[int, TemporalObject | None]
        A palette of musical objects indexed by integer.
        Index 0 is always a rest (no child produced).
        Any TemporalObject subclass is valid: Phonon, Gesture, plain TO, etc.

    voices : dict[str, Envelope]
        One envelope per voice. Each envelope encodes a step-function score
        as (timeSec, elementIndex) breakpoint pairs, where timeSec is
        relative to the Phrase's own startTimeSec.

        Example — one voice that plays element 1, then rests, then element 2:
            Envelope([(0.0, 1), (2.0, 0), (4.0, 2)])

        The duration of each slot is determined by the time to the next
        breakpoint (or to the Phrase end for the last slot). The element's
        own durationSec is overridden by this interval.

On construction, _assemble() walks every voice, clones the referenced
elements, sets their start/duration to match the slot, and appends them
as children. The Phrase's total duration is derived from the latest
endpoint across all voices.

On export, _unfoldAll() recurses into any Phonon/Gesture children exactly
as Gesture does, then the tree is handed to an exporter.

Usage
-----
    from GreasyPidgin.Phrase import Phrase
    from GreasyPidgin.Phonon import Phonon
    from GreasyPidgin.Envelope import Envelope

    elements = {
        0: None,                                        # rest
        1: Phonon(0, 1, 'c4', pitchUnit='spn'),
        2: Phonon(0, 1, 'e4', pitchUnit='spn'),
        3: Phonon(0, 1, 'g4', pitchUnit='spn'),
    }

    voices = {
        "soprano": Envelope([(0.0, 1), (1.0, 2), (2.0, 3), (3.0, 0)]),
        "alto":    Envelope([(0.0, 3), (1.5, 1), (3.0, 2)]),
    }

    phrase = Phrase(0.0, elements, voices, bpm=120)
    phrase.toMidi('/tmp/phrase.mid')
"""

from GreasyPidgin.TimeGrid import beatToSec, secToBeat
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Phonon import Phonon
from GreasyPidgin.Gesture import Gesture
from GreasyPidgin.Envelope import Envelope
from GreasyPidgin.Exporters import MidiExporter, JsonExporter, CsvExporter, MusicXmlExporter


class Phrase(TemporalObject):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        startTimeSec: float = 0.0,
        elements: dict[int, TemporalObject | None] | None = None,
        voices: dict[str, Envelope] | None = None,
        *,
        bpm: float = 60.0,
        timeUnit: str = 'seconds',   # 's' / 'beats' / 'b'
        ticksPerBeat: int = 480,
    ) -> None:

        super().__init__(
            startTimeSec=float(startTimeSec),
            data={
                "bpm":          bpm,
                "ticksPerBeat": ticksPerBeat,
            },
        )

        self.elements:  dict[int, TemporalObject | None] = elements or {0: None}
        self.voices:    dict[str, Envelope]              = voices   or {}
        self.bpm        = float(bpm)
        self.timeUnit   = timeUnit

        # ensure index 0 is always a rest
        if 0 not in self.elements:
            self.elements[0] = None

        if self.voices:
            self._assemble()

    # ------------------------------------------------------------------
    # Assembly: voices → children
    # ------------------------------------------------------------------

    def _readBreakpoints(self, env: Envelope) -> list[tuple[float, int]]:
        """
        Extract (timeSec, elementIndex) pairs from an Envelope.

        The Envelope normalises its y-values internally, so we denormalise
        using y_range to recover the original integer indices.
        We treat the envelope as a step function — no interpolation.
        """
        if not env.points or env.y_range is None:
            return []

        y_min, y_max = env.y_range
        y_span = (y_max - y_min) if y_max != y_min else 1.0

        x_min, x_max = env.x_range
        x_span = (x_max - x_min) if x_max != x_min else 1.0

        breakpoints: list[tuple[float, int]] = []
        for x_norm, y_norm in sorted(env.points, key=lambda p: p[0]):
            timeSec = x_min + x_norm * x_span
            index   = int(round(y_min + y_norm * y_span))
            breakpoints.append((timeSec, index))

        return breakpoints

    def _assemble(self) -> None:
        """
        Walk every voice, clone elements into correctly timed children.

        Children accumulate in self.children; the Phrase's duration and
        endTimeSec are derived from the latest child endpoint.
        """
        self.children.clear()
        latestEnd = 0.0

        for voiceName, env in self.voices.items():
            breakpoints = self._readBreakpoints(env)
            if not breakpoints:
                continue

            for i, (timeSec, index) in enumerate(breakpoints):
                # duration = time to next breakpoint, or to a natural phrase end
                if i + 1 < len(breakpoints):
                    nextTime = breakpoints[i + 1][0]
                else:
                    # last slot: use element's own duration as a hint,
                    # but only if it's meaningful; otherwise use a 1-beat fallback
                    hint = None
                    if index != 0 and index in self.elements:
                        elem = self.elements[index]
                        if elem is not None and elem.durationSec > 0:
                            hint = elem.durationSec
                    nextTime = timeSec + (hint if hint is not None
                                         else beatToSec(1.0, self.bpm))

                slotDur = nextTime - timeSec

                # index 0 = rest: skip
                if index == 0 or index not in self.elements:
                    latestEnd = max(latestEnd, nextTime)
                    continue

                elem = self.elements[index]
                if elem is None:
                    latestEnd = max(latestEnd, nextTime)
                    continue

                # clone the element, override start and duration
                child              = elem.clone()
                child.startTimeSec = timeSec        # relative to Phrase start
                child.durationSec  = slotDur
                child.endTimeSec   = timeSec + slotDur

                # propagate tempo if not already set
                if hasattr(child, 'data'):
                    if "bpm" not in child.data:
                        child.data["bpm"] = self.bpm
                    if "ticksPerBeat" not in child.data:
                        child.data["ticksPerBeat"] = int(
                            self.data.get("ticksPerBeat", 480))

                self.children.append(child)
                latestEnd = max(latestEnd, timeSec + slotDur)

        # update Phrase bounds from assembled children
        if latestEnd > 0.0:
            self.durationSec = latestEnd
            self.endTimeSec  = self.startTimeSec + latestEnd

    # ------------------------------------------------------------------
    # Unfold all Phonon / Gesture children recursively
    # ------------------------------------------------------------------

    def _unfoldAll(self, noteSelectKey: str) -> None:
        for child in self.children:
            if isinstance(child, Phrase):
                child._unfoldAll(noteSelectKey)
            elif isinstance(child, Gesture):
                child._unfoldAll(noteSelectKey)
            elif isinstance(child, Phonon):
                child.unfold(noteSelectKey)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def toMidi(
        self,
        path: str = "/tmp/phrase.mid",
        *,
        noteSelectKey: str = 'lowest',
        trackName: str = "phrase",
        parseEnvelopes: bool = True,
        perNoteTracks: bool = False,
        pitchBendRange: int = 4096,
        pitchwheelResolution: int = 50,
        channel: int = 0,
    ) -> None:
        """Unfold all children then export to MIDI."""
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
        path: str = "/tmp/phrase.xml",
        *,
        noteSelectKey: str = 'lowest',
        title: str = "GreasyPidgin Score",
        timeSignature: str = "4/4",
    ) -> None:
        """Unfold all children then export to MusicXML."""
        self._unfoldAll(noteSelectKey)
        self.export(MusicXmlExporter(path, title=title, timeSignature=timeSignature))

    def toCsv(
        self,
        path: str = "/tmp/phrase.csv",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold all children then export to CSV."""
        self._unfoldAll(noteSelectKey)
        self.export(CsvExporter(path))

    def toJson(
        self,
        path: str = "/tmp/phrase.json",
        *,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Unfold all children then export to JSON."""
        self._unfoldAll(noteSelectKey)
        self.export(JsonExporter(path))

    # ------------------------------------------------------------------
    # Legacy
    # ------------------------------------------------------------------

    def parseMidi(
        self,
        filepath: str = "/tmp/phrase.mid",
        trackname: str = "phrase",
        perNoteTracks: bool = False,
        noteSelectKey: str = 'lowest',
    ) -> None:
        """Legacy alias for toMidi(). Use toMidi() in new code."""
        self.toMidi(
            filepath,
            noteSelectKey=noteSelectKey,
            trackName=trackname,
            perNoteTracks=perNoteTracks,
        )

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        voiceSummary = {
            name: f"{len(self._readBreakpoints(env))} slots"
            for name, env in self.voices.items()
        }
        return (
            f"Phrase(\n"
            f"   id         : {self.id}\n"
            f"   start      : {self.startTimeSec:.3f}s\n"
            f"   duration   : {self.durationSec:.3f}s\n"
            f"   end        : {self.endTimeSec:.3f}s\n"
            f"   bpm        : {self.bpm}\n"
            f"   elements   : {len(self.elements)} "
            f"(indices: {sorted(self.elements.keys())})\n"
            f"   voices     : {voiceSummary}\n"
            f"   children   : {len(self.children)}\n"
            f")"
        )