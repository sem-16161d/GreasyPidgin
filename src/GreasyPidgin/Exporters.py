"""
Exporters.py

Export backends for TemporalObject.

All domain-specific knowledge (MIDI ticks, pitchwheel, CC numbers, JSON
structure, CSV columns) lives here. TemporalObject itself is format-agnostic.

Usage
-----
    from GreasyPidgin.Exporters import MidiExporter, JsonExporter, CsvExporter

    to.export(MidiExporter('/tmp/out.mid'))
    to.export(JsonExporter('/tmp/out.json'))
    to.export(CsvExporter('/tmp/out.csv'))

Pitchwheel convention
---------------------
Microtonal pitch is stored as a plain tuple on the leaf:

    leaf.data["pitchwheel"] = (startSemitones, endSemitones)

Both values are semitone offsets from the anchor note (nearest 12-EDO integer).
A flat microtonal note has identical start and end values, e.g. (0.5, 0.5).
A glissando has different values, e.g. (0.0, 2.5).

MidiExporter multiplies by pitchBendRange to get MIDI bend units and clamps
to the standard MIDI range [-8192, 8191].

This avoids using Envelope for two-point data, sidestepping its internal
normalisation which is not appropriate for small semitone offset values.

CC envelopes (modulationWheel, aftertouch etc.) still use Envelope objects
stored in leaf.envelopes, since those genuinely need time-varying interpolation.
"""

from __future__ import annotations

import csv
import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .TemporalObject import TemporalObject


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIDI_CC_NAMES: list[str] = [
    "bankSelect", "modulationWheel", "breathController", "undefined3",
    "footController", "portamento/GlideTime", "dataEntry", "mIDIVolume",
    "stereoBalance", "undefined9", "panPosition", "expressionPedal",
    "effectController1", "effectController2", "undefined14", "undefined15",
    "generalPurposeSlider1", "generalPurposeSlider2", "generalPurposeSlider3",
    "generalPurposeSlider4", "undefined20", "undefined21", "undefined22",
    "undefined23", "undefined24", "undefined25", "undefined26", "undefined27",
    "undefined28", "undefined29", "undefined30", "undefined31",
    "bankSelectLSB", "modulationWheelLSB", "breathControllerLSB", "undefined35",
    "footControllerLSB", "portamentoTimeLSB", "dataEntryLSB", "volumeLSB",
    "balanceLSB", "undefined41", "panPositionLSB", "expressionLSB",
    "effectController1LSB", "effectController2LSB", "undefined46", "undefined47",
    "undefined48", "undefined49", "undefined50", "undefined51", "undefined52",
    "undefined53", "undefined54", "undefined55", "undefined56", "undefined57",
    "undefined58", "undefined59", "undefined60", "undefined61", "undefined62",
    "undefined63",
    "sustainPedal", "portamento", "sostenuto", "softPedal", "legato", "hold2",
    "soundController1", "soundController2", "soundController3", "soundController4",
    "soundController5", "soundController6", "soundController7", "soundController8",
    "soundController9", "soundController10",
    "generalPurposeCC1", "generalPurposeCC2", "generalPurposeCC3", "generalPurposeCC4",
    "undefined84", "undefined85", "undefined86", "undefined87", "undefined88",
    "undefined89", "undefined90",
    "effect1Reverb", "effect2Tremolo", "effect3Chorus", "effect4Detune",
    "effect5Phaser", "dataIncrement", "dataDecrement",
    "nRPN_LSB", "nRPN_MSB", "rPN_LSB", "rPN_MSB",
    "undefined102", "undefined103", "undefined104", "undefined105", "undefined106",
    "undefined107", "undefined108", "undefined109", "undefined110", "undefined111",
    "undefined112", "undefined113", "undefined114", "undefined115", "undefined116",
    "undefined117", "undefined118", "undefined119",
    "allSoundsOff", "resetAllControllers", "localKeyboard", "allNotesOff",
    "omniModeOff", "omniModeOn", "monoModeOn", "polyModeOn",
]

# Standard MIDI pitchwheel range
MIDI_PITCHWHEEL_MIN = -8192
MIDI_PITCHWHEEL_MAX =  8191


def _ccNumber(key: str | int) -> int:
    if isinstance(key, int):
        return key
    return MIDI_CC_NAMES.index(key)


def _secToBeats(sec: float, bpm: float) -> float:
    return sec * bpm / 60.0


def _clampBend(bend: int) -> int:
    return max(MIDI_PITCHWHEEL_MIN, min(MIDI_PITCHWHEEL_MAX, bend))


def _semToBend(semitones: float, pitchBendRange: int) -> int:
    """Convert semitone offset to MIDI bend units, clamped to valid range."""
    return _clampBend(int(round(semitones * pitchBendRange)))


def _centLabel(semitones: float) -> str | None:
    """Return '+50 CENT' style label, or None if the deviation is zero."""
    cents = round(semitones * 100)
    return f"{cents:+d} CENT" if cents != 0 else None


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Exporter:
    """Abstract base. Subclasses implement export(to: TemporalObject)."""

    def __init__(self, path: str) -> None:
        self.path = str(path)

    def _ensureDir(self) -> None:
        dirName = os.path.dirname(self.path)
        if dirName:
            os.makedirs(dirName, exist_ok=True)

    def export(self, to: "TemporalObject") -> None:
        raise NotImplementedError(f"{self.__class__.__name__} must implement export()")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r})"


# ---------------------------------------------------------------------------
# MIDI
# ---------------------------------------------------------------------------

class MidiExporter(Exporter):
    """
    Export a TemporalObject tree to a MIDI file.

    Reads from leaf.data:
        pitchMidi    float         — MIDI note (fractional = microtonal)
        dynamicdB    float         — dynamic in dB             (default 100)
        bpm          float         — tempo                     (default 60)
        ticksPerBeat int           — MIDI resolution            (default 480)
        pitchwheel   (float,float) — (startSem, endSem) offsets from anchor
                                     auto-computed from pitchMidi if absent
        annotations  list          — [(offsetSec, str), ...]

    CC envelopes (modulationWheel, aftertouch, etc.) are read from
    leaf.envelopes. The special keys 'pitchwheel' and 'glissando' in
    leaf.envelopes are ignored — pitchwheel lives in leaf.data instead.

    Parameters
    ----------
    path : str
    trackName : str
    parseEnvelopes : bool
        Emit CC messages from leaf.envelopes (default True).
    perNoteTracks : bool
        Spread overlapping notes across separate MIDI tracks (default False).
    pitchBendRange : int
        Ticks per semitone. Default 4096 → ±2 semitones fills the full
        MIDI pitchwheel range of ±8192 ticks.
    channel : int
        MIDI channel (0-indexed, so 0 = channel 1).
    """

    def __init__(
        self,
        path: str = "/tmp/out.mid",
        *,
        trackName: str = "track",
        parseEnvelopes: bool = True,
        perNoteTracks: bool = False,
        pitchBendRange: int = 4096,
        pitchwheelResolution: int = 50,  # interpolation steps per second for glissandi
        channel: int = 0,
    ) -> None:
        super().__init__(path)
        self.trackName            = trackName
        self.parseEnvelopes       = parseEnvelopes
        self.perNoteTracks        = perNoteTracks
        self.pitchBendRange       = pitchBendRange
        self.pitchwheelResolution = pitchwheelResolution
        self.channel              = channel

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def export(self, to: "TemporalObject") -> None:
        from mido import MidiFile, MidiTrack, MetaMessage, bpm2tempo

        self._ensureDir()
        leaves = to.flatten()
        if not leaves:
            print("MidiExporter: nothing to export.")
            return

        bpm          = float(to.data.get("bpm") or getattr(to, "bpm", 60.0))
        ticksPerBeat = int(to.data.get("ticksPerBeat") or getattr(to, "ticksPerBeat", 480))

        leaves = self._assignTracks(leaves)
        nTracks = max(lf.midiTrackIndex for lf in leaves) + 1

        tracks: list[list[tuple[float, object]]] = [[] for _ in range(nTracks)]
        for leaf in leaves:
            leafBpm = float(leaf.data.get("bpm") or getattr(leaf, "bpm", bpm))
            tracks[leaf.midiTrackIndex].extend(self._leafMessages(leaf, leafBpm))

        midiFile = MidiFile(ticks_per_beat=ticksPerBeat)
        for i, absEvents in enumerate(tracks):
            tr   = MidiTrack()
            name = f"{self.trackName}_t{i}" if self.perNoteTracks else self.trackName
            tr.append(MetaMessage("track_name", name=name, time=0))
            if i == 0:
                tr.insert(1, MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0))

            lastTick = 0
            for beats, msg in sorted(absEvents, key=lambda e: e[0]):
                tick     = int(round(beats * ticksPerBeat))
                msg.time = max(0, tick - lastTick)
                tr.append(msg)
                lastTick = tick

            midiFile.tracks.append(tr)

        midiFile.save(self.path)
        print(f"MidiExporter: saved -> {self.path}")

    # ------------------------------------------------------------------
    # Track assignment (greedy interval colouring)
    # ------------------------------------------------------------------

    def _assignTracks(self, leaves: list) -> list:
        if not self.perNoteTracks:
            for lf in leaves:
                lf.midiTrackIndex = 0
            return leaves

        active: list[tuple[float, int]] = []
        nextTrack = 0
        for leaf in sorted(leaves, key=lambda c: (c.startTimeSec, c.endTimeSec)):
            free = min(
                ((end, tr) for end, tr in active if end <= leaf.startTimeSec),
                key=lambda x: x[0],
                default=None,
            )
            if free is None:
                tr = nextTrack
                nextTrack += 1
            else:
                tr = free[1]
                active = [(e, t) for e, t in active if t != tr]
            leaf.midiTrackIndex = tr
            active.append((leaf.endTimeSec, tr))
        return leaves

    # ------------------------------------------------------------------
    # Per-leaf message builders
    # ------------------------------------------------------------------

    def _leafMessages(self, leaf, bpm: float) -> list:
        startB = _secToBeats(leaf.startTimeSec, bpm)
        endB   = _secToBeats(leaf.endTimeSec,   bpm)
        out    = self._noteMessages(leaf, startB, endB, bpm)
        if self.parseEnvelopes:
            out.extend(self._ccMessages(leaf, bpm))
        return out

    def _noteMessages(self, leaf, startB: float, endB: float, bpm: float) -> list:
        from mido import Message, MetaMessage
        from .Normalisation import normaliseIntoRange

        # --- anchor note ---
        pitchMidi = float(leaf.data.get("pitchMidi", 0.0))
        anchor    = round(pitchMidi)
        diff      = pitchMidi - anchor   # semitone offset, e.g. 0.5 for quartertone

        # --- pitchwheel semitone offsets ---
        # If the caller has already set data["pitchwheel"] = (startSem, endSem),
        # use that (e.g. for glissando). Otherwise derive from pitchMidi.
        if "pitchwheel" in leaf.data:
            startSem, endSem = leaf.data["pitchwheel"]
        else:
            startSem = endSem = diff

        # --- velocity ---
        dynamicdB = float(leaf.data.get("dynamicdB", 100.0))
        minDb     = float(leaf.data.get("minDb",     0.0))
        maxDb     = float(leaf.data.get("maxDb",     100.0))
        velocity  = int(round(127 * normaliseIntoRange(dynamicdB, minDb, maxDb)))
        velocity  = max(1, min(127, velocity))

        # --- microtonal annotation ---
        # No glissando: single label at note start if microtonal.
        # Glissando (startSem != endSem): label start and/or end independently.
        annotationMessages: list[tuple[float, MetaMessage]] = []
        isGliss = abs(startSem - endSem) > 1e-9

        if isGliss:
            label = _centLabel(startSem)
            if label:
                annotationMessages.append(
                    (startB, MetaMessage("lyrics", text=label, time=0))
                )
            label = _centLabel(endSem)
            if label:
                annotationMessages.append(
                    (endB, MetaMessage("lyrics", text=f"-> {label}", time=0))
                )
        else:
            label = _centLabel(startSem)
            if label:
                annotationMessages.append(
                    (startB, MetaMessage("lyrics", text=label, time=0))
                )

        # --- any pre-existing annotations from leaf.data or leaf.annotations ---
        for offsetSec, text in leaf.data.get("annotations", leaf.annotations):
            beats = _secToBeats(leaf.startTimeSec + float(offsetSec), bpm)
            annotationMessages.append(
                (beats, MetaMessage("lyrics", text=str(text), time=0))
            )

        ch = self.channel
        return [
            (startB, Message("note_on",  channel=ch, note=anchor, velocity=velocity, time=0)),
            (endB,   Message("note_off", channel=ch, note=anchor, velocity=velocity, time=0)),
            *annotationMessages,
        ]

    def _pitchwheelMessages(self, leaf, startB: float, endB: float) -> list:
        from mido import Message

        if "pitchwheel" in leaf.data:
            startSem, endSem = leaf.data["pitchwheel"]
        else:
            pitchMidi = float(leaf.data.get("pitchMidi", 0.0))
            diff      = pitchMidi - round(pitchMidi)
            startSem  = endSem = diff

        bendStart = _semToBend(startSem, self.pitchBendRange)
        bendEnd   = _semToBend(endSem,   self.pitchBendRange)
        ch        = self.channel

        # flat — just two messages
        if bendStart == bendEnd:
            return [
                (startB, Message("pitchwheel", channel=ch, pitch=bendStart, time=0)),
                (endB,   Message("pitchwheel", channel=ch, pitch=bendEnd,   time=0)),
            ]

        # glissando — interpolate at pitchwheelResolution steps per second
        durationSec = (endB - startB) * 60.0 / max(leaf.data.get("bpm") or getattr(leaf, "bpm", 60.0), 1e-6)
        nSteps      = max(2, int(durationSec * self.pitchwheelResolution))
        msgs        = []
        for i in range(nSteps):
            t       = i / (nSteps - 1)
            sem     = startSem + t * (endSem - startSem)
            bend    = _semToBend(sem, self.pitchBendRange)
            beats   = startB + t * (endB - startB)
            msgs.append((beats, Message("pitchwheel", channel=ch, pitch=bend, time=0)))
        return msgs

    def _ccMessages(self, leaf, bpm: float) -> list:
        """Emit CC messages from leaf.envelopes, skipping pitchwheel and glissando."""
        from mido import Message
        from .Grid import Grid

        out     = []
        startB  = _secToBeats(leaf.startTimeSec, bpm)
        endB    = _secToBeats(leaf.endTimeSec,   bpm)

        for key, env in leaf.envelopes.items():
            if key in ("pitchwheel", "glissando"):
                continue   # pitchwheel is in leaf.data; glissando is analytical

            if key == "aftertouch":
                out.extend(self._aftertouchMessages(leaf, env, bpm))
                continue

            # generic CC
            ccNum  = _ccNumber(key)
            xGrid  = Grid.series(leaf.startTimeSec, 0.001, int(leaf.durationSec * 1000))
            yGrid  = Grid.series(0, 1, 128)
            for timeSec, value in env.mapToGrid(xGrid, yGrid):
                beats = _secToBeats(timeSec, bpm)
                out.append((
                    beats,
                    Message("control_change", channel=self.channel,
                            control=ccNum, value=int(value), time=0),
                ))

        # always emit pitchwheel (even if only leaf.data["pitchMidi"] is set)
        out.extend(self._pitchwheelMessages(leaf, startB, endB))

        return out

    def _aftertouchMessages(self, leaf, env, bpm: float) -> list:
        """Emit channel aftertouch from a dynamic Envelope."""
        from mido import Message
        from .Grid import Grid

        xGrid = Grid.series(leaf.startTimeSec, 0.001, int(leaf.durationSec * 1000))
        yGrid = Grid.series(0, 1, 128)
        out   = []
        for timeSec, value in env.mapToGrid(xGrid, yGrid):
            beats = _secToBeats(timeSec, bpm)
            out.append((
                beats,
                Message("aftertouch", channel=self.channel,
                        value=int(value), time=0),
            ))
        return out


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

class JsonExporter(Exporter):
    """
    Serialise the full TemporalObject tree to JSON.

    Tree structure is preserved via nested 'children' lists.
    Each node includes all data keys as-is.

    Parameters
    ----------
    path : str
    indent : int
        JSON indentation (default 2).
    includeEnvelopes : bool
        Serialise envelope breakpoints (default True).
    """

    def __init__(
        self,
        path: str = "/tmp/out.json",
        *,
        indent: int = 2,
        includeEnvelopes: bool = True,
    ) -> None:
        super().__init__(path)
        self.indent           = indent
        self.includeEnvelopes = includeEnvelopes

    def export(self, to: "TemporalObject") -> None:
        self._ensureDir()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._serialiseNode(to), f, indent=self.indent, default=str)
        print(f"JsonExporter: saved -> {self.path}")

    def _serialiseNode(self, node: "TemporalObject") -> dict:
        out: dict = {
            "type":         node.__class__.__name__,
            "id":           node.id,
            "startTimeSec": node.startTimeSec,
            "durationSec":  node.durationSec,
            "endTimeSec":   node.endTimeSec,
            "annotations":  node.annotations,
            "data":         node.data,
            "children":     [self._serialiseNode(c) for c in node.children],
        }
        if self.includeEnvelopes and node.envelopes:
            out["envelopes"] = {
                key: {
                    "x_range": list(env.x_range) if env.x_range else None,
                    "y_range": list(env.y_range) if env.y_range else None,
                    "points":  env.points,
                }
                for key, env in node.envelopes.items()
            }
        return out


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

class CsvExporter(Exporter):
    """
    Serialise the full TemporalObject tree to CSV.

    Tree structure is encoded as id / parentId columns.
    Each row is one node. data keys are written as individual columns;
    all unique keys across the whole tree are collected first so the
    header is consistent.

    Parameters
    ----------
    path : str
    includeEnvelopes : bool
        Include a comma-separated list of envelope key names (default True).
    """

    def __init__(
        self,
        path: str = "/tmp/out.csv",
        *,
        includeEnvelopes: bool = True,
    ) -> None:
        super().__init__(path)
        self.includeEnvelopes = includeEnvelopes

    def export(self, to: "TemporalObject") -> None:
        self._ensureDir()
        rows: list[dict] = []
        self._collectRows(to, parentId=None, rows=rows)
        if not rows:
            print("CsvExporter: nothing to export.")
            return

        structuralFields = [
            "id", "parentId", "type", "isContainer",
            "startTimeSec", "durationSec", "endTimeSec",
            "annotations",
        ]
        if self.includeEnvelopes:
            structuralFields.append("envelopeKeys")

        dataKeys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for k in row.pop("_dataKeys", []):
                if k not in seen:
                    dataKeys.append(k)
                    seen.add(k)

        fieldnames = structuralFields + dataKeys
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        print(f"CsvExporter: saved -> {self.path}")

    def _collectRows(
        self,
        node: "TemporalObject",
        parentId: int | None,
        rows: list[dict],
    ) -> None:
        row: dict = {
            "id":           node.id,
            "parentId":     parentId if parentId is not None else "",
            "type":         node.__class__.__name__,
            "isContainer":  node.isContainer(),
            "startTimeSec": node.startTimeSec,
            "durationSec":  node.durationSec,
            "endTimeSec":   node.endTimeSec,
            "annotations":  "|".join(f"{t}:{txt}" for t, txt in node.annotations),
            "_dataKeys":    list(node.data.keys()),
        }
        if self.includeEnvelopes:
            row["envelopeKeys"] = ",".join(node.envelopes.keys())
        for k, v in node.data.items():
            row[k] = v
        rows.append(row)
        for child in node.children:
            self._collectRows(child, parentId=node.id, rows=rows)


# ---------------------------------------------------------------------------
# MusicXML  (stub)
# ---------------------------------------------------------------------------

class MusicXmlExporter(Exporter):
    """
    Export a TemporalObject tree to MusicXML via music21.

    Requires: pip install music21

    Reads from leaf.data:
        pitchMidi    float  — integer part used (microtones not yet supported)
        dynamicdB    float  — mapped to a Dynamic mark
        bpm          float  — tempo
        ticksPerBeat int    — used for duration quantisation
        annotations  list   — [(offsetSec, str), ...] (falls back to
                               leaf.annotations, same as MidiExporter);
                               the first entry's text becomes the note's
                               lyric, e.g. Phonon.setLyric()/Gesture.setLyrics()
        dynamicMarking str  — a flat marking ('mf') becomes a real Dynamic
                               mark at the note's onset; a hairpin like
                               'pp-mp' or 'ff>mp' prints as one dash-joined
                               italic text label 'pp-mp' (not a wedge, and
                               not MusicXML's <other-dynamics> — that
                               fallback is spec-valid but Dorico's importer
                               drops it, so a plain <words> text element is
                               used instead for reliability) — see
                               Phonon.setDynamicMarking() / Gesture.setDynamicMarkings()

    Parameters
    ----------
    path : str
    title : str
    timeSignature : str
        Fixed time signature used to bar the whole piece (default "4/4").
        This is not meter inference — every measure gets the same length,
        derived from this signature.

    A note that runs past the barline of the measure it starts in is
    split into fragments at each barline it crosses and tied back
    together (Tie 'start' / 'continue' / 'stop') — inserting an
    over-long, untied note directly is not just visually odd: music21's
    own writer will silently re-split it at the wrong offsets when it
    doesn't fit its measure, corrupting the note's timing. Splitting it
    correctly ourselves avoids that.

    Not yet implemented:
        - Microtonal pitch
        - Envelope / CC data
        - Automatic time / key signature inference (a single fixed
          timeSignature is used throughout — see above)
        - Chords (simultaneous notes on the same track)
    """

    def __init__(
        self,
        path: str = "/tmp/out.xml",
        *,
        title: str = "GreasyPidgin Score",
        timeSignature: str = "4/4",
    ) -> None:
        super().__init__(path)
        self.title         = title
        self.timeSignature = timeSignature

    def _splitAtBarlines(self, offsetBeats: float, durationBeats: float, barLen: float):
        """
        Yield (measureIndex, localOffset, fragmentDuration) triples that
        cover [offsetBeats, offsetBeats + durationBeats), split at every
        barline crossed. A note entirely within one measure yields a
        single fragment.
        """
        end = offsetBeats + durationBeats
        pos = offsetBeats
        eps = 1e-9
        if durationBeats <= eps:
            measureIdx = int((pos + eps) // barLen)
            yield measureIdx, pos - measureIdx * barLen, durationBeats
            return
        while pos < end - eps:
            measureIdx  = int((pos + eps) // barLen)
            measureEnd  = (measureIdx + 1) * barLen
            fragEnd     = min(end, measureEnd)
            localOffset = pos - measureIdx * barLen
            yield measureIdx, localOffset, fragEnd - pos
            pos = fragEnd

    def _insertDynamicMarking(self, m21, marking: str, fragments: list, trackMeasures: list) -> None:
        """
        Render one leaf's dynamic-marking text at the note's onset.

        A plain marking ('mf') becomes a real Dynamic mark (<dynamics><mf/>),
        which every notation program reads natively.

        A hairpin ('pp-mp', 'ff>mp') is *not* drawn as a wedge/hairpin
        shape — it prints as one dash-joined label ('pp-mp'), regardless
        of which separator ('-', '<', '>', '~') the marking was written
        with. This is rendered as plain italic text (MusicXML <words>)
        rather than a Dynamic's <other-dynamics> fallback: <other-dynamics>
        is valid MusicXML and MuseScore reads it fine, but Dorico's
        importer silently drops it, while <words> — the same element used
        for tempo/expression text — is read reliably everywhere.
        """
        from .Dynamics import splitHairpin

        firstMeasureIdx, firstLocalOffset, _ = fragments[0]
        hairpin = splitHairpin(marking)

        if hairpin is None:
            trackMeasures[firstMeasureIdx].insert(
                firstLocalOffset, m21.dynamics.Dynamic(marking.strip().lower())
            )
            return

        label = f"{hairpin[0]}-{hairpin[1]}"
        text = m21.expressions.TextExpression(label)
        text.style.fontStyle = "italic"
        text.placement = "below"
        trackMeasures[firstMeasureIdx].insert(firstLocalOffset, text)

    def export(self, to: "TemporalObject") -> None:
        try:
            import music21 as m21
        except ImportError as e:
            raise ImportError(
                "MusicXmlExporter requires music21: pip install music21"
            ) from e

        self._ensureDir()
        leaves = to.flatten()
        if not leaves:
            print("MusicXmlExporter: nothing to export.")
            return

        bpm    = float(to.data.get("bpm") or getattr(to, "bpm", 60.0))
        barLen = m21.meter.TimeSignature(self.timeSignature).barDuration.quarterLength

        # --- assign each leaf a track via greedy interval colouring ---
        active: list[tuple[float, int]] = []
        nextTrack = 0
        for leaf in sorted(leaves, key=lambda c: (c.startTimeSec, c.endTimeSec)):
            free = min(
                ((end, tr) for end, tr in active if end <= leaf.startTimeSec),
                key=lambda x: x[0], default=None,
            )
            if free is None:
                tr = nextTrack; nextTrack += 1
            else:
                tr = free[1]
                active = [(e, t) for e, t in active if t != tr]
            leaf.midiTrackIndex = tr
            active.append((leaf.endTimeSec, tr))

        nTracks = nextTrack

        # --- convert every leaf to beats up front, and find how many ---
        # --- bars of `timeSignature` the whole piece needs           ---
        leafBeats: list[tuple[object, float, float]] = []
        lastMeasureIndex = 0
        for leaf in leaves:
            leafBpm       = float(leaf.data.get("bpm") or getattr(leaf, "bpm", bpm))
            durationBeats = leaf.durationSec * leafBpm / 60.0
            offsetBeats   = leaf.startTimeSec * leafBpm / 60.0
            leafBeats.append((leaf, offsetBeats, durationBeats))
            lastMeasureIndex = max(
                lastMeasureIndex, int((offsetBeats + durationBeats) // barLen)
            )
        nMeasures = lastMeasureIndex + 1

        # --- build the score: every part gets the same number of      ---
        # --- `timeSignature`-length measures, so all tracks stay      ---
        # --- bar-aligned and music21's notation engine only ever has  ---
        # --- to reason about one bar's worth of material at a time.   ---
        # --- (Putting the whole piece in a single unbarred Measure —  ---
        # --- the previous behaviour — made music21's tuplet/beam      ---
        # --- grouping pathologically slow: a hundred mixed-tuplet     ---
        # --- notes could take minutes, sometimes never finishing, vs. ---
        # --- a fraction of a second once barred.)                     ---
        score = m21.stream.Score()
        score.metadata = m21.metadata.Metadata()
        score.metadata.title = self.title
        parts = [m21.stream.Part() for _ in range(nTracks)]

        measures: list[list] = []
        for part in parts:
            partMeasures = []
            for i in range(nMeasures):
                measure = m21.stream.Measure(number=i + 1)
                if i == 0:
                    measure.insert(0.0, m21.meter.TimeSignature(self.timeSignature))
                part.insert(i * barLen, measure)
                partMeasures.append(measure)
            measures.append(partMeasures)

        for leaf, offsetBeats, durationBeats in leafBeats:
            midiNote      = int(round(float(leaf.data.get("pitchMidi", 60.0))))
            fragments     = list(self._splitAtBarlines(offsetBeats, durationBeats, barLen))
            trackMeasures = measures[leaf.midiTrackIndex]
            for i, (measureIdx, localOffset, fragDur) in enumerate(fragments):
                note = m21.note.Note(
                    m21.pitch.Pitch(midiNote),
                    duration=m21.duration.Duration(fragDur),
                )
                if len(fragments) > 1:
                    note.tie = m21.tie.Tie(
                        'start' if i == 0 else
                        'stop' if i == len(fragments) - 1 else
                        'continue'
                    )
                if i == 0:
                    # a lyric belongs on the syllable's own onset only —
                    # never repeated on a tied continuation fragment
                    lyricEntries = leaf.data.get("annotations", leaf.annotations)
                    if lyricEntries:
                        note.lyric = str(lyricEntries[0][1])
                # insert() (not append()) so the note lands at its actual
                # offset within its measure — append() ignores any pre-set
                # .offset and just places elements back-to-back in call
                # order, which was silently discarding every leaf's real
                # start time and any gaps (rests) between notes.
                trackMeasures[measureIdx].insert(localOffset, note)

            marking = leaf.data.get("dynamicMarking")
            if marking:
                self._insertDynamicMarking(m21, marking, fragments, trackMeasures)

        for part in parts:
            score.append(part)

        score.write("musicxml", fp=self.path)
        print(f"MusicXmlExporter: saved -> {self.path}")