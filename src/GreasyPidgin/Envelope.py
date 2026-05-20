import numpy as np
from collections import Counter

from GreasyPidgin.Normalisation import normaliseValues

class Envelope:
    """
    The basic class for working with envelopes.
    Can be initialized from values or breakpoint pairs
    sorts breakpoint pairs automatically if not specified otherwise
    """

    def __init__(self, data=None, autosort=True, polyFit=False):
        self.poly_fits = {}
        self.coefficients = {}  # <- NEW: store poly coefficients by degree

        if data is None:
            return

        if self._is_pair_list(data):
            env = self.from_pairs(data, autosort=autosort)
        else:
            env = self.from_values(data)

        self.points = env.points
        self.x_range = env.x_range
        self.y_range = env.y_range
        self.reducedEnv = Envelope()
        if polyFit:
            self._auto_fit_polynomials()

    # -------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------
    @staticmethod
    def _clip01(val):
        return np.clip(val, 0.0, 1.0)

    @staticmethod
    def _is_pair_list(obj):
        return (
            isinstance(obj, (list, tuple))
            and len(obj) > 0
            and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in obj)
        )

    @staticmethod
    def _normalize_xy(xs, ys):
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        x_span = x_max - x_min if x_max != x_min else 1.0
        y_span = y_max - y_min if y_max != y_min else 1.0

        norm = [((x - x_min) / x_span, (y - y_min) / y_span) for x, y in zip(xs, ys)]
        return norm, (x_min, x_max), (y_min, y_max)

    # -------------------------------------------------------------
    # Constructors
    # -------------------------------------------------------------
    @classmethod
    def from_pairs(cls, pairs, autosort=True):
        if not cls._is_pair_list(pairs):
            raise ValueError("Envelope.from_pairs: input must be [[x,y],...].")

        if autosort:
            pairs = sorted(pairs, key=lambda p: p[0])

        xs = [float(p[0]) for p in pairs]
        ys = [float(p[1]) for p in pairs]

        norm, xr, yr = cls._normalize_xy(xs, ys)

        env = cls()
        env.points = norm
        env.x_range = xr
        env.y_range = yr
        env.poly_fits = {}
        env.coefficients = {}  # <- NEW
        return env

    @classmethod
    def from_values(cls, values):
        if not isinstance(values, (list, tuple)):
            raise ValueError("Envelope.from_values: expected list of numbers.")
        if len(values) == 0:
            raise ValueError("Envelope.from_values: cannot build from empty list.")

        pairs = [(i, val) for i, val in enumerate(values)]
        env = cls.from_pairs(pairs)
        return env

    def rescale(self, new_x_range=None, new_y_range=None, inplace=False):
        if not self.points:
            raise ValueError("Envelope.rescale: empty envelope")

        target = self if inplace else Envelope()

        # copy normalized points (unchanged)
        target.points = list(self.points)

        # set ranges
        target.x_range = tuple(new_x_range) if new_x_range is not None else self.x_range
        target.y_range = tuple(new_y_range) if new_y_range is not None else self.y_range

        # copy polynomial fits + coeffs (still valid because internal norm unchanged)
        target.poly_fits = dict(self.poly_fits)
        target.coefficients = dict(getattr(self, "coefficients", {}))  # <- NEW

        return target

    # -------------------------------------------------------------
    # Polynomial fitting
    # -------------------------------------------------------------
    def _auto_fit_polynomials(self):
        pts = self.points
        if len(pts) < 2:
            self.poly_fits = {}
            self.coefficients = {}  # <- NEW
            return

        xs = np.array([p[0] for p in pts], dtype=float)
        ys = np.array([p[1] for p in pts], dtype=float)

        self.poly_fits = {}
        self.coefficients = {}  # <- NEW

        for deg in range(1, 6):
            coeffs = np.polyfit(xs, ys, deg)          # highest power first
            poly = np.poly1d(coeffs)

            # store coefficients as plain Python floats (JSON/pickle friendly)
            self.coefficients[deg] = [float(c) for c in coeffs]

            # store clamped callable
            self.poly_fits[deg] = lambda x, p=poly: np.clip(p(x), 0.0, 1.0)

  
    # -------------------------------------------------------------
    # data reduction
    # -------------------------------------------------------------  

    def _internalRenderNorm(self, resolution = 20):
        return [self.getValue(i/resolution, True, True) for i in range(resolution)]
            

    def _differentiate(self,values):
        out = [values[0]]
        for i,v in enumerate(values[1:]):
            out.append(values[i]-v) 
        return out

    def _minimaMaxima(self,values):
        differentiated = self._differentiate(values)
        minima, maxima = [],[]
        for i,d in enumerate(differentiated):
            if d <=0:
                minima.append((i, values[i], d))
            else:
                maxima.append((i, values[i], d))
        minima = sorted(minima, key= lambda v: v[2])
        maxima = sorted(maxima, key= lambda v: v[2])
        return minima, maxima

    def reduceEnvPoints(self, numMinima = 3, numMaxima = 3, resolution = 20):
        values = self._internalRenderNorm(resolution)
        mima = self._minimaMaxima(values)
        newEnvPoints = []
        # print(mima[0])
        for triple in mima[0][:(numMinima+1)]:
            newEnvPoints.append(triple[:2])
        for triple in list(reversed(mima[1]))[:(numMaxima+1)]:
            newEnvPoints.append(triple[:2])
        self.reducedEnv = Envelope(newEnvPoints)

    # -------------------------------------------------------------
    # Value lookup
    # -------------------------------------------------------------
    def getValue(
        self,
        xPos,
        normalizedX: bool = False,
        normalizedY: bool = False,
        interpolateOutsideOfRange: bool = True,
        polyDegree: int = 0,
    ):
        if not getattr(self, "points", None):
            raise ValueError("Envelope.getValue: empty envelope")

        # convert x to normalized domain
        x_norm = self._x_to_norm(xPos, normalizedX)

        # ---------------------------------------------------------
        # Polynomial branch
        # ---------------------------------------------------------
        if polyDegree and polyDegree > 0:
            if not self.poly_fits:
                raise ValueError("Envelope.getValue: no polynomial fits available")

            if polyDegree not in self.poly_fits:
                raise ValueError(
                    f"Envelope.getValue: polynomial degree {polyDegree} not fitted"
                )

            y_norm = float(self.poly_fits[polyDegree](x_norm))
            return self._y_from_norm(y_norm, normalizedY)

        # ---------------------------------------------------------
        # Default: piecewise linear envelope
        # ---------------------------------------------------------
        pts = self._sorted_points()
        y_norm = self._y_at_x_norm(
            x_norm,
            pts,
            interpolateOutsideOfRange
        )

        return self._y_from_norm(y_norm, normalizedY)


    # map to grids
    def mapToGrid(self, xGrid, yGrid):
        xList = xGrid.sorted()
        xMin, xMax = min(xList), max(xList)
        xRange = xMax - xMin
        vals = [(min(xList), yGrid.quantise(self.getValue(0, True)))]
        lastY = vals[0][1]
        for xNorm in normaliseValues(xList)[1:]:
            yCandidate = yGrid.quantise(self.getValue(xNorm, True))
            if yCandidate != lastY:
                vals.append((xNorm * xRange + xMin, yCandidate))
                lastY = yCandidate
        return vals

    # ---------------- helpers ----------------
    def _sorted_points(self):
        return sorted(self.points, key=lambda p: p[0])

    def _x_to_norm(self, xPos, normalizedX: bool) -> float:
        if normalizedX:
            return float(xPos)

        if self.x_range is None:
            raise ValueError("Envelope.getValue: missing x_range")

        x_min, x_max = self.x_range
        span = (x_max - x_min) or 1.0
        return (float(xPos) - x_min) / span

    def _y_from_norm(self, y_norm: float, normalizedY: bool) -> float:
        y_norm = float(y_norm)
        if normalizedY:
            return y_norm

        if self.y_range is None:
            raise ValueError("Envelope.getValue: missing y_range")

        y_min, y_max = self.y_range
        return float(y_min + y_norm * (y_max - y_min))

    def _y_at_x_norm(self, x_norm: float, pts, allow_extrap: bool) -> float:
        x_norm = float(x_norm)
        n = len(pts)

        if n == 1:
            return float(pts[0][1])

        x0, y0 = pts[0]
        xN, yN = pts[-1]

        if x_norm <= x0:
            return self._y_extrap_left(x_norm, pts) if allow_extrap else float(y0)

        if x_norm >= xN:
            return self._y_extrap_right(x_norm, pts) if allow_extrap else float(yN)

        return self._y_interp_inside(x_norm, pts)

    def _y_interp_inside(self, x: float, pts) -> float:
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            if xa <= x <= xb:
                return self._lerp(x, xa, ya, xb, yb)
        return float(pts[-1][1])  # fallback

    def _y_extrap_left(self, x: float, pts) -> float:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        return self._lerp(x, x0, y0, x1, y1)

    def _y_extrap_right(self, x: float, pts) -> float:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        return self._lerp(x, x1, y1, x2, y2)

    @staticmethod
    def _lerp(x: float, xa: float, ya: float, xb: float, yb: float) -> float:
        if xb == xa:
            return float(ya)
        t = (x - xa) / (xb - xa)
        return float(ya + t * (yb - ya))

    # -------------------------------------------------------------
    # Display
    # -------------------------------------------------------------
    def display(self, use_normalized=False, show_polynomials=False, showReduced = False):
        import matplotlib.pyplot as plt

        if not self.points:
            raise ValueError("Envelope.display: empty envelope")

        xsN = np.array([p[0] for p in self.points])
        ysN = np.array([p[1] for p in self.points])

        if use_normalized:
            xs, ys = xsN, ysN
        else:
            x_min, x_max = self.x_range
            y_min, y_max = self.y_range
            xs = x_min + xsN * (x_max - x_min)
            ys = y_min + ysN * (y_max - y_min)

        plt.figure(figsize=(6, 4))
        plt.plot(xs, ys, "o-", label="Envelope")

        if show_polynomials:
            x_dense_norm = np.linspace(0, 1, 400)
            for deg, poly in self.poly_fits.items():
                y_dense_norm = poly(x_dense_norm)
                if use_normalized:
                    x_dense = x_dense_norm
                    y_dense = y_dense_norm
                else:
                    x_min, x_max = self.x_range
                    y_min, y_max = self.y_range
                    x_dense = x_min + x_dense_norm * (x_max - x_min)
                    y_dense = y_min + y_dense_norm * (y_max - y_min)

                plt.plot(x_dense, y_dense, "--", label=f"poly deg {deg}")

        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def _get_y_values(self, normalized: bool = False):
        """
        Return a list of y-values.

        If normalized=True  -> internal normalized y in [0,1]
        If normalized=False -> mapped back to original y-domain via y_range
        """
        if not self.points:
            raise ValueError("Envelope._get_y_values: envelope has no points")

        ys_norm = [float(y) for _, y in self.points]

        if normalized:
            return ys_norm

        if self.y_range is None:
            raise ValueError(
                "Envelope._get_y_values: y_range is not set; cannot denormalize."
            )

        y_min, y_max = self.y_range
        y_span = y_max - y_min if y_max != y_min else 1.0
        return [y_min + yn * y_span for yn in ys_norm]

    # ------------------------------------------------------------------
    # Statistical descriptors on y-values
    # ------------------------------------------------------------------
    def most_common_y(self, normalized: bool = False, rounding: int = 6):
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.most_common_y: no y-values to analyze")

        rounded = [round(y, rounding) for y in ys]
        counts = Counter(rounded)
        mode_val, _ = counts.most_common(1)[0]
        return float(mode_val)

    def least_common_y(self, normalized: bool = False, rounding: int = 6):
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.least_common_y: no y-values to analyze")

        rounded = [round(y, rounding) for y in ys]
        counts = Counter(rounded)
        
        mode_val= counts.most_common()[-1][0]
        return float(mode_val)

    def mean_y(self, normalized: bool = False):
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.mean_y: no y-values to analyze")
        return float(np.mean(ys))

    def median_y(self, normalized: bool = False):
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.median_y: no y-values to analyze")
        return float(np.median(ys))

    def std_y(self, normalized: bool = False, ddof: int = 0):
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.std_y: no y-values to analyze")
        return float(np.std(ys, ddof=ddof))

    # -------------------------------------------------------------
    def __repr__(self):
        return (
            f"Envelope\n   pointsNorm={self.points}\n   x_range={self.x_range}, "
            f"y_range={self.y_range}\n   coefficients={getattr(self,'coefficients',{})})"
        )