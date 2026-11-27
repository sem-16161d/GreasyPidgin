/*
Envelope.js — JavaScript port of GreasyPidgin/Envelope.py

Breakpoint envelopes with per-segment curves, moving bounds, jitter,
polynomial fits and simple statistics. Points are stored normalized
(x and y in 0..1) together with the original x_range / y_range.

Runs in Max 9 [v8] and in Node.

    Max:   var Envelope = require("Envelope").Envelope;
    Node:  const { Envelope } = require("./Envelope");

Differences from the Python version
-----------------------------------
- Keyword arguments become an options object as the last argument:
      new Envelope([[0, 0, "exp"], [1, 10], [3, 2]], { minEnv: [0, 2] })
      Envelope.periodic(7.3, 13, { shape: "triangle", jitter: 0.1 })
      env.withBounds([0, 0.5, 0.1], null, { subdivisions: 4 })
- Points are [x, y] arrays instead of tuples.
- withJitter(seed) is reproducible within JavaScript, but gives other
  numbers than Python's numpy generator for the same seed.
- histogram() returns a Map (keeps the order; object keys would be re-sorted).
- display() (matplotlib) does not exist; use displayAscii().

Segment curves
--------------
    'linear'                  straight line (default, also null / 0)
    'step' / 'hold'           stay at the start value until the next point
    'exp'                     slow start, fast end (convex)
    'log'                     fast start, slow end (concave)
    'easeIn' / 'easeOut'      quadratic slow start / slow end
    'easeInOut'               smoothstep: slow start and slow end
    'smooth' / 'sine'         cosine ease: slow start and slow end
    <number>                  curvature like SuperCollider's Env curve
                              (> 0 slow start / fast end, < 0 the opposite)

A curve belongs to the segment that STARTS at its breakpoint.
*/

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const clip = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const mod = (a, b) => ((a % b) + b) % b;              // Python-style modulo
const roundTo = (x, decimals) => Number(Number(x).toFixed(decimals));
const isNumber = v => typeof v === "number";

function print(text) {
    if (typeof post === "function") post(text + "\n");  // Max
    else console.log(text);                             // Node
}

// Seeded uniform generator (mulberry32); null seed -> Math.random
function makeRandom(seed) {
    if (seed === null || seed === undefined) return Math.random;
    let a = Math.floor(Number(seed)) >>> 0;
    return () => {
        a = (a + 0x6D2B79F5) >>> 0;
        let t = a;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// Least-squares polynomial fit, highest power first, like numpy.polyfit:
// scaled Vandermonde matrix solved by a one-sided Jacobi SVD, which also
// gives numpy's minimum-norm answer when there are fewer points than terms.
function polyfit(xs, ys, deg) {
    const m = xs.length, n = deg + 1;
    const A = xs.map(x => Array.from({ length: n }, (_, j) => x ** (deg - j)));
    const scale = Array.from({ length: n }, (_, j) => Math.hypot(...A.map(r => r[j])) || 1);
    for (const row of A) for (let j = 0; j < n; j++) row[j] /= scale[j];
    const V = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => +(i === j)));

    for (let sweep = 0; sweep < 60; sweep++) {
        let rotated = false;
        for (let p = 0; p < n - 1; p++) {
            for (let q = p + 1; q < n; q++) {
                let alpha = 0, beta = 0, gamma = 0;
                for (const r of A) { alpha += r[p] * r[p]; beta += r[q] * r[q]; gamma += r[p] * r[q]; }
                if (Math.abs(gamma) <= 1e-15 * Math.sqrt(alpha * beta)) continue;
                rotated = true;
                const zeta = (beta - alpha) / (2 * gamma);
                const t = (zeta >= 0 ? 1 : -1) / (Math.abs(zeta) + Math.sqrt(1 + zeta * zeta));
                const c = 1 / Math.sqrt(1 + t * t), s = c * t;
                for (const M of [A, V]) {
                    for (const r of M) {
                        const rp = r[p], rq = r[q];
                        r[p] = c * rp - s * rq;
                        r[q] = s * rp + c * rq;
                    }
                }
            }
        }
        if (!rotated) break;
    }

    const sv = Array.from({ length: n }, (_, j) => Math.hypot(...A.map(r => r[j])));
    const cutoff = m * Number.EPSILON * Math.max(...sv);
    const coeffs = new Array(n).fill(0);
    for (let j = 0; j < n; j++) {
        if (!(sv[j] > cutoff)) continue;
        let ub = 0;
        for (let i = 0; i < m; i++) ub += A[i][j] * ys[i];
        const w = ub / (sv[j] * sv[j]);
        for (let k = 0; k < n; k++) coeffs[k] += V[k][j] * w;
    }
    return coeffs.map((c, k) => c / scale[k]);
}

const polyval = (coeffs, x) => coeffs.reduce((acc, c) => acc * x + c, 0);

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

class Envelope {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }

    constructor(data = null, {
        autosort = true, polyFit = false, curves = null, minEnv = null, maxEnv = null,
        boundsNormalizedX = true, boundsSubdivisions = null, jitter = null,
        jitterMode = "value", jitterClip = true, jitterNormalizedX = true, seed = null,
    } = {}) {
        this.poly_fits = {};
        this.coefficients = {};
        this.curves = [];       // per-segment curve shapes (points.length - 1)
        this.points = [];       // normalized [x, y] breakpoints
        this.x_range = null;
        this.y_range = null;
        this.reducedEnv = null; // set by reduceEnvPoints()
        if (data === null || data === undefined) return;

        const mods = { minEnv, maxEnv, boundsNormalizedX, boundsSubdivisions,
                       jitter, jitterMode, jitterClip, jitterNormalizedX, seed };
        const env = Envelope._is_pair_list(data)
            ? Envelope.from_pairs(data, { autosort, curves, ...mods })
            : Envelope.from_values(data, { curves, ...mods });
        Object.assign(this, {
            points: env.points, x_range: env.x_range, y_range: env.y_range,
            curves: env.curves, poly_fits: env.poly_fits, coefficients: env.coefficients,
        });
        if (polyFit) this.recalculatePolynomials();
    }

    // -------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------

    static _is_pair_list(obj) {
        return Array.isArray(obj) && obj.length > 0 && obj.every(p =>
            Array.isArray(p) && (p.length === 2 || (p.length === 3 && Envelope._looks_like_curve(p[2]))));
    }

    static _looks_like_curve(c) {
        return c === null || c === undefined || typeof c === "string" || isNumber(c);
    }

    // -------------------------------------------------------------
    // Curve helpers
    // -------------------------------------------------------------

    /** Validate a curve spec; return a name from CURVE_NAMES or a non-zero number. */
    static _check_curve(curve) {
        if (curve === null || curve === undefined) return "linear";
        if (typeof curve === "string") {
            const key = curve.trim().toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
            if (Object.hasOwn(Envelope._CURVE_ALIASES, key)) return Envelope._CURVE_ALIASES[key];
            throw new Error(`Envelope: unknown curve '${curve}'. Use one of ${JSON.stringify(Envelope.CURVE_NAMES)} or a number.`);
        }
        if (isNumber(curve)) {
            if (!Number.isFinite(curve) || Math.abs(curve) > Envelope._MAX_CURVATURE) {
                throw new Error(`Envelope: numeric curve must be finite with |c| <= ${Envelope._MAX_CURVATURE}, got ${curve}`);
            }
            return Math.abs(curve) < 1e-9 ? "linear" : curve;
        }
        throw new Error(`Envelope: invalid curve spec ${curve}`);
    }

    /** Map linear progress t in [0,1] to curved progress in [0,1]. */
    static _curve_warp(t, curve) {
        if (t <= 0) return 0;
        if (t >= 1) return 1;
        switch (curve) {
            case "linear":    return t;
            case "step":      return 0;
            case "easeIn":    return t * t;
            case "easeOut":   return 1 - (1 - t) ** 2;
            case "easeInOut": return t * t * (3 - 2 * t);
            case "smooth":    return 0.5 * (1 - Math.cos(Math.PI * t));
        }
        const c = curve === "exp" ? Envelope._EXP_STRENGTH
                : curve === "log" ? -Envelope._EXP_STRENGTH
                : Number(curve);
        return Math.expm1(c * t) / Math.expm1(c);
    }

    /** Canonical per-segment curve list of length nPoints - 1. */
    _normalise_curves(curves, nPoints) {
        const nSeg = Math.max(0, nPoints - 1);
        if (curves === null || curves === undefined) return new Array(nSeg).fill("linear");
        if (curves.length !== nSeg && curves.length !== nPoints) {
            throw new Error(`Envelope: expected ${nSeg} curves (one per segment), got ${curves.length}`);
        }
        return curves.slice(0, nSeg).map(c => Envelope._check_curve(c));
    }

    /** Stored curves padded / trimmed to nPoints - 1 entries. */
    _curves_for(nPoints) {
        const nSeg = Math.max(0, nPoints - 1);
        const stored = (this.curves || []).slice(0, nSeg);
        while (stored.length < nSeg) stored.push("linear");
        return stored;
    }

    /** Replace all segment curves (one per segment), or null to reset to linear. */
    setCurves(curves) {
        this.curves = this._normalise_curves(curves, this.points.length);
        return this;
    }

    /** Set the curve of one segment (0 = between the first two points). */
    setCurve(segmentIndex, curve) {
        const nSeg = this.points.length - 1;
        if (!(segmentIndex >= 0 && segmentIndex < nSeg)) {
            throw new RangeError(`Envelope.setCurve: segment ${segmentIndex} out of range (0..${nSeg - 1})`);
        }
        const curves = this._curves_for(this.points.length);
        curves[segmentIndex] = Envelope._check_curve(curve);
        this.curves = curves;
        return this;
    }

    getCurves() {
        return this._curves_for(this.points.length);
    }

    hasCurves() {
        return this.getCurves().some(c => c !== "linear");
    }

    static _normalize_xy(xs, ys) {
        const xMin = Math.min(...xs), xMax = Math.max(...xs);
        const yMin = Math.min(...ys), yMax = Math.max(...ys);
        const xSpan = xMax !== xMin ? xMax - xMin : 1;
        const ySpan = yMax !== yMin ? yMax - yMin : 1;
        const norm = xs.map((x, i) => [(x - xMin) / xSpan, (ys[i] - yMin) / ySpan]);
        return [norm, [xMin, xMax], [yMin, yMax]];
    }

    // -------------------------------------------------------------
    // Constructors
    // -------------------------------------------------------------

    /** pairs: [[x, y], ...] or [[x, y, curve], ...]. `curves` gives one curve per
        segment instead (not both). Modifiers: see withBounds() / withJitter(). */
    static from_pairs(pairs, { autosort = true, curves = null, ...mods } = {}) {
        if (!Envelope._is_pair_list(pairs)) {
            throw new Error("Envelope.from_pairs: input must be [[x,y],...] or [[x,y,curve],...].");
        }
        const n = pairs.length;
        const inline = pairs.some(p => p.length === 3);
        if (inline && curves !== null) {
            throw new Error("Envelope.from_pairs: give curves either inline ([x,y,curve]) or via curves=, not both.");
        }
        // a curve belongs to the breakpoint its segment starts at,
        // so it travels with that point when sorting
        let pointCurves;
        if (inline) pointCurves = pairs.map(p => (p.length === 3 ? p[2] : null));
        else if (curves !== null) pointCurves = new Envelope()._normalise_curves(curves, n).concat([null]);
        else pointCurves = new Array(n).fill(null);

        let order = pairs.map((_, i) => i);
        if (autosort) order = order.sort((a, b) => pairs[a][0] - pairs[b][0] || a - b);

        const xs = order.map(i => Number(pairs[i][0]));
        const ys = order.map(i => Number(pairs[i][1]));
        const sortedCurves = order.map(i => pointCurves[i]).slice(0, Math.max(0, n - 1));
        const [norm, xr, yr] = Envelope._normalize_xy(xs, ys);

        const env = new Envelope();
        env.points = norm;
        env.x_range = xr;
        env.y_range = yr;
        env.curves = sortedCurves.map(c => Envelope._check_curve(c));
        return Envelope._apply_modifiers(env, mods);
    }

    static from_values(values, { curves = null, ...mods } = {}) {
        if (!Array.isArray(values)) throw new Error("Envelope.from_values: expected list of numbers.");
        if (!values.length) throw new Error("Envelope.from_values: cannot build from empty list.");
        return Envelope.from_pairs(values.map((v, i) => [i, v]), { curves, ...mods });
    }

    /** Return f(phaseInCycles) -> value in [-1, 1]. */
    static _periodic_shape(shape) {
        if (typeof shape === "function") return shape;
        const fns = {
            sine:     p => Math.sin(2 * Math.PI * p),
            cosine:   p => Math.cos(2 * Math.PI * p),
            triangle: p => 1 - 4 * Math.abs(mod(p + 0.25, 1) - 0.5),
            saw:      p => 2 * mod(p, 1) - 1,
            saw_down: p => 1 - 2 * mod(p, 1),
            square:   p => (mod(p, 1) < 0.5 ? 1 : -1),
        };
        const aliases = { sin: "sine", cos: "cosine", tri: "triangle", sawtooth: "saw", ramp: "saw",
                          rampup: "saw", rampdown: "saw_down", sawdown: "saw_down" };
        let key = String(shape).trim().toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
        key = aliases[key] || key;
        if (!Object.hasOwn(fns, key)) {
            throw new Error(`Envelope.periodic: unknown shape '${shape}'. Use one of ${JSON.stringify(Object.keys(fns).sort())} or a function f(phaseInCycles) -> [-1, 1].`);
        }
        return fns[key];
    }

    /**
     * Envelope from a periodic function.
     *
     * periods    : number of cycles; may be fractional (7.3)
     * resolution : breakpoints per cycle
     * shape      : 'sine', 'cosine', 'triangle', 'saw', 'saw_down', 'square' or f(phase) -> [-1, 1]
     * phase      : phase offset in cycles
     * xRange / yRange : domain of the result, [0, 1] each by default
     * includeEnd : put a final breakpoint exactly at the end of the last (partial) cycle
     * + minEnv / maxEnv / jitter modifiers (see withBounds / withJitter)
     */
    static periodic(periods = 1, resolution = 16, {
        shape = "sine", phase = 0, xRange = [0, 1], yRange = [0, 1], includeEnd = true, ...mods
    } = {}) {
        periods = Number(periods);
        if (!Number.isFinite(periods) || periods <= 0) throw new Error("Envelope.periodic: periods must be > 0");
        resolution = Math.trunc(resolution);
        if (resolution < 1) throw new Error("Envelope.periodic: resolution must be >= 1");
        for (const [name, rng] of [["xRange", xRange], ["yRange", yRange]]) {
            if (!rng || rng.length !== 2) {
                throw new Error(`Envelope.periodic: ${name} must be a [min, max] pair, got ${JSON.stringify(rng)}`);
            }
        }
        const f = Envelope._periodic_shape(shape);
        const nGrid = Math.floor(periods * resolution + 1e-9);
        const cycles = Array.from({ length: nGrid + 1 }, (_, k) => k / resolution);
        if (includeEnd && periods - cycles[cycles.length - 1] > 1e-9) cycles.push(periods);
        if (cycles.length < 2) cycles.push(periods);   // at least a start and an end point

        const env = new Envelope();
        env.points = cycles.map(c => [c / periods, 0.5 + 0.5 * clip(f(c + phase), -1, 1)]);
        env.x_range = [Number(xRange[0]), Number(xRange[1])];
        env.y_range = [Number(yRange[0]), Number(yRange[1])];
        if (typeof shape === "string" && shape.trim().toLowerCase() === "square") {
            env.curves = new Array(env.points.length - 1).fill("step");
        }
        return Envelope._apply_modifiers(env, mods);
    }

    /** Shared tail of all constructors: moving bounds, then jitter. */
    static _apply_modifiers(env, {
        minEnv = null, maxEnv = null, boundsNormalizedX = true, boundsSubdivisions = null,
        jitter = null, jitterMode = "value", jitterClip = true, jitterNormalizedX = true, seed = null,
    } = {}) {
        if (minEnv !== null || maxEnv !== null) {
            env = env.withBounds(minEnv, maxEnv, { normalizedX: boundsNormalizedX, subdivisions: boundsSubdivisions });
        }
        if (jitter !== null) {
            env = env.withJitter(jitter, { mode: jitterMode, clip: jitterClip, normalizedX: jitterNormalizedX, seed });
        }
        return env;
    }

    rescale(newXRange = null, newYRange = null, inplace = false) {
        if (!this.points.length) throw new Error("Envelope.rescale: empty envelope");
        const target = inplace ? this : new Envelope();
        target.points = this.points.map(p => p.slice());
        target.x_range = newXRange !== null ? [newXRange[0], newXRange[1]] : this.x_range;
        target.y_range = newYRange !== null ? [newYRange[0], newYRange[1]] : this.y_range;
        target.poly_fits = { ...this.poly_fits };
        target.coefficients = { ...this.coefficients };
        target.curves = this._curves_for(this.points.length);
        return target;
    }

    // -------------------------------------------------------------
    // Bounds (moving minimum / maximum), curves, jitter
    // -------------------------------------------------------------

    static _as_bound(b) {
        if (b === null || b === undefined || b instanceof Envelope) return b ?? null;
        if (isNumber(b)) return b;
        if (Array.isArray(b)) return new Envelope(b);
        throw new Error(`Envelope.withBounds: cannot use ${b} as a bound`);
    }

    /** Refit polynomials on `out`, then return it, or move its state into this. */
    _finish_modification(out, overwriteOriginal) {
        out.recalculatePolynomials();
        if (!overwriteOriginal) return out;
        for (const k of ["points", "x_range", "y_range", "curves", "poly_fits", "coefficients"]) this[k] = out[k];
        this.reducedEnv = null;   // was derived from the old points
        return this;
    }

    /**
     * New envelope whose minimum / maximum are envelopes themselves:
     *     out(x) = floor(x) + shape(x) * (ceiling(x) - floor(x))
     *
     * minEnv / maxEnv : Envelope, array (read as new Envelope(array)), number,
     *                   or null (keep this envelope's own y_range bound)
     * normalizedX     : stretch the bounds over this envelope's x span (default)
     *                   or place them by their own x_range in these x units
     * subdivisions    : extra points per segment; default 8 with moving bounds or
     *                   curves, 0 otherwise (exact)
     * The result has linear segments and no curves.
     */
    withBounds(minEnv = null, maxEnv = null, { normalizedX = true, subdivisions = null, overwriteOriginal = false } = {}) {
        if (!this.points.length) throw new Error("Envelope.withBounds: empty envelope");
        const lo = Envelope._as_bound(minEnv);
        const hi = Envelope._as_bound(maxEnv);
        const [xMin, xMax] = this.x_range;
        const xSpan = (xMax - xMin) || 1;
        const [yMin, yMax] = this.y_range;

        const boundAt = (b, dflt, xn) => {
            if (b === null) return dflt;
            if (isNumber(b)) return b;
            return normalizedX ? b.getValue(xn, true, false) : b.getValue(xMin + xn * xSpan, false, false);
        };

        // breakpoints: this envelope's own plus those of the bounds
        const xsSet = new Set(this.points.map(([x]) => roundTo(x, 12)));
        let moving = false;
        for (const b of [lo, hi]) {
            if (!(b instanceof Envelope)) continue;
            moving = true;
            for (const [bx] of b.points) {
                const xn = normalizedX ? bx : this._x_to_norm(b._x_from_norm(bx), false);
                if (xn >= 0 && xn <= 1) xsSet.add(roundTo(xn, 12));
            }
        }
        xsSet.add(0).add(1);
        let xs = [...xsSet].sort((a, b) => a - b);

        if (subdivisions === null) subdivisions = moving || this.hasCurves() ? 8 : 0;
        subdivisions = Math.max(0, Math.trunc(subdivisions));
        if (subdivisions) {
            const dense = [];
            for (let i = 0; i < xs.length - 1; i++) {
                for (let j = 0; j <= subdivisions; j++) dense.push(xs[i] + (xs[i + 1] - xs[i]) * j / (subdivisions + 1));
            }
            dense.push(xs[xs.length - 1]);
            xs = dense;
        }

        const pairs = xs.map(xn => {
            const shape = this.getValue(xn, true, true);
            const floor = boundAt(lo, yMin, xn);
            const ceil = boundAt(hi, yMax, xn);
            return [xMin + xn * xSpan, floor + shape * (ceil - floor)];
        });
        if (pairs.length === 1) pairs.push([xMax, pairs[0][1]]);
        const out = Envelope.from_pairs(pairs);
        out.x_range = [xMin, xMax];
        return this._finish_modification(out, overwriteOriginal);
    }

    /** Copy with the given per-segment curves (see setCurves()). */
    /**
     * Retrograde: the envelope played backwards in time (x mirrored).
     * Same x_range and y_range. Curves are mirrored (easeIn <-> easeOut, exp <-> log,
     * a number c -> -c) so every segment keeps its shape.
     * 'step' stays 'step': a step row [a, b, c, d] becomes [d, c, b, a].
     */
    reverse({ overwriteOriginal = false } = {}) {
        if (!this.points.length) throw new Error("Envelope.reverse: empty envelope");
        const MIRROR = { easeIn: "easeOut", easeOut: "easeIn", exp: "log", log: "exp" };
        const [pts, curves] = this._sorted_points_and_curves();
        const out = this.rescale();
        out.points = pts.slice().reverse().map(([x, y]) => [1 - x, y]);
        out.curves = curves.slice().reverse().map(c => (typeof c === "number" ? -c : MIRROR[c] ?? c));
        return this._finish_modification(out, overwriteOriginal);
    }

    /**
     * Inversion: every y mirrored around `axis` (y' = 2 * axis - y).
     * axis : null     -> the first breakpoint's value (serial row inversion:
     *                    the row keeps its first note, every interval flips)
     *        "center" -> the middle of the y range (the range stays the same)
     *        a number -> mirror around that value (in y units)
     * Curves stay as they are: a vertical mirror keeps each segment's shape.
     */
    inverse(axis = null, { overwriteOriginal = false } = {}) {
        if (!this.points.length) throw new Error("Envelope.inverse: empty envelope");
        const [yMin, yMax] = this.y_range;
        if (axis === null || axis === undefined) {
            axis = this._y_from_norm(this._sorted_points_and_curves()[0][0][1], false);
        } else if (typeof axis === "string" && ["center", "centre"].includes(axis.toLowerCase())) {
            axis = (yMin + yMax) / 2;
        } else if (isNumber(axis)) {
            axis = Number(axis);
        } else {
            throw new Error(`Envelope.inverse: axis must be null, "center" or a number, got ${axis}`);
        }
        const out = this.rescale(null, [2 * axis - yMax, 2 * axis - yMin]);
        out.points = this.points.map(([x, y]) => [x, 1 - y]);
        return this._finish_modification(out, overwriteOriginal);
    }

    withCurves(curves, { overwriteOriginal = false } = {}) {
        const out = this.rescale();
        out.setCurves(curves);
        return this._finish_modification(out, overwriteOriginal);
    }

    /**
     * New envelope whose breakpoint y-values deviate randomly by a percentage.
     *
     * jitter      : fraction (0.1 = up to +-10%), or an Envelope / array varying it along x
     * mode        : 'value' — percentage of the point's own value (0 never moves)
     *               'range' — percentage of the whole y span
     * clip        : keep the current y_range and clip into it (default), or refit it
     * normalizedX : stretch a jitter envelope over this envelope's x span (default)
     * seed        : reproducible result (JavaScript-only sequence)
     */
    withJitter(jitter, { mode = "value", clip: clipToRange = true, normalizedX = true, seed = null, overwriteOriginal = false } = {}) {
        if (!this.points.length) throw new Error("Envelope.withJitter: empty envelope");
        if (mode !== "value" && mode !== "range") {
            throw new Error(`Envelope.withJitter: unknown mode '${mode}' (use 'value' or 'range')`);
        }
        const j = Envelope._as_bound(jitter);
        if (j === null) return this._finish_modification(this.rescale(), overwriteOriginal);

        const [xMin, xMax] = this.x_range;
        const xSpan = (xMax - xMin) || 1;
        const [yMin, yMax] = this.y_range;
        const ySpan = yMax - yMin;
        const random = makeRandom(seed);

        const absX = [], absY = [];
        for (const [xn, yn] of this.points) {
            let amount = isNumber(j) ? j
                : normalizedX ? j.getValue(xn, true, false)
                : j.getValue(xMin + xn * xSpan, false, false);
            amount = Math.abs(amount);
            const r = random() * 2 - 1;
            const y = yMin + yn * ySpan;
            absX.push(xMin + xn * xSpan);
            absY.push(mode === "value" ? y * (1 + amount * r) : y + amount * ySpan * r);
        }

        if (!clipToRange) {
            const out = Envelope.from_pairs(absX.map((x, i) => [x, absY[i]]),
                                            { autosort: false, curves: this._curves_for(this.points.length) });
            out.x_range = [xMin, xMax];
            return this._finish_modification(out, overwriteOriginal);
        }
        const lo = Math.min(yMin, yMax), hi = Math.max(yMin, yMax);
        const out = new Envelope();
        out.points = this.points.map(([xn], i) => [xn, ySpan ? clip((clip(absY[i], lo, hi) - yMin) / ySpan, 0, 1) : 0]);
        out.x_range = this.x_range;
        out.y_range = this.y_range;
        out.curves = this._curves_for(this.points.length);
        return this._finish_modification(out, overwriteOriginal);
    }

    _x_from_norm(xn) {
        const [xMin, xMax] = this.x_range;
        return xMin + xn * ((xMax - xMin) || 1);
    }

    // -------------------------------------------------------------
    // Polynomial fitting
    // -------------------------------------------------------------

    /** (Re)fit polynomials of degree 1..5 to the current breakpoints, in place. */
    recalculatePolynomials() {
        this.poly_fits = {};
        this.coefficients = {};
        if (this.points.length < 2) return this;
        const xs = this.points.map(p => p[0]);
        const ys = this.points.map(p => p[1]);
        for (let deg = 1; deg <= 5; deg++) {
            const coeffs = polyfit(xs, ys, deg);
            this.coefficients[deg] = coeffs;
            this.poly_fits[deg] = x => clip(polyval(coeffs, x), 0, 1);
        }
        return this;
    }

    // -------------------------------------------------------------
    // Data reduction
    // -------------------------------------------------------------

    /** `resolution` normalized y samples from x = 0 to x = 1 (both included). */
    _internalRenderNorm(resolution = 20) {
        const n = Math.max(2, Math.trunc(resolution));
        return Array.from({ length: n }, (_, i) => this.getValue(i / (n - 1), true, true));
    }

    /**
     * Simplify the envelope to its two endpoints plus its `numMinima` lowest
     * local minima and `numMaxima` highest local maxima, found on the shape
     * sampled at `resolution` points. The result keeps this envelope's x/y
     * units and is stored in (and returned as) this.reducedEnv.
     */
    reduceEnvPoints(numMinima = 3, numMaxima = 3, resolution = 20) {
        const ys = this._internalRenderNorm(resolution);
        const n = ys.length;
        const inner = Array.from({ length: n - 2 }, (_, k) => k + 1);
        const minima = inner.filter(i => ys[i - 1] > ys[i] && ys[i] <= ys[i + 1]);
        const maxima = inner.filter(i => ys[i - 1] < ys[i] && ys[i] >= ys[i + 1]);
        const keep = new Set([0, n - 1]);
        minima.sort((a, b) => ys[a] - ys[b] || a - b).slice(0, Math.max(0, numMinima)).forEach(i => keep.add(i));
        maxima.sort((a, b) => ys[b] - ys[a] || a - b).slice(0, Math.max(0, numMaxima)).forEach(i => keep.add(i));
        this.reducedEnv = Envelope.from_pairs(
            [...keep].sort((a, b) => a - b).map(i => [this._x_from_norm(i / (n - 1)), this._y_from_norm(ys[i], false)]));
        return this.reducedEnv;
    }

    // -------------------------------------------------------------
    // Value lookup
    // -------------------------------------------------------------

    getValue(xPos, normalizedX = false, normalizedY = false, interpolateOutsideOfRange = true, polyDegree = 0) {
        if (!this.points.length) throw new Error("Envelope.getValue: empty envelope");
        const xNorm = this._x_to_norm(xPos, normalizedX);
        if (polyDegree && polyDegree > 0) {
            if (!Object.keys(this.poly_fits).length) throw new Error("Envelope.getValue: no polynomial fits available");
            if (!Object.hasOwn(this.poly_fits, polyDegree)) throw new Error(`Envelope.getValue: polynomial degree ${polyDegree} not fitted`);
            return this._y_from_norm(this.poly_fits[polyDegree](xNorm), normalizedY);
        }
        const [pts, curves] = this._sorted_points_and_curves();
        return this._y_from_norm(this._y_at_x_norm(xNorm, pts, interpolateOutsideOfRange, curves), normalizedY);
    }

    /** Quantise the envelope onto grids (anything with sorted() and quantise()):
        returns [x, y] pairs wherever the quantised y changes along xGrid. */
    mapToGrid(xGrid, yGrid) {
        const xList = xGrid.sorted();
        if (!xList.length) return [];
        const xMin = xList[0], xMax = xList[xList.length - 1];
        const xRange = xMax - xMin;
        const vals = [[xMin, yGrid.quantise(this.getValue(0, true))]];
        let lastY = vals[0][1];
        for (const x of xList.slice(1)) {
            const xNorm = xRange ? (x - xMin) / xRange : 0;
            const yCandidate = yGrid.quantise(this.getValue(xNorm, true));
            if (yCandidate !== lastY) {
                vals.push([xNorm * xRange + xMin, yCandidate]);
                lastY = yCandidate;
            }
        }
        return vals;
    }

    // ---------------- helpers ----------------

    /** Points sorted by x, each segment's curve following its start point. */
    _sorted_points_and_curves() {
        const n = this.points.length;
        const stored = this._curves_for(n);
        const order = this.points.map((_, i) => i).sort((a, b) => this.points[a][0] - this.points[b][0] || a - b);
        const pts = order.map(i => this.points[i]);
        const curves = order.slice(0, -1).map(i => (i < n - 1 ? stored[i] : "linear"));
        return [pts, curves];
    }

    _x_to_norm(xPos, normalizedX) {
        if (normalizedX) return Number(xPos);
        if (this.x_range === null) throw new Error("Envelope.getValue: missing x_range");
        const [xMin, xMax] = this.x_range;
        return (Number(xPos) - xMin) / ((xMax - xMin) || 1);
    }

    _y_from_norm(yNorm, normalizedY) {
        if (normalizedY) return Number(yNorm);
        if (this.y_range === null) throw new Error("Envelope.getValue: missing y_range");
        const [yMin, yMax] = this.y_range;
        return yMin + yNorm * (yMax - yMin);
    }

    _y_at_x_norm(xNorm, pts, allowExtrap, curves = null) {
        const n = pts.length;
        if (curves === null) curves = new Array(Math.max(0, n - 1)).fill("linear");
        if (n === 1) return pts[0][1];
        const [x0, y0] = pts[0];
        const [xN, yN] = pts[n - 1];
        if (xNorm <= x0) return allowExtrap ? this._y_extrap_left(xNorm, pts, curves) : y0;
        if (xNorm >= xN) return allowExtrap ? this._y_extrap_right(xNorm, pts, curves) : yN;
        return this._y_interp_inside(xNorm, pts, curves);
    }

    _y_interp_inside(x, pts, curves) {
        for (let i = 0; i < pts.length - 1; i++) {
            const [xa, ya] = pts[i], [xb, yb] = pts[i + 1];
            if (xa <= x && x <= xb) {
                const curve = curves ? curves[i] : "linear";
                return curve === "linear" ? Envelope._lerp(x, xa, ya, xb, yb) : Envelope._curved(x, xa, ya, xb, yb, curve);
            }
        }
        return pts[pts.length - 1][1];
    }

    // Outside the breakpoints the straight line through the edge segment
    // continues; a 'step' edge segment holds its edge value instead.
    _y_extrap_left(x, pts, curves) {
        const [[x0, y0], [x1, y1]] = pts;
        return curves && curves[0] === "step" ? y0 : Envelope._lerp(x, x0, y0, x1, y1);
    }

    _y_extrap_right(x, pts, curves) {
        const [x1, y1] = pts[pts.length - 2], [x2, y2] = pts[pts.length - 1];
        return curves && curves[curves.length - 1] === "step" ? y2 : Envelope._lerp(x, x1, y1, x2, y2);
    }

    static _curved(x, xa, ya, xb, yb, curve) {
        if (xb === xa) return ya;
        return ya + Envelope._curve_warp((x - xa) / (xb - xa), curve) * (yb - ya);
    }

    static _lerp(x, xa, ya, xb, yb) {
        if (xb === xa) return ya;
        return ya + (x - xa) / (xb - xa) * (yb - ya);
    }

    // -------------------------------------------------------------
    // Display
    // -------------------------------------------------------------

    /** ASCII rendering with 'O' characters; printed (Max console / Node) and returned. */
    displayAscii(maxWidth = 60, maxHeight = 20, useNormalized = false) {
        if (!this.points.length) throw new Error("Envelope.displayAscii: empty envelope");
        const width = Math.max(2, Math.trunc(maxWidth));
        const height = Math.max(2, Math.trunc(maxHeight));
        const rows = Array.from({ length: width }, (_, col) =>
            Math.round((1 - clip(this.getValue(col / (width - 1), true, true), 0, 1)) * (height - 1)));

        // connect each column to the previous one so steep segments stay continuous
        const grid = Array.from({ length: height }, () => new Array(width).fill(" "));
        grid[rows[0]][0] = "O";
        for (let col = 1; col < width; col++) {
            const lo = Math.min(rows[col - 1], rows[col]), hi = Math.max(rows[col - 1], rows[col]);
            for (let r = lo; r <= hi; r++) grid[r][col] = "O";
        }

        const g = v => String(Number(v.toPrecision(6)));
        let xLabel, yTop, yBottom;
        if (useNormalized || this.x_range === null || this.y_range === null) {
            [xLabel, yTop, yBottom] = ["x: [0, 1] (normalized)", "1", "0"];
        } else {
            xLabel = `x: [${g(this.x_range[0])}, ${g(this.x_range[1])}]`;
            [yTop, yBottom] = [g(this.y_range[1]), g(this.y_range[0])];
        }
        const w = Math.max(yTop.length, yBottom.length);
        const lines = grid.map((row, r) =>
            `${(r === 0 ? yTop : r === height - 1 ? yBottom : "").padStart(w)} | ${row.join("")}`);
        lines.push(" ".repeat(w + 1) + "+" + "-".repeat(width + 1));
        lines.push(" ".repeat(w + 3) + xLabel);
        const art = lines.join("\n");
        print(art);
        return art;
    }

    // ------------------------------------------------------------------
    // Statistics on the breakpoint y-values
    // ------------------------------------------------------------------

    /** Breakpoint y-values, normalized or in y_range units (same mapping as getValue). */
    _get_y_values(normalized = false) {
        if (!this.points.length) throw new Error("Envelope._get_y_values: envelope has no points");
        return this.points.map(([, y]) => this._y_from_norm(y, normalized));
    }

    _counts(normalized, rounding) {
        const counts = new Map();
        for (const y of this._get_y_values(normalized)) {
            const k = roundTo(y, rounding);
            counts.set(k, (counts.get(k) || 0) + 1);
        }
        return counts;
    }

    most_common_y(normalized = false, rounding = 6) {
        let best = null, bestCount = -1;
        for (const [k, c] of this._counts(normalized, rounding)) if (c > bestCount) [best, bestCount] = [k, c];
        return best;
    }

    least_common_y(normalized = false, rounding = 6) {
        let best = null, bestCount = Infinity;
        for (const [k, c] of this._counts(normalized, rounding)) if (c <= bestCount) [best, bestCount] = [k, c];
        return best;
    }

    /** Map {yValue -> count}, sorted by value (default) or by count ('count', most frequent first). */
    histogram(normalized = false, rounding = 6, sortBy = "value") {
        const items = [...this._counts(normalized, rounding)];
        if (sortBy === "value") items.sort((a, b) => a[0] - b[0]);
        else if (sortBy === "count") items.sort((a, b) => b[1] - a[1]);
        else throw new Error(`Envelope.histogram: unknown sortBy '${sortBy}' (use 'value' or 'count')`);
        return new Map(items);
    }

    mean_y(normalized = false) {
        const ys = this._get_y_values(normalized);
        return ys.reduce((a, b) => a + b, 0) / ys.length;
    }

    median_y(normalized = false) {
        const ys = this._get_y_values(normalized).sort((a, b) => a - b);
        const m = ys.length >> 1;
        return ys.length % 2 ? ys[m] : (ys[m - 1] + ys[m]) / 2;
    }

    std_y(normalized = false, ddof = 0) {
        const ys = this._get_y_values(normalized);
        const mean = ys.reduce((a, b) => a + b, 0) / ys.length;
        return Math.sqrt(ys.reduce((a, y) => a + (y - mean) ** 2, 0) / (ys.length - ddof));
    }

    // -------------------------------------------------------------
    toString() {
        return `Envelope\n   pointsNorm=${JSON.stringify(this.points)}\n   x_range=${JSON.stringify(this.x_range)}, ` +
               `y_range=${JSON.stringify(this.y_range)}\n   curves=${JSON.stringify(this.getCurves())}\n   ` +
               `coefficients=${JSON.stringify(this.coefficients)})`;
    }
}

Envelope.CURVE_NAMES = ["linear", "step", "exp", "log", "easeIn", "easeOut", "easeInOut", "smooth"];
Envelope._CURVE_ALIASES = {
    lin: "linear", linear: "linear",
    step: "step", hold: "step",
    exp: "exp", exponential: "exp",
    log: "log", logarithmic: "log",
    easein: "easeIn", ease_in: "easeIn", in: "easeIn",
    easeout: "easeOut", ease_out: "easeOut", out: "easeOut",
    easeinout: "easeInOut", ease_in_out: "easeInOut", inout: "easeInOut",
    smooth: "smooth", sine: "smooth", cosine: "smooth",
};
Envelope._EXP_STRENGTH = 5;      // curvature used by 'exp' / 'log'
Envelope._MAX_CURVATURE = 100;

for (const C of [Envelope]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") exports.Envelope = Envelope;
