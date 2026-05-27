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
    from GreasyPidgin.TemporalObject import TemporalObject


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
    return f"{cents:+d}" if cents != 0 else None


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

        bpm          = float(to.data.get("bpm", 60.0))
        ticksPerBeat = int(to.data.get("ticksPerBeat", 480))

        leaves = self._assignTracks(leaves)
        nTracks = max(lf.midiTrackIndex for lf in leaves) + 1

        tracks: list[list[tuple[float, object]]] = [[] for _ in range(nTracks)]
        for leaf in leaves:
            leafBpm = float(leaf.data.get("bpm", bpm))
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
        durationSec = (endB - startB) * 60.0 / max(leaf.data.get("bpm", 60.0), 1e-6)
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

    Not yet implemented:
        - Microtonal pitch
        - Envelope / CC data
        - Time / key signature inference
        - Tied notes across barlines
        - Chords (simultaneous notes on the same track)
    """

    def __init__(
        self,
        path: str = "/tmp/out.xml",
        *,
        title: str = "GreasyPidgin Score",
    ) -> None:
        super().__init__(path)
        self.title = title

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

        bpm = float(to.data.get("bpm", 60.0))

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
        score   = m21.stream.Score()
        score.metadata = m21.metadata.Metadata()
        score.metadata.title = self.title
        parts = [m21.stream.Part() for _ in range(nTracks)]
        for part in parts:
            part.append(m21.stream.Measure())

        for leaf in leaves:
            leafBpm       = float(leaf.data.get("bpm", bpm))
            midiNote      = int(round(float(leaf.data.get("pitchMidi", 60.0))))
            durationBeats = leaf.durationSec * leafBpm / 60.0
            note          = m21.note.Note(
                m21.pitch.Pitch(midiNote),
                duration=m21.duration.Duration(durationBeats),
            )
            note.offset = leaf.startTimeSec * leafBpm / 60.0
            parts[leaf.midiTrackIndex].measure(0).append(note)

        for part in parts:
            score.append(part)

        score.write("musicxml", fp=self.path)
        print(f"MusicXmlExporter: saved -> {self.path}")
