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
        # one counter on the base class: cls._nextId += 1 would give every
        # subclass its own counter and duplicate ids across types
        id_ = TemporalObject._nextId
        TemporalObject._nextId += 1
        return id_

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
        self.setDuration(durationSec)
        self.envelopes:   dict[str, Envelope]     = dict(envelopes or {})
        self.annotations: list[tuple[float, str]] = list(annotations or [])
        self.data:        dict                    = dict(data or {})
        self.children:    list[Self]              = list(children or [])
        self._refresh()

    # ------------------------------------------------------------------
    # Internal bookkeeping
    # ------------------------------------------------------------------

    def setDuration(self, durationSec: float) -> None:
        self.durationSec = float(durationSec)
        self.endTimeSec  = self.startTimeSec + self.durationSec

    def _leafEnd(self, parentalStartSec: float) -> float:
        """Latest absolute end time among this node's leaves."""
        if not self.children:
            return parentalStartSec + self.endTimeSec
        return max(c._leafEnd(parentalStartSec + self.startTimeSec) for c in self.children)

    def _refresh(self) -> None:
        """Recompute endTimeSec / durationSec from the leaves (containers only)."""
        if self.children:
            self.setDuration(self._leafEnd(0.0) - self.startTimeSec)

    # ------------------------------------------------------------------
    # Identity / copying
    # ------------------------------------------------------------------

    def clone(self) -> Self:
        """Deep copy with fresh ids, including every subclass attribute."""
        obj = object.__new__(self.__class__)
        obj.__dict__.update(copy.deepcopy({k: v for k, v in vars(self).items() if k != "children"}))
        obj.id = self._allocateId()
        obj.children = [c.clone() for c in self.children]
        return obj

    # ------------------------------------------------------------------
    # Container interface
    # ------------------------------------------------------------------

    def isContainer(self) -> bool:
        return bool(self.children)

    def addChild(self, child: Self) -> None:
        """Append a deep copy of *child*. Child time is relative to self."""
        if not isinstance(child, TemporalObject):
            raise TypeError(f"addChild: expected TemporalObject, got {type(child).__name__}")
        self.children.append(child.clone())
        self._refresh()

    def removeShortChildren(self, thresholdSec: float = 0.01) -> None:
        """Drop children whose duration is at or below *thresholdSec*."""
        self.children = [c for c in self.children if c.durationSec > thresholdSec]
        self._refresh()

    def sortChildren(self) -> None:
        self.children.sort(key=lambda o: (o.startTimeSec, o.durationSec))

    def clear(self) -> None:
        """Remove all children; the node keeps its current duration."""
        self.children.clear()

    # ------------------------------------------------------------------
    # Time operations
    # ------------------------------------------------------------------

    def shiftTime(self, deltaSec: float) -> None:
        """Shift start and end by *deltaSec* (children move along, their times are relative)."""
        self.startTimeSec += float(deltaSec)
        self.endTimeSec   += float(deltaSec)

    def stretchTime(self, factor: float) -> None:
        """Scale duration by *factor*; children's starts and durations scale with it."""
        factor = float(factor)
        for c in self.children:
            c.startTimeSec *= factor
            c.stretchTime(factor)
        self.setDuration(self.durationSec * factor)

    # ------------------------------------------------------------------
    # Overlap helpers
    # ------------------------------------------------------------------

    def overlaps(self, other: Self) -> bool:
        return self.startTimeSec < other.endTimeSec and other.startTimeSec < self.endTimeSec

    def resolveChildOverlaps(self, minDurationSec: float = 0.0) -> None:
        """
        Trim overlapping adjacent children so none overlap. A child that
        would end up shorter than *minDurationSec* is cut to that length
        instead and the next child is pushed later (or dropped if too short).
        """
        self.sortChildren()
        minDur = float(minDurationSec)
        i = 0
        while i < len(self.children) - 1:
            a, b = self.children[i], self.children[i + 1]
            if a.endTimeSec > b.startTimeSec:
                a.setDuration(max(b.startTimeSec - a.startTimeSec, minDur))
                if a.endTimeSec > b.startTimeSec:            # b must make room
                    cut = a.endTimeSec - b.startTimeSec
                    b.startTimeSec = a.endTimeSec
                    b.setDuration(b.durationSec - cut)
                    if b.durationSec <= 0.0 or b.durationSec < minDur:
                        self.children.pop(i + 1)
                        continue
            i += 1
        self._refresh()

    # ------------------------------------------------------------------
    # Quantisation
    # ------------------------------------------------------------------

    def quantiseTime(self, grid: Grid, parentalStartSec: float = 0.0) -> None:
        """Snap the absolute start/end times of all leaves to *grid*."""
        if self.children:
            for child in self.children:
                child.quantiseTime(grid, parentalStartSec=parentalStartSec + self.startTimeSec)
            self._refresh()
            return
        start = float(grid.quantise(parentalStartSec + self.startTimeSec))
        end   = float(grid.quantise(parentalStartSec + self.endTimeSec))
        self.startTimeSec = start - parentalStartSec
        self.setDuration(max(end, start) - start)

    # ------------------------------------------------------------------
    # Flattening  (non-mutating)
    # ------------------------------------------------------------------

    def flatten(self, parentalStartSec: float = 0.0) -> list[Self]:
        """Return absolute-time *copies* of all leaf descendants. Nothing is mutated."""
        if not self.children:
            leaf = self.clone()
            leaf.shiftTime(parentalStartSec)
            return [leaf]
        absStart = self.startTimeSec + parentalStartSec
        return [leaf for child in self.children for leaf in child.flatten(absStart)]

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
        if self.children:
            tail = f"children={len(self.children)}"
        else:
            preview = dict(list(self.data.items())[:3])
            if len(self.data) > 3:
                preview["..."] = f"({len(self.data)} keys total)"
            tail = f"data={preview}"
        return (
            f"{self.__class__.__name__}(id={self.id}, start={self.startTimeSec:.3f}, "
            f"dur={self.durationSec:.3f}, end={self.endTimeSec:.3f}, {tail})"
        )
