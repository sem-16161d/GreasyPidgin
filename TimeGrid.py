from .QuantisationGrid import Grid

class TimeGrid(Grid):
    """
    Time quantisation grid in *beats*, with helpers for seconds.

    - Internally everything is stored in beats (float).
    - You can access per-subdivision grids via `self.grids[subdivision]`.
    - The TimeGrid instance itself is a Grid over the union of all points.
    """

import warnings
from .QuantisationGrid import Grid

class TimeGrid(Grid):
    def __init__(
        self,
        durationSec: float | None = None,
        durationBeats: float | None = None,
        bpm: float = 120.0,
        possibleSubdivision=None,
    ):
        """
        A time grid over a given duration, at a given BPM.

        You can specify:
          - only durationSec
          - only durationBeats
          - or both (they must match for the given bpm, otherwise a warning
            is raised and the larger implied duration is used)

        possibleSubdivision is a list of integer subdivision factors
        (e.g. [5, 7, 8]); for each beat, all these subdivisions are
        added to the grid.
        """
        if possibleSubdivision is None:
            possibleSubdivision = [1]

        self.bpm = float(bpm)

        if durationSec is None and durationBeats is None:
            raise ValueError(
                "TimeGrid: you must specify at least durationSec or durationBeats."
            )

        beats_from_sec = None

        # If seconds given → compute beats_from_sec
        if durationSec is not None:
            durationSec = float(durationSec)
            beats_from_sec = durationSec * self.bpm / 60.0

        # If beats given → normalise
        if durationBeats is not None:
            durationBeats = float(durationBeats)

        # Case 1: only beats given
        if durationSec is None and durationBeats is not None:
            self.durationBeats = durationBeats
            self.durationSec = self.durationBeats * 60.0 / self.bpm

        # Case 2: only seconds given
        elif durationSec is not None and durationBeats is None:
            self.durationSec = durationSec
            self.durationBeats = beats_from_sec

        # Case 3: both given → check consistency
        else:
            # both not None here
            assert beats_from_sec is not None
            # if mismatch → warn and use the larger duration (in beats)
            if abs(beats_from_sec - durationBeats) > 1e-6:
                larger_beats = max(beats_from_sec, durationBeats)
                warnings.warn(
                    "TimeGrid: durationSec and durationBeats do not match for "
                    f"bpm={self.bpm}. Using larger value: {larger_beats:.6f} beats.",
                    UserWarning,
                )
                self.durationBeats = larger_beats
                self.durationSec = self.durationBeats * 60.0 / self.bpm
            else:
                # they match within tolerance
                self.durationBeats = durationBeats
                self.durationSec = durationSec

        self.possibleSubdivision = list(possibleSubdivision)
        self.grids: dict[int, Grid] = {}

        # build sub-grids and union
        all_points = set()
        for subdiv in self.possibleSubdivision:
            g = self._make_single_subdivision_grid(subdiv)
            self.grids[subdiv] = g
            all_points.update(g)

        super().__init__(all_points)
    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _make_single_subdivision_grid(self, subdiv: int) -> Grid:
        """
        Make a simple Grid with a *single* subdivision over durationBeats.

        Example: durationBeats = 4, subdiv = 3  →  0, 1/3, 2/3, 1, 4/3, ...
        """
        if subdiv <= 0:
            raise ValueError("subdiv must be a positive integer")

        points = []
        # we treat beats from 0 up to durationBeats (inclusive-ish)
        # number of slots per beat: subdiv
        # total number of beats: durationBeats
        # we step in fractions of 1/subdiv
        step = 1.0 / subdiv
        current = 0.0
        # use a small epsilon to include the last beat
        eps = 1e-9
        while current <= self.durationBeats + eps:
            points.append(current)
            current += step

        return Grid(points)

    # ------------------------------------------------------------------
    # time conversion helpers
    # ------------------------------------------------------------------
    def beat_to_sec(self, beat: float) -> float:
        """Convert a beat position to seconds."""
        return (60.0 / self.bpm) * float(beat)

    def sec_to_beat(self, sec: float) -> float:
        """Convert seconds to beat position."""
        return float(sec) * self.bpm / 60.0

    # ------------------------------------------------------------------
    # extension
    # ------------------------------------------------------------------
    def extend_to_beat(self, beat: float):
        """
        Extend all sub-grids (and the main grid) so that they cover at least
        up to the given beat.
        """
        if beat <= self.durationBeats:
            return

        # how many extra beats do we need?
        extra_beats = float(beat) - self.durationBeats
        self.durationBeats += extra_beats
        self.durationSec = self.beat_to_sec(self.durationBeats)

        # rebuild all sub-grids & union again
        all_points = set()
        for subdiv in self.possibleSubdivision:
            g = self._make_single_subdivision_grid(subdiv)
            self.grids[subdiv] = g
            all_points.update(g)

        # clear and refill this Grid
        self.clear()
        for p in all_points:
            self.add(p)

    # ------------------------------------------------------------------
    # quantisation
    # ------------------------------------------------------------------
    def quantize_beat(self, beat: float, subdivision: int | None = None):
        """
        Quantise a raw beat position to the closest grid point.

        - If `subdivision` is given, use only that sub-grid.
        - Otherwise, use the full union grid.
        """
        if subdivision is not None:
            if subdivision not in self.grids:
                raise KeyError(f"Unknown subdivision {subdivision} in TimeGrid.")
            grid = self.grids[subdivision]
        else:
            grid = self  # the union grid

        return grid.closest(float(beat))

    def quantize_sec(self, sec: float, subdivision: int | None = None):
        """
        Quantise a raw *time in seconds* to the closest grid point (in seconds).
        """
        beat_raw = self.sec_to_beat(sec)
        beat_q = self.quantize_beat(beat_raw, subdivision=subdivision)
        return self.beat_to_sec(beat_q)

    # ------------------------------------------------------------------
    # constructor to build a complex grid from simple ones
    # ------------------------------------------------------------------
    @classmethod
    def from_simple_grids(cls, grids, bpm: float):
        """
        Build a TimeGrid by combining several simple grids.

        `grids` can be:
            - a dict{subdivision: Grid or iterable_of_beats}, or
            - any iterable of Grid/iterable; in that case subdivision is
              ignored and we just union everything.

        The TimeGrid's duration is set to cover the max beat of all grids.
        """
        # Normalise to dict[int, Grid]
        if isinstance(grids, dict):
            norm = {}
            all_points = set()
            for subdiv, g in grids.items():
                g_grid = Grid(g) if not isinstance(g, Grid) else g
                norm[int(subdiv)] = g_grid
                all_points.update(g_grid)
        else:
            # just an iterable of grids/iterables
            norm = {}
            all_points = set()
            for idx, g in enumerate(grids, start=1):
                g_grid = Grid(g) if not isinstance(g, Grid) else g
                norm[idx] = g_grid
                all_points.update(g_grid)

        if not all_points:
            # empty TimeGrid
            tg = cls(durationSec=0.0, durationBeats=0.0, bpm=bpm, possibleSubdivision=[])
            return tg

        max_beat = max(all_points)
        duration_beats = float(max_beat)
        duration_sec = duration_beats * 60.0 / bpm

        possible_subdivisions = sorted(norm.keys())

        # create instance with correct meta info but don't build grids yet
        obj = cls(
            durationSec=duration_sec,
            durationBeats=duration_beats,
            bpm=bpm,
            possibleSubdivision=possible_subdivisions,
        )

        # override the auto-built grids with our provided ones
        obj.grids = norm
        obj.clear()
        for g in norm.values():
            obj.update(g)

        return obj