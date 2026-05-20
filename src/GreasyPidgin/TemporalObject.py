"""
TemporalObject.py

A TemporalObject is a time interval that can contain other TemporalObjects
and carry arbitrary payload data and time-varying envelopes.

It knows nothing about export formats, MIDI, audio, video, or pitch.
All domain-specific data lives in ``self.data``. Exporters interpret it.

    TemporalObject
        startTimeSec, durationSec, endTimeSec   — time
        children: list[TemporalObject]           — structure (relative times)
        envelopes: dict[str, Envelope]           — time-varying behaviour
        annotations: list[tuple[float, str]]     — time-stamped text labels
        data: dict                               — everything else

Example
-------
    # A MIDI note
    TemporalObject(0.0, 2.0, data={"pitchMidi": 60.0, "dynamicdB": 80.0, "bpm": 120})

    # An image shown for 3 seconds
    TemporalObject(2.0, 3.0, data={"file": "frame.png", "type": "image"})

    # A video clip
    TemporalObject(5.0, 10.0, data={"file": "clip.mp4", "type": "video", "framerate": 25})
"""

import copy
from typing import Self, TYPE_CHECKING

from .Envelope import Envelope
from .Grid import Grid

if TYPE_CHECKING:
    from .Exporters import Exporter


class TemporalObject:

    _nextId: int = 0

    @classmethod
    def _allocateId(cls) -> int:
        id_ = cls._nextId
        cls._nextId += 1
        return id_

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        startTimeSec: float = 0.0,
        durationSec: float = 0.0,
        children: list[Self] | None = None,
        *,
        envelopes: dict[str, Envelope] | None = None,
        annotations: list[tuple[float, str]] | None = None,
        data: dict | None = None,
    ) -> None:
        self.id = self._allocateId()

        self.startTimeSec = float(startTimeSec)
        self.durationSec  = float(durationSec)
        self.endTimeSec   = self.startTimeSec + self.durationSec

        self.envelopes:   dict[str, Envelope]     = dict(envelopes)   if envelopes   else {}
        self.annotations: list[tuple[float, str]] = list(annotations) if annotations else []
        self.data:        dict                    = dict(data)         if data        else {}

        self.children: list[Self] = list(children) if children else []
        if self.children:
            self._refresh()

    # ------------------------------------------------------------------
    # Internal bookkeeping
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Recompute endTimeSec / durationSec from flattened leaves."""
        leaves = self.flatten()
        if leaves:
            self.endTimeSec  = max(lf.endTimeSec for lf in leaves)
            self.durationSec = self.endTimeSec - self.startTimeSec

    # ------------------------------------------------------------------
    # Identity / copying
    # ------------------------------------------------------------------

    def clone(self) -> Self:
        """
        Deep copy of this node.

        Children are deep-copied so the clone is fully independent.
        """
        obj              = object.__new__(self.__class__)
        obj.id           = self._allocateId()
        obj.startTimeSec = self.startTimeSec
        obj.durationSec  = self.durationSec
        obj.endTimeSec   = self.endTimeSec
        obj.envelopes    = copy.deepcopy(self.envelopes)
        obj.annotations  = list(self.annotations)
        obj.data         = copy.deepcopy(self.data)
        obj.children     = [c.clone() for c in self.children]
        return obj

    # ------------------------------------------------------------------
    # Container interface
    # ------------------------------------------------------------------

    def isContainer(self) -> bool:
        return bool(self.children)

    def addChild(self, child: Self) -> None:
        """Append a deep copy of *child*. Child time is relative to self."""
        if not isinstance(child, TemporalObject):
            raise TypeError(
                f"addChild: expected TemporalObject, got {type(child).__name__}"
            )
        self.children.append(child.clone())
        self._refresh()

    def removeShortChildren(self, thresholdSec: float = 0.01) -> None:
        """Drop children whose duration is at or below *thresholdSec*."""
        self.children = [c for c in self.children if c.durationSec > thresholdSec]
        self._refresh()

    def sortChildren(self) -> None:
        self.children.sort(key=lambda o: (o.startTimeSec, o.durationSec))

    def clear(self) -> None:
        self.children.clear()
        self._refresh()

    # ------------------------------------------------------------------
    # Time operations
    # ------------------------------------------------------------------

    def shiftTime(self, deltaSec: float) -> None:
        """Shift start and end by *deltaSec*. Does not recurse into children."""
        self.startTimeSec += float(deltaSec)
        self.endTimeSec   += float(deltaSec)

    def stretchTime(self, factor: float) -> None:
        """Scale duration in place (leaf only)."""
        self.durationSec *= float(factor)
        self.endTimeSec   = self.startTimeSec + self.durationSec

    # ------------------------------------------------------------------
    # Overlap helpers
    # ------------------------------------------------------------------

    def overlaps(self, other: Self) -> bool:
        return not (
            self.endTimeSec    <= other.startTimeSec
            or other.endTimeSec <= self.startTimeSec
        )

    def resolveChildOverlaps(self, minDurationSec: float = 0.0) -> None:
        """Trim overlapping adjacent children so none overlap."""
        if len(self.children) < 2:
            return
        self.sortChildren()
        minDur = float(minDurationSec)
        i = 0
        while i < len(self.children) - 1:
            a = self.children[i]
            b = self.children[i + 1]
            if a.endTimeSec <= b.startTimeSec:
                i += 1
                continue
            idealDur = b.startTimeSec - a.startTimeSec
            if idealDur >= minDur:
                a.durationSec = idealDur
                a.endTimeSec  = a.startTimeSec + idealDur
                i += 1
                continue
            a.durationSec  = max(a.durationSec, minDur)
            a.endTimeSec   = a.startTimeSec + a.durationSec
            push            = minDur - idealDur
            b.startTimeSec += push
            b.durationSec  -= push
            b.endTimeSec    = b.startTimeSec + b.durationSec
            if b.durationSec <= 0.0 or b.durationSec < minDur:
                self.children.pop(i + 1)
                continue
            i += 1
        self._refresh()

    # ------------------------------------------------------------------
    # Quantisation
    # ------------------------------------------------------------------

    def quantiseTime(self, grid: Grid) -> None:
        """Snap start/end times of all leaves to *grid*."""
        if self.isContainer():
            for child in self.children:
                child.quantiseTime(grid)
            if self.children:
                self.startTimeSec = min(c.startTimeSec for c in self.children)
                self.endTimeSec   = max(c.endTimeSec   for c in self.children)
                self.durationSec  = self.endTimeSec - self.startTimeSec
            return
        self.startTimeSec = float(grid.quantise(self.startTimeSec))
        self.endTimeSec   = float(grid.quantise(self.endTimeSec))
        if self.endTimeSec < self.startTimeSec:
            self.endTimeSec = self.startTimeSec
        self.durationSec = self.endTimeSec - self.startTimeSec

    # ------------------------------------------------------------------
    # Flattening  (non-mutating)
    # ------------------------------------------------------------------

    def flatten(self, parentalStartSec: float = 0.0) -> list[Self]:
        """
        Return absolute-time *copies* of all leaf descendants.

        Neither self nor any child is mutated.
        """
        if not self.isContainer():
            leaf              = self.clone()
            leaf.startTimeSec += parentalStartSec
            leaf.endTimeSec   += parentalStartSec
            return [leaf]

        leaves: list[Self] = []
        absStart = self.startTimeSec + parentalStartSec
        for child in self.children:
            childCopy = child.clone()
            leaves.extend(childCopy.flatten(absStart))
        return leaves

    # ------------------------------------------------------------------
    # Export hook
    # ------------------------------------------------------------------

    def export(self, exporter: "Exporter") -> None:
        """
        Export via *exporter*.

        Examples
        --------
            to.export(MidiExporter('/tmp/out.mid'))
            to.export(JsonExporter('/tmp/out.json'))
            to.export(CsvExporter('/tmp/out.csv'))
        """
        exporter.export(self)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        dataPreview = {k: v for k, v in list(self.data.items())[:3]}
        if len(self.data) > 3:
            dataPreview["..."] = f"({len(self.data)} keys total)"

        if self.isContainer():
            return (
                f"{self.__class__.__name__}("
                f"id={self.id}, "
                f"start={self.startTimeSec:.3f}, "
                f"dur={self.durationSec:.3f}, "
                f"end={self.endTimeSec:.3f}, "
                f"children={len(self.children)})"
            )
        return (
            f"{self.__class__.__name__}("
            f"id={self.id}, "
            f"start={self.startTimeSec:.3f}, "
            f"dur={self.durationSec:.3f}, "
            f"end={self.endTimeSec:.3f}, "
            f"data={dataPreview})"
        )