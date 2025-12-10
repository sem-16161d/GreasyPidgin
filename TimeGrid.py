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
            possibleSubdivision = [1]

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
