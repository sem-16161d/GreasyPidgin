import warnings
import numpy as np
from collections import Counter
import matplotlib.pyplot as plt
from GreasyPidgin.Normalisation import normaliseValues

class Envelope:
    """
    The basic class for working with envelopes.
    Can be initialized from values or breakpoint pairs
    sorts breakpoint pairs automatically if not specified otherwise

    Segment curves
    --------------
    Between two breakpoints the envelope is linear by default. Each segment
    can instead be given a curve shape, in one of two ways:

        Envelope([[0, 0, 'exp'], [1, 10, 'easeOut'], [3, 2]])   # 3rd item of a pair
        Envelope([[0, 0], [1, 10], [3, 2]], curves=['exp', 'easeOut'])

    A curve always belongs to the segment that STARTS at the breakpoint it
    is attached to (the last breakpoint's curve is ignored). Available shapes:

        'linear'                  straight line (default, also None / 0)
        'step' / 'hold'           stay at the start value until the next point
        'exp'                     slow start, fast end (convex)
        'log'                     fast start, slow end (concave)
        'easeIn' / 'easeOut'      quadratic slow start / slow end
        'easeInOut'               smoothstep: slow start and slow end
        'smooth' / 'sine'         cosine ease: slow start and slow end
        <float>                   curvature like SuperCollider's Env curve:
                                  >0 slow start / fast end, <0 fast start /
                                  slow end, 0 linear (larger = stronger)

    The shape describes the progress between the two values, so it works the
    same for rising and falling segments. Polynomial fits (polyFit) ignore
    curves; they approximate the breakpoints only.

    Moving bounds
    -------------
    Every constructor (Envelope(...), from_pairs, from_values, periodic)
    accepts minEnv / maxEnv (plus boundsNormalizedX and boundsSubdivisions)
    to replace the envelope's constant minimum / maximum with envelopes of
    their own; see withBounds(). The constructed shape is then used as a
    normalized 0..1 shape between the floor and the ceiling, so the bounds
    take the place of the envelope's own y-range:

        Envelope.periodic(7.3, 13, minEnv=[0, 0.5, 0.1])
        Envelope([0, 1, 0.3, 0.8], maxEnv=[1, 0.4])

    Jitter
    ------
    Every constructor also accepts jitter (plus jitterMode, jitterClip,
    jitterNormalizedX and seed): a random percentual deviation of each
    breakpoint's y-value, either a fixed amount (0.1 = up to +-10%) or an
    Envelope / list that changes the amount along x; see withJitter().

        Envelope.periodic(7.3, 13, jitter=0.1)
        Envelope.periodic(7.3, 13, jitter=[0, 0.3])      # none at first, up to +-30% at the end

    Order of the constructor modifiers: curves, then minEnv/maxEnv, then
    jitter. Each one also exists as a method: withCurves(), withBounds(),
    withJitter(). These return a modified COPY and leave the original
    untouched, unless overwriteOriginal=True, in which case the envelope is
    changed in place (and returned). setCurves() / setCurve() are plain
    setters and always work in place.

    Polynomial fits
    ---------------
    recalculatePolynomials() (re)fits the polynomials for degrees 1..5 to
    the current breakpoints. It runs automatically on every envelope a
    constructor modifies (bounds or jitter) and on the copy -- or, with
    overwriteOriginal=True, the original -- that withCurves / withBounds /
    withJitter produce, so the fits never describe stale points. A plain
    unmodified envelope only gets fits with polyFit=True.
    """

    CURVE_NAMES = (
        "linear", "step", "exp", "log",
        "easeIn", "easeOut", "easeInOut", "smooth",
    )
    _CURVE_ALIASES = {
        "lin": "linear", "linear": "linear",
        "step": "step", "hold": "step",
        "exp": "exp", "exponential": "exp",
        "log": "log", "logarithmic": "log",
        "easein": "easeIn", "ease_in": "easeIn", "in": "easeIn",
        "easeout": "easeOut", "ease_out": "easeOut", "out": "easeOut",
        "easeinout": "easeInOut", "ease_in_out": "easeInOut", "inout": "easeInOut",
        "smooth": "smooth", "sine": "smooth", "cosine": "smooth",
    }
    _EXP_STRENGTH = 5.0   # curvature used by 'exp' / 'log'
    _MAX_CURVATURE = 100.0

    def __init__(self, data=None, autosort=True, polyFit=False, curves=None,
                 minEnv=None, maxEnv=None, boundsNormalizedX=True,
                 boundsSubdivisions=None, jitter=None, jitterMode="value",
                 jitterClip=True, jitterNormalizedX=True, seed=None):
        self.poly_fits = {}
        self.coefficients = {}  # <- NEW: store poly coefficients by degree
        self.curves = []        # per-segment curve shapes (len(points) - 1)

        if data is None:
            return

        if self._is_pair_list(data):
            env = self.from_pairs(
                data, autosort=autosort, curves=curves,
                minEnv=minEnv, maxEnv=maxEnv,
                boundsNormalizedX=boundsNormalizedX,
                boundsSubdivisions=boundsSubdivisions,
                jitter=jitter, jitterMode=jitterMode, jitterClip=jitterClip,
                jitterNormalizedX=jitterNormalizedX, seed=seed,
            )
        else:
            env = self.from_values(
                data, curves=curves,
                minEnv=minEnv, maxEnv=maxEnv,
                boundsNormalizedX=boundsNormalizedX,
                boundsSubdivisions=boundsSubdivisions,
                jitter=jitter, jitterMode=jitterMode, jitterClip=jitterClip,
                jitterNormalizedX=jitterNormalizedX, seed=seed,
            )

        self.points = env.points
        self.x_range = env.x_range
        self.y_range = env.y_range
        self.curves = env.curves
        self.poly_fits = env.poly_fits
        self.coefficients = env.coefficients
        self.reducedEnv = Envelope()
        if polyFit:
            self.recalculatePolynomials()

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
            and all(
                isinstance(p, (list, tuple))
                and (len(p) == 2 or (len(p) == 3 and Envelope._looks_like_curve(p[2])))
                for p in obj
            )
        )

    @staticmethod
    def _looks_like_curve(c):
        return c is None or isinstance(c, (str, int, float, np.integer, np.floating))

    # -------------------------------------------------------------
    # Curve helpers
    # -------------------------------------------------------------
    @classmethod
    def _check_curve(cls, curve):
        """Validate a curve spec and return its canonical form
        (a name from CURVE_NAMES or a non-zero float)."""
        if curve is None:
            return "linear"
        if isinstance(curve, str):
            key = curve.strip().lower().replace("-", "_").replace(" ", "_")
            if key in cls._CURVE_ALIASES:
                return cls._CURVE_ALIASES[key]
            raise ValueError(
                f"Envelope: unknown curve {curve!r}. Use one of "
                f"{list(cls.CURVE_NAMES)} or a number."
            )
        if isinstance(curve, (int, float, np.integer, np.floating)) and not isinstance(curve, bool):
            c = float(curve)
            if not np.isfinite(c) or abs(c) > cls._MAX_CURVATURE:
                raise ValueError(
                    f"Envelope: numeric curve must be finite with |c| <= {cls._MAX_CURVATURE:g}, got {curve!r}"
                )
            return "linear" if abs(c) < 1e-9 else c
        raise ValueError(f"Envelope: invalid curve spec {curve!r}")

    @classmethod
    def _curve_warp(cls, t: float, curve) -> float:
        """Map linear progress t in [0,1] to curved progress in [0,1]."""
        t = float(t)
        if t <= 0.0:
            return 0.0
        if t >= 1.0:
            return 1.0
        if curve == "linear":
            return t
        if curve == "step":
            return 0.0
        if curve == "easeIn":
            return t * t
        if curve == "easeOut":
            return 1.0 - (1.0 - t) ** 2
        if curve == "easeInOut":
            return t * t * (3.0 - 2.0 * t)
        if curve == "smooth":
            return 0.5 * (1.0 - float(np.cos(np.pi * t)))
        if curve == "exp":
            c = cls._EXP_STRENGTH
        elif curve == "log":
            c = -cls._EXP_STRENGTH
        else:
            c = float(curve)
        return float(np.expm1(c * t) / np.expm1(c))

    def _normalise_curves(self, curves, n_points):
        """Return a canonical per-segment curve list of length n_points-1."""
        n_seg = max(0, n_points - 1)
        if curves is None:
            return ["linear"] * n_seg
        curves = list(curves)
        if len(curves) not in (n_seg, n_points):
            raise ValueError(
                f"Envelope: expected {n_seg} curves (one per segment), got {len(curves)}"
            )
        return [self._check_curve(c) for c in curves[:n_seg]]

    def _curves_for(self, n_points):
        """Stored curves, padded/trimmed defensively to n_points-1 entries
        (also covers envelopes created before curves existed)."""
        stored = list(getattr(self, "curves", None) or [])
        n_seg = max(0, n_points - 1)
        stored = stored[:n_seg] + ["linear"] * (n_seg - len(stored))
        return stored

    def setCurves(self, curves):
        """Replace all segment curves. `curves`: one entry per segment
        (len(points) - 1), or None to reset everything to linear."""
        self.curves = self._normalise_curves(curves, len(self.points))
        return self

    def setCurve(self, segmentIndex: int, curve):
        """Set the curve of one segment (0 = between the first two points)."""
        n_seg = len(self.points) - 1
        if not (0 <= segmentIndex < n_seg):
            raise IndexError(
                f"Envelope.setCurve: segment {segmentIndex} out of range (0..{n_seg - 1})"
            )
        curves = self._curves_for(len(self.points))
        curves[segmentIndex] = self._check_curve(curve)
        self.curves = curves
        return self

    def getCurves(self):
        """Per-segment curve shapes (len(points) - 1 entries)."""
        return self._curves_for(len(getattr(self, "points", []) or []))

    def hasCurves(self) -> bool:
        return any(c != "linear" for c in self.getCurves())

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
    def from_pairs(cls, pairs, autosort=True, curves=None, minEnv=None,
                   maxEnv=None, boundsNormalizedX=True, boundsSubdivisions=None,
                   jitter=None, jitterMode="value", jitterClip=True,
                   jitterNormalizedX=True, seed=None):
        """pairs: [[x, y], ...] or [[x, y, curve], ...]. `curves` (optional)
        gives one curve per segment instead; it cannot be combined with
        3-item pairs. minEnv / maxEnv: see withBounds(); jitter: see
        withJitter()."""
        if not cls._is_pair_list(pairs):
            raise ValueError("Envelope.from_pairs: input must be [[x,y],...] or [[x,y,curve],...].")

        n = len(pairs)
        inline = any(len(p) == 3 for p in pairs)
        if inline and curves is not None:
            raise ValueError(
                "Envelope.from_pairs: give curves either inline ([x,y,curve]) or via curves=, not both."
            )

        # a curve belongs to the breakpoint its segment starts at, so it
        # travels with that point when sorting
        if inline:
            pointCurves = [p[2] if len(p) == 3 else None for p in pairs]
        elif curves is not None:
            seg = cls()._normalise_curves(curves, n)
            pointCurves = seg + [None]
        else:
            pointCurves = [None] * n

        order = list(range(n))
        if autosort:
            order = sorted(order, key=lambda i: pairs[i][0])

        xs = [float(pairs[i][0]) for i in order]
        ys = [float(pairs[i][1]) for i in order]
        sortedCurves = [pointCurves[i] for i in order][:max(0, n - 1)]

        norm, xr, yr = cls._normalize_xy(xs, ys)

        env = cls()
        env.points = norm
        env.x_range = xr
        env.y_range = yr
        env.curves = [cls._check_curve(c) for c in sortedCurves]
        env = cls._apply_modifiers(
            env, minEnv, maxEnv, boundsNormalizedX, boundsSubdivisions,
            jitter, jitterMode, jitterClip, jitterNormalizedX, seed,
        )
        return env

    @classmethod
    def from_values(cls, values, curves=None, minEnv=None, maxEnv=None,
                    boundsNormalizedX=True, boundsSubdivisions=None,
                    jitter=None, jitterMode="value", jitterClip=True,
                    jitterNormalizedX=True, seed=None):
        if not isinstance(values, (list, tuple)):
            raise ValueError("Envelope.from_values: expected list of numbers.")
        if len(values) == 0:
            raise ValueError("Envelope.from_values: cannot build from empty list.")

        pairs = [(i, val) for i, val in enumerate(values)]
        env = cls.from_pairs(
            pairs, curves=curves, minEnv=minEnv, maxEnv=maxEnv,
            boundsNormalizedX=boundsNormalizedX,
            boundsSubdivisions=boundsSubdivisions,
            jitter=jitter, jitterMode=jitterMode, jitterClip=jitterClip,
            jitterNormalizedX=jitterNormalizedX, seed=seed,
        )
        return env

    # ---- periodic generator -------------------------------------
    @staticmethod
    def _periodic_shape(shape):
        """Return f(phase_in_cycles) -> value in [-1, 1]."""
        if callable(shape):
            return shape
        key = str(shape).strip().lower().replace("-", "_").replace(" ", "_")
        fns = {
            "sine":      lambda p: float(np.sin(2 * np.pi * p)),
            "cosine":    lambda p: float(np.cos(2 * np.pi * p)),
            "triangle":  lambda p: 1.0 - 4.0 * abs(((p + 0.25) % 1.0) - 0.5),
            "saw":       lambda p: 2.0 * (p % 1.0) - 1.0,
            "saw_down":  lambda p: 1.0 - 2.0 * (p % 1.0),
            "square":    lambda p: 1.0 if (p % 1.0) < 0.5 else -1.0,
        }
        aliases = {"sin": "sine", "cos": "cosine", "tri": "triangle",
                   "sawtooth": "saw", "ramp": "saw", "rampup": "saw",
                   "rampdown": "saw_down", "sawdown": "saw_down"}
        key = aliases.get(key, key)
        if key not in fns:
            raise ValueError(
                f"Envelope.periodic: unknown shape {shape!r}. Use one of "
                f"{sorted(fns)} or a function f(phase_in_cycles) -> [-1, 1]."
            )
        return fns[key]

    @classmethod
    def periodic(cls, periods=1.0, resolution=16, shape="sine", phase=0.0,
                 xRange=(0.0, 1.0), yRange=(0.0, 1.0), includeEnd=True,
                 minEnv=None, maxEnv=None, boundsNormalizedX=True,
                 boundsSubdivisions=None, jitter=None, jitterMode="value",
                 jitterClip=True, jitterNormalizedX=True, seed=None):
        """
        Build an envelope from a simple periodic function.

        periods    : number of cycles to generate; may be fractional
                      (7.3 -> seven full cycles plus 30% of an eighth)
        resolution : breakpoints per cycle (13 -> a point every 1/13 cycle)
        shape      : 'sine' (starts at the middle, rising), 'cosine' (starts
                      at the top), 'triangle' (like sine), 'saw' (rises from
                      the bottom), 'saw_down' (falls from the top), 'square'
                      (starts high; built from step segments), or a function
                      f(phase_in_cycles) -> value in [-1, 1]
        phase      : phase offset in cycles (0.25 shifts a sine into a cosine)
        xRange     : x domain of the result, normalized (0, 1) by default
        yRange     : y domain the wave is scaled to, (0, 1) by default; the
                      full wave always spans exactly yRange, so a sine
                      oscillates around its centre
        includeEnd : always put a final breakpoint exactly at the end of the
                      last (partial) cycle, even if it falls between two
                      resolution steps

        minEnv / maxEnv : optional moving floor / ceiling (see withBounds());
                      the wave is then squeezed between them instead of
                      spanning yRange.
        jitter     : optional random deviation of the values (see withJitter())

        The result is a normal Envelope (y_range = yRange), so getValue,
        displayAscii, withBounds etc. all work on it.
        """
        periods = float(periods)
        if not np.isfinite(periods) or periods <= 0:
            raise ValueError("Envelope.periodic: periods must be > 0")
        resolution = int(resolution)
        if resolution < 1:
            raise ValueError("Envelope.periodic: resolution must be >= 1")
        for name, rng in (("xRange", xRange), ("yRange", yRange)):
            try:
                ok = len(rng) == 2
            except TypeError:
                ok = False
            if not ok:
                raise ValueError(
                    f"Envelope.periodic: {name} must be a (min, max) pair, got {rng!r}. "
                    f"Argument order is periodic(periods, resolution, shape, phase, "
                    f"xRange, yRange, ...), so pass the y-range as a keyword, "
                    f"e.g. yRange=(0, 0.1)."
                )

        f = cls._periodic_shape(shape)

        nGrid = int(np.floor(periods * resolution + 1e-9))
        cycles = [k / resolution for k in range(nGrid + 1)]
        if includeEnd and periods - cycles[-1] > 1e-9:
            cycles.append(periods)
        if len(cycles) < 2:
            cycles.append(periods)   # at least a start and an end point

        pts = []
        for c in cycles:
            v = float(np.clip(f(c + phase), -1.0, 1.0))
            pts.append((c / periods, 0.5 + 0.5 * v))

        env = cls()
        env.points = pts
        env.x_range = (float(xRange[0]), float(xRange[1]))
        env.y_range = (float(yRange[0]), float(yRange[1]))
        if str(shape).strip().lower() == "square":
            env.curves = ["step"] * (len(pts) - 1)
        return cls._apply_modifiers(
            env, minEnv, maxEnv, boundsNormalizedX, boundsSubdivisions,
            jitter, jitterMode, jitterClip, jitterNormalizedX, seed,
        )

    @staticmethod
    def _apply_modifiers(env, minEnv, maxEnv, boundsNormalizedX, boundsSubdivisions,
                         jitter, jitterMode, jitterClip, jitterNormalizedX, seed):
        """Shared tail of all constructors: moving bounds, then jitter."""
        if minEnv is not None or maxEnv is not None:
            env = env.withBounds(minEnv, maxEnv, normalizedX=boundsNormalizedX,
                                 subdivisions=boundsSubdivisions)
        if jitter is not None:
            env = env.withJitter(jitter, mode=jitterMode, clip=jitterClip,
                                 normalizedX=jitterNormalizedX, seed=seed)
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
        target.curves = self._curves_for(len(self.points))

        return target

    # -------------------------------------------------------------
    # Bounds (moving minimum / maximum)
    # -------------------------------------------------------------
    @staticmethod
    def _as_bound(b):
        if b is None or isinstance(b, Envelope):
            return b
        if isinstance(b, (int, float, np.integer, np.floating)):
            return float(b)
        if isinstance(b, (list, tuple)):
            return Envelope(b)
        raise ValueError(f"Envelope.withBounds: cannot use {b!r} as a bound")

    def _finish_modification(self, new, overwriteOriginal: bool):
        """Common tail of withCurves / withBounds / withJitter: refit the
        polynomials on `new`, then either return it as a copy (original
        untouched) or move its state into self (overwriteOriginal=True)."""
        new.recalculatePolynomials()
        if not overwriteOriginal:
            return new
        self.points = new.points
        self.x_range = new.x_range
        self.y_range = new.y_range
        self.curves = new.curves
        self.poly_fits = new.poly_fits
        self.coefficients = new.coefficients
        if hasattr(self, "reducedEnv"):
            self.reducedEnv = Envelope()   # derived from the old points
        return self

    def withBounds(self, minEnv=None, maxEnv=None, normalizedX: bool = True,
                   subdivisions=None, overwriteOriginal: bool = False):
        """
        Return a new envelope in which this envelope's minimum and maximum
        are themselves envelopes: its shape (the normalized 0..1 y-values)
        is squeezed between a moving floor and a moving ceiling,

            out(x) = floor(x) + shape(x) * (ceiling(x) - floor(x))

        minEnv / maxEnv : the floor / ceiling. Each can be an Envelope, a
                           list (read as Envelope(list)), a plain number
                           (constant), or None (keep this envelope's own
                           y_range minimum / maximum). Bounds are in
                           absolute y units, e.g. a floor of [0, 0.5, 0.1]
                           rises from 0 to 0.5 in the middle and falls to
                           0.1 at the end.
        normalizedX     : True (default) stretches the bound envelopes over
                           this envelope's whole x span; False places them
                           by their own x_range in this envelope's x units.
        subdivisions    : extra evaluation points per segment. The product of
                           two changing lines is a curve, so with moving
                           bounds (or curved segments) the result is
                           sampled; default 8 then, 0 when the bounds are
                           constant and all segments are linear (exact).

        overwriteOriginal : False (default) returns a new envelope and leaves
                           this one untouched; True changes this envelope in
                           place and returns it.

        The result has linear segments and no curves. If a floor ends up
        above its ceiling the shape is simply inverted there. Polynomial fits
        are recalculated on the result.
        """
        if not getattr(self, "points", None):
            raise ValueError("Envelope.withBounds: empty envelope")

        lo = self._as_bound(minEnv)
        hi = self._as_bound(maxEnv)
        x_min, x_max = self.x_range
        x_span = (x_max - x_min) or 1.0
        y_min, y_max = self.y_range

        def bound_at(b, default, xn):
            if b is None:
                return float(default)
            if isinstance(b, float):
                return b
            if normalizedX:
                return b.getValue(xn, normalizedX=True, normalizedY=False)
            return b.getValue(x_min + xn * x_span, normalizedX=False, normalizedY=False)

        # breakpoints: this envelope's own plus those of the bounds
        xs = {round(float(x), 12) for x, _ in self.points}
        moving = False
        for b in (lo, hi):
            if isinstance(b, Envelope):
                moving = True
                for bx, _ in b.points:
                    xn = float(bx) if normalizedX else self._x_to_norm(b._x_from_norm(bx), False)
                    if 0.0 <= xn <= 1.0:
                        xs.add(round(xn, 12))
        xs.update((0.0, 1.0))
        xs = sorted(xs)

        if subdivisions is None:
            subdivisions = 8 if (moving or self.hasCurves()) else 0
        subdivisions = max(0, int(subdivisions))
        if subdivisions:
            dense = []
            for a, b in zip(xs[:-1], xs[1:]):
                dense.extend(a + (b - a) * j / (subdivisions + 1) for j in range(subdivisions + 1))
            dense.append(xs[-1])
            xs = dense

        pairs = []
        for xn in xs:
            shape = self.getValue(xn, normalizedX=True, normalizedY=True)
            floor_v = bound_at(lo, y_min, xn)
            ceil_v = bound_at(hi, y_max, xn)
            pairs.append([x_min + xn * x_span, floor_v + shape * (ceil_v - floor_v)])

        if len(pairs) == 1:
            pairs.append([x_max, pairs[0][1]])
        out = Envelope.from_pairs(pairs)
        if x_max != x_min:
            out.x_range = (x_min, x_max)
        return self._finish_modification(out, overwriteOriginal)

    def withCurves(self, curves, overwriteOriginal: bool = False):
        """Return a copy with the given per-segment curves (see setCurves()).
        overwriteOriginal=True changes this envelope in place instead."""
        out = self.rescale()
        out.setCurves(curves)
        return self._finish_modification(out, overwriteOriginal)

    def withJitter(self, jitter, mode: str = "value", clip: bool = True,
                   normalizedX: bool = True, seed=None,
                   overwriteOriginal: bool = False):
        """
        Return a new envelope whose breakpoint y-values are randomly
        deviated by a percentage.

        jitter      : the deviation amount, as a fraction (0.1 = up to +-10%).
                       A number is used for every breakpoint; an Envelope or
                       a list (read as Envelope(list)) varies the amount
                       along x, e.g. [0, 0.3] grows from no jitter to +-30%.
                       The jitter envelope's y-values are the fractions
                       themselves (absolute y units).
        mode        : 'value' (default): the deviation is a percentage of
                       the breakpoint's own value, y * (1 + jitter * r);
                       a value of 0 therefore never moves.
                       'range': the deviation is a percentage of the
                       envelope's whole y-span, so zeros move as well.
                       r is uniformly random in [-1, 1] for every breakpoint.
        clip        : True (default) keeps the envelope's current y_range
                       and clips jittered values into it; False lets values
                       leave it and re-fits the y_range to the jittered data.
        normalizedX : True stretches a jitter Envelope over this envelope's
                       whole x span; False places it by its own x_range in
                       this envelope's x units.
        seed        : optional seed for a reproducible result.
        overwriteOriginal : False (default) returns a new envelope and leaves
                       this one untouched; True changes this envelope in
                       place and returns it.

        x positions and segment curves are kept; polynomial fits are
        recalculated on the jittered points.
        """
        if not getattr(self, "points", None):
            raise ValueError("Envelope.withJitter: empty envelope")
        if mode not in ("value", "range"):
            raise ValueError(
                f"Envelope.withJitter: unknown mode {mode!r} (use 'value' or 'range')"
            )
        j = self._as_bound(jitter)
        if j is None:
            return self._finish_modification(self.rescale(), overwriteOriginal)

        x_min, x_max = self.x_range
        x_span = (x_max - x_min) or 1.0
        y_min, y_max = self.y_range
        y_span = y_max - y_min
        rng = np.random.default_rng(seed)

        absX, absY = [], []
        for xn, yn in self.points:
            if isinstance(j, float):
                amount = j
            elif normalizedX:
                amount = j.getValue(xn, normalizedX=True, normalizedY=False)
            else:
                amount = j.getValue(x_min + xn * x_span, normalizedX=False, normalizedY=False)
            amount = abs(float(amount))
            r = float(rng.uniform(-1.0, 1.0))
            y = y_min + yn * y_span
            y = y * (1.0 + amount * r) if mode == "value" else y + amount * y_span * r
            absX.append(x_min + xn * x_span)
            absY.append(y)

        if not clip:
            out = Envelope.from_pairs(
                [[x, y] for x, y in zip(absX, absY)], autosort=False,
                curves=self._curves_for(len(self.points)),
            )
            out.x_range = (x_min, x_max)
            return self._finish_modification(out, overwriteOriginal)

        lo, hi = min(y_min, y_max), max(y_min, y_max)
        out = Envelope()
        out.points = [
            (xn, float(np.clip((min(max(y, lo), hi) - y_min) / y_span, 0.0, 1.0)) if y_span else 0.0)
            for (xn, _), y in zip(self.points, absY)
        ]
        out.x_range = self.x_range
        out.y_range = self.y_range
        out.curves = self._curves_for(len(self.points))
        return self._finish_modification(out, overwriteOriginal)

    def _x_from_norm(self, xn: float) -> float:
        x_min, x_max = self.x_range
        return x_min + float(xn) * ((x_max - x_min) or 1.0)

    # -------------------------------------------------------------
    # Polynomial fitting
    # -------------------------------------------------------------
    def recalculatePolynomials(self):
        """(Re)fit the polynomials of degree 1..5 to the current breakpoints,
        in place. Returns self."""
        pts = getattr(self, "points", None) or []
        if len(pts) < 2:
            self.poly_fits = {}
            self.coefficients = {}  # <- NEW
            return self

        xs = np.array([p[0] for p in pts], dtype=float)
        ys = np.array([p[1] for p in pts], dtype=float)

        self.poly_fits = {}
        self.coefficients = {}  # <- NEW

        for deg in range(1, 6):
            with warnings.catch_warnings():
                # few breakpoints + high degree: ill-conditioned but harmless
                warnings.simplefilter("ignore")
                coeffs = np.polyfit(xs, ys, deg)          # highest power first
            poly = np.poly1d(coeffs)

            # store coefficients as plain Python floats (JSON/pickle friendly)
            self.coefficients[deg] = [float(c) for c in coeffs]

            # store clamped callable
            self.poly_fits[deg] = lambda x, p=poly: np.clip(p(x), 0.0, 1.0)

        return self

    _auto_fit_polynomials = recalculatePolynomials   # backwards-compatible name

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
        # Default: piecewise envelope (linear unless segment curves are set)
        # ---------------------------------------------------------
        pts, curves = self._sorted_points_and_curves()
        y_norm = self._y_at_x_norm(
            x_norm,
            pts,
            interpolateOutsideOfRange,
            curves,
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

    def _sorted_points_and_curves(self):
        """Points sorted by x, with the curve of each segment following the
        breakpoint it starts at."""
        n = len(self.points)
        stored = self._curves_for(n)
        order = sorted(range(n), key=lambda i: self.points[i][0])
        pts = [self.points[i] for i in order]
        curves = [stored[i] if i < n - 1 else "linear" for i in order[:-1]]
        return pts, curves

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

    def _y_at_x_norm(self, x_norm: float, pts, allow_extrap: bool, curves=None) -> float:
        x_norm = float(x_norm)
        n = len(pts)
        if curves is None:
            curves = ["linear"] * max(0, n - 1)

        if n == 1:
            return float(pts[0][1])

        x0, y0 = pts[0]
        xN, yN = pts[-1]

        if x_norm <= x0:
            return self._y_extrap_left(x_norm, pts, curves) if allow_extrap else float(y0)

        if x_norm >= xN:
            return self._y_extrap_right(x_norm, pts, curves) if allow_extrap else float(yN)

        return self._y_interp_inside(x_norm, pts, curves)

    def _y_interp_inside(self, x: float, pts, curves=None) -> float:
        for i, ((xa, ya), (xb, yb)) in enumerate(zip(pts[:-1], pts[1:])):
            if xa <= x <= xb:
                curve = curves[i] if curves else "linear"
                if curve == "linear":
                    return self._lerp(x, xa, ya, xb, yb)
                return self._curved(x, xa, ya, xb, yb, curve)
        return float(pts[-1][1])  # fallback

    # Extrapolation outside the breakpoints continues the straight line
    # through the edge segment's two endpoints; a 'step' edge segment holds
    # its edge value instead.
    def _y_extrap_left(self, x: float, pts, curves=None) -> float:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        if curves and curves[0] == "step":
            return float(y0)
        return self._lerp(x, x0, y0, x1, y1)

    def _y_extrap_right(self, x: float, pts, curves=None) -> float:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        if curves and curves[-1] == "step":
            return float(y2)
        return self._lerp(x, x1, y1, x2, y2)

    @classmethod
    def _curved(cls, x: float, xa: float, ya: float, xb: float, yb: float, curve) -> float:
        if xb == xa:
            return float(ya)
        t = (x - xa) / (xb - xa)
        w = cls._curve_warp(t, curve)
        return float(ya + w * (yb - ya))

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
        if self.hasCurves():
            # curved segments: draw the sampled shape, breakpoints as dots
            x_curve_norm = np.linspace(0, 1, 400)
            y_curve_norm = np.array([self.getValue(float(x), True, True) for x in x_curve_norm])
            if use_normalized:
                x_curve, y_curve = x_curve_norm, y_curve_norm
            else:
                x_min, x_max = self.x_range
                y_min, y_max = self.y_range
                x_curve = x_min + x_curve_norm * (x_max - x_min)
                y_curve = y_min + y_curve_norm * (y_max - y_min)
            plt.plot(x_curve, y_curve, "-", label="Envelope")
            plt.plot(xs, ys, "o", color="C0")
        else:
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

    def displayAscii(self, maxWidth: int = 60, maxHeight: int = 20, use_normalized: bool = False) -> str:
        """
        Print a terminal-friendly ASCII rendering of the envelope using 'O'
        characters — a counterpart to display() for when a matplotlib
        window isn't available or wanted (e.g. over ssh, in a log).

        The envelope's shape (linear or curved segments) is sampled one
        column at a time (via getValue()) rather than only plotting the
        breakpoints, so curved-looking or steep segments still read as a
        continuous line rather than scattered dots.

        maxWidth  : number of character columns spanning the x-axis
        maxHeight : number of character rows spanning the y-axis
        use_normalized : label the axes in normalized [0,1] coordinates
                          instead of the original x_range/y_range domain
                          (the traced shape itself is identical either way)

        Returns the rendered string (also printed) so it can be captured
        or logged.
        """
        if not getattr(self, "points", None):
            raise ValueError("Envelope.displayAscii: empty envelope")

        width  = max(2, int(maxWidth))
        height = max(2, int(maxHeight))

        # sample the envelope at one x per column
        rows = []
        for col in range(width):
            xNorm = col / (width - 1)
            yNorm = self.getValue(xNorm, normalizedX=True, normalizedY=True)
            yNorm = min(1.0, max(0.0, float(yNorm)))
            rows.append(int(round((1.0 - yNorm) * (height - 1))))

        # plot each column, connecting to the previous column's row with a
        # vertical run of 'O's so steep segments don't look like dotted gaps
        grid = [[" "] * width for _ in range(height)]
        grid[rows[0]][0] = "O"
        for col in range(1, width):
            r0, r1 = rows[col - 1], rows[col]
            lo, hi = (r0, r1) if r0 <= r1 else (r1, r0)
            for r in range(lo, hi + 1):
                grid[r][col] = "O"

        if use_normalized or self.x_range is None or self.y_range is None:
            xLabel = "x: [0, 1] (normalized)"
            yTop, yBottom = "1", "0"
        else:
            x_min, x_max = self.x_range
            y_min, y_max = self.y_range
            xLabel = f"x: [{x_min:g}, {x_max:g}]"
            yTop, yBottom = f"{y_max:g}", f"{y_min:g}"

        yLabelWidth = max(len(yTop), len(yBottom))
        lines = []
        for r, rowChars in enumerate(grid):
            if r == 0:
                label = yTop
            elif r == height - 1:
                label = yBottom
            else:
                label = ""
            lines.append(f"{label:>{yLabelWidth}} | {''.join(rowChars)}")

        lines.append(" " * (yLabelWidth + 1) + "+" + "-" * (width + 1))
        lines.append(" " * (yLabelWidth + 3) + xLabel)

        art = "\n".join(lines)
        print(art)
        return art

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

    def histogram(self, normalized: bool = False, rounding: int = 6, sortBy: str = "value") -> dict:
        """
        Count how often each unique y-value appears among this envelope's
        breakpoints (the same Counter machinery behind most_common_y() /
        least_common_y(), exposed as the full distribution).

        normalized : count normalized [0,1] y-values instead of the
                      original y_range domain
        rounding   : decimal places used to bucket near-identical floats
                      together, so e.g. 0.30000000004 and 0.3 count as
                      the same value (matches most_common_y/least_common_y)
        sortBy     : 'value' (ascending y, default) or 'count' (most
                      frequent first)

        Returns {yValue: count, ...}.
        """
        ys = self._get_y_values(normalized=normalized)
        if not ys:
            raise ValueError("Envelope.histogram: no y-values to analyze")

        rounded = [round(float(y), rounding) for y in ys]
        counts = Counter(rounded)

        if sortBy == "value":
            items = sorted(counts.items(), key=lambda kv: kv[0])
        elif sortBy == "count":
            items = counts.most_common()
        else:
            raise ValueError(
                f"Envelope.histogram: unknown sortBy {sortBy!r} (use 'value' or 'count')"
            )

        return {k: v for k, v in items}

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
            f"y_range={self.y_range}\n   curves={self.getCurves()}\n   "
            f"coefficients={getattr(self,'coefficients',{})})"
        )