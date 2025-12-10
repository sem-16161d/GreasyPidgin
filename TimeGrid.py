import math

class TimeGrid:
    def __init__(self, durationSec=1, bpm=106, possibleSubdivision=None):
        """
        A time grid over a given duration, at a given BPM.

        possibleSubdivision is a list of integer subdivision factors
        (e.g. [5, 7, 8]); for each beat, all these subdivisions are
        added to the grid.
        """
        if possibleSubdivision is None:
            possibleSubdivision = [3, 5, 7, 8]

        self.durationSec = float(durationSec)
        self.bpm = float(bpm)
        self.possibleSubdivision = list(possibleSubdivision)
        self.grids = dict()
        self.grid = self._make_time_grid()

    # ------------------------------------------------------------------
    # Core grid construction
    # ------------------------------------------------------------------
    def _make_time_grid(self):
        beatDurationSec = 60.0 / self.bpm
        ceilNumBeats = math.ceil(self.durationSec / beatDurationSec)

        grid = set()

        for cnb in range(ceilNumBeats):
            for pd in self.possibleSubdivision:
                for i in range(pd):
                    slot = (1.0 / pd) * i + cnb
                    grid.add(slot)

        return grid

    # ------------------------------------------------------------------
    # Extension of existing grid
    # ------------------------------------------------------------------
    def extend_grid_to(self, beats):
        """
        Extend the time grid so that it includes 'beats' (beat position).
        Only extends upward (positive direction).
        """
        if not self.grid:
            return

        gmaxBeats = max(self.grid)

        if beats <= gmaxBeats:
            return

        needed_beats = math.ceil(beats - gmaxBeats)

        start_beat = math.ceil(gmaxBeats)
        end_beat = start_beat + needed_beats

        for cnb in range(start_beat, end_beat):
            for pd in self.possibleSubdivision:
                for i in range(pd):
                    slot = (1.0 / pd) * i + cnb
                    self.grid.add(slot)

    # ------------------------------------------------------------------
    # Quantization
    # ------------------------------------------------------------------
    def quantizeBeat(self, beatRaw, warn=True, extend=False):
        """
        Quantize a (floating) beat position to the closest grid point.

        Parameters
        ----------
        beatRaw : float
            Beat position to quantize.
        warn : bool
            Print a warning if beatRaw lies outside current grid range
            and extend=False.
        extend : bool
            If True, automatically extend the grid so that beatRaw
            lies inside it before quantizing.
        """
        if not self.grid:
            raise ValueError("TimeGrid.quantizeBeat: grid is empty")

        gminBeats = min(self.grid)
        gmaxBeats = max(self.grid)

        # handle outside-range
        if beatRaw < gminBeats or beatRaw > gmaxBeats:
            if extend:
                self.extend_grid_to(beatRaw)
                # update after extending
                gminBeats = min(self.grid)
                gmaxBeats = max(self.grid)
            elif warn:
                print(
                    f"Warning: beat {beatRaw} is outside grid range "
                    f"[{gminBeats}, {gmaxBeats}]"
                )

        # return closest slot
        return min(self.grid, key=lambda x: abs(x - beatRaw))

    def single_subdivision(cls, durationSec, bpm, subdivision):
        """
        Convenience constructor: create a grid that uses exactly ONE
        subdivision value (e.g. only quintuplets, only septuplets, etc.).

        Example:
            g5 = TimeGrid.single_subdivision(4.0, 120, 5)  # 4 sec @ 120 BPM, 5-tuplets
        """
        return cls(
            durationSec=durationSec,
            bpm=bpm,
            possibleSubdivision=[int(subdivision)],
        )

    def combine(cls, grids):
        """
        Combine several TimeGrid instances into a single complex grid.

        All grids must have the same BPM. The resulting grid's duration
        is set so that it covers the full extent of all input grids.

        Usage:
            g5 = TimeGrid.single_subdivision(4.0, 120, 5)
            g7 = TimeGrid.single_subdivision(4.0, 120, 7)
            g8 = TimeGrid.single_subdivision(4.0, 120, 8)

            g_complex = TimeGrid.combine([g5, g7, g8])

        g_complex.grid will contain the UNION of all beat positions
        from g5, g7, and g8.
        """
        grids = list(grids)
        if not grids:
            raise ValueError("TimeGrid.combine: need at least one grid")

        # all BPMs must match
        bpm0 = grids[0].bpm
        for g in grids:
            if g.bpm != bpm0:
                raise ValueError(
                    f"TimeGrid.combine: all grids must have the same BPM "
                    f"(got {bpm0} and {g.bpm})"
                )

        # combined duration = max end-beat * beatDurationSec
        # we estimate end-beat as max(grid)
        max_beat = max(max(g.grid) for g in grids if g.grid)
        beatDurationSec = 60.0 / bpm0
        durationSec = max_beat * beatDurationSec

        # create an "empty" grid object and then overwrite its grid
        combined = cls(durationSec=durationSec, bpm=bpm0, possibleSubdivision=[])
        combined.grid = set()
        for g in grids:
            combined.grid.update(g.grid)

        return combined