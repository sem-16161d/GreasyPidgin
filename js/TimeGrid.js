/*
TimeGrid.js — JavaScript port of GreasyPidgin/TimeGrid.py

A TimeGrid is a Grid of time positions in seconds with tempo (bpm,
ticksPerBeat), a span (startTimeSec..endTimeSec) and optional layers.
RQQ is a hierarchical rhythm notation; Rest (or R) marks silent parts.

    Max:   var T = require("TimeGrid");   T.TimeGrid.fromEuclidean(5, 8, 0, { durationBeats: 4, bpm: 120 })
    Node:  const { TimeGrid, RQQ, R } = require("./TimeGrid");

    TimeGrid.fromRQQ(new RQQ(4, [1, 1, R(1), 2]), { bpm: 90 }).sorted();   // [0, 0.667, 2]

Differences from the Python version: keyword arguments become an options
object; Rest is an object (R(1) / new Rest(1)), not a float subclass; no
fromMidiFile() / toMidi(), toEvents() gives the onsets as notes instead.
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { Grid } = load("Grid");

const roundTo = (x, d) => Number(Number(x).toFixed(d));
const beatToSec = (beat, bpm = 60) => Number(beat) * 60 / Number(bpm);
const secToBeat = (sec, bpm = 60) => Number(sec) * Number(bpm) / 60;

/** Euclidean rhythm (Bjorklund): `pulses` onsets spread evenly over `steps`. */
function bjorklund(pulses, steps) {
    pulses = Math.max(0, Math.min(Math.trunc(pulses), steps));
    if (pulses === 0 || pulses === steps) return new Array(steps).fill(pulses ? 1 : 0);
    let ones = Array.from({ length: pulses }, () => [1]), zeros = Array.from({ length: steps - pulses }, () => [0]);
    while (zeros.length > 1) {
        const n = Math.min(ones.length, zeros.length);
        const paired = ones.slice(0, n).map((o, i) => o.concat(zeros[i]));
        zeros = ones.length > zeros.length ? ones.slice(n) : zeros.slice(n);
        ones = paired;
    }
    return ones.concat(zeros).flat();
}

const rotate = (pattern, rotation) => {
    const r = pattern.length ? ((rotation % pattern.length) + pattern.length) % pattern.length : 0;
    return pattern.slice(r).concat(pattern.slice(0, r));
};

function subdivisionTimes(startTimeSec, totalSec, subdivisions, bpm, includeEnd = false) {
    const startBeats = secToBeat(startTimeSec, bpm), spanBeats = secToBeat(totalSec, bpm);
    const eps = 1e-9, endSec = startTimeSec + totalSec, seen = new Set();
    for (const sd of subdivisions) {
        for (let i = 0; i <= Math.round(spanBeats * sd); i++) {
            const t = roundTo(beatToSec(startBeats + i / sd, bpm), 8);
            if (startTimeSec - eps <= t && (includeEnd ? t <= endSec + eps : t < endSec - eps)) seen.add(t);
        }
    }
    return [...seen].sort((a, b) => a - b);
}

const totalSecOf = (durationSec, durationBeats, bpm, defaultBeats) =>
    durationSec !== null ? Number(durationSec) : beatToSec(durationBeats !== null ? durationBeats : defaultBeats, bpm);

function leaningWeights(n, leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve) {
    if (Math.abs(leaning) < 1e-9) return new Array(n).fill(1);
    const k = Math.log(leaningMax / leaningMin) * Math.abs(leaning) * leaningIntensity;
    return Array.from({ length: n }, (_, i) => {
        const t = n > 1 ? i / (n - 1) : 0.5;
        const w = leaningCurve === "exponential"
            ? leaningMax * Math.exp(-k * (leaning < 0 ? t : 1 - t))
            : leaning < 0 ? leaningMax + (leaningMin - leaningMax) * t : leaningMin + (leaningMax - leaningMin) * t;
        return Math.max(leaningMin, Math.min(leaningMax, w));
    });
}

/** Keep each candidate with probability base * weight, calibrated to expectedEvents. */
function bernoulliPick(candidates, expectedEvents, weights, leaning, maxRetries = 100) {
    const total = weights.reduce((a, b) => a + b, 0);
    const probs = weights.map(w => Math.min(1, (total ? expectedEvents / total : 0) * w));
    for (let k = 0; k < maxRetries; k++) {
        const events = candidates.filter((_, i) => Math.random() < probs[i]);
        if (events.length) return events;
    }
    return [candidates[leaning <= 0 ? 0 : candidates.length - 1]];
}

// ---------------------------------------------------------------------------
// Rest and RQQ
// ---------------------------------------------------------------------------

/** A duration that takes up time but has no onset. */
class Rest {
    constructor(value) { this.value = Number(value); }
    valueOf() { return this.value; }
    toString() { return `R(${this.value})`; }
}
const R = value => new Rest(value);

function flattenRQQ(r) {
    if (typeof r === "number" || r instanceof Rest) return [r];
    if (Array.isArray(r)) return r.flatMap(flattenRQQ);
    if (r instanceof RQQ) return flattenRQQ(r.rawdividedDurations);
    return [];
}

/**
 * Rhythm Quantisation Quotient: divides durationBeats into proportional parts.
 * A nested RQQ weighs as much as its own duration and keeps its subdivisions.
 *   new RQQ(4, [1, 1, R(1), 2])            quarter, quarter, rest, half
 *   new RQQ(4, [1, new RQQ(1, [1,1,1]), 1, 1])   triplets in beat 2
 */
class RQQ {
    constructor(durationBeats, ratios, { bpm = 60, startOffsetBeats = 0 } = {}) {
        this.durationBeats = Number(durationBeats);
        this.ratios = flattenRQQ(ratios);
        this.bpm = Number(bpm);
        this.startOffsetBeats = Number(startOffsetBeats);
        this._getStartsBeats();
    }

    _divideDurationRaw() {
        const total = this.ratios.reduce((a, r) => a + Number(r), 0);
        this.rawdividedDurations = this.ratios.map(r => {
            const d = Number(r) / total * this.durationBeats;
            return r instanceof Rest ? new Rest(d) : d;
        });
    }

    /** Onsets (beats) of the non-rest parts. */
    _getStartsBeats() {
        this._divideDurationRaw();
        this.startsBeats = [];
        let pos = this.startOffsetBeats;
        for (const d of this.rawdividedDurations) {
            if (!(d instanceof Rest)) this.startsBeats.push(pos);
            pos += Number(d);
        }
    }

    toString() {
        return `RQQ(durationBeats=${this.durationBeats}, subdivisions=[${this.ratios.join(", ")}], startsBeats=${JSON.stringify(this.startsBeats)})`;
    }
}

// ---------------------------------------------------------------------------
// TimeGrid
// ---------------------------------------------------------------------------

class TimeGrid extends Grid {

    /** values: seconds; endTimeSec null = last + last step. */
    constructor(values = null, { startTimeSec = 0, endTimeSec = null, bpm = 60, ticksPerBeat = 480 } = {}) {
        super(values);
        this.bpm = Number(bpm);
        this.ticksPerBeat = Math.trunc(ticksPerBeat);
        this.layers = {};
        this.densityCurve = {};
        this.startTimeSec = Number(startTimeSec);
        this.startTimeBeats = secToBeat(this.startTimeSec, this.bpm);
        const srt = this.sorted();
        if (endTimeSec !== null) this.endTimeSec = Number(endTimeSec);
        else if (srt.length >= 2) this.endTimeSec = 2 * srt[srt.length - 1] - srt[srt.length - 2];
        else this.endTimeSec = srt.length ? srt[0] : 0;
        this.durationSec = this.endTimeSec - this.startTimeSec;
        this.durationBeats = secToBeat(this.durationSec, this.bpm);
        this.endTimeBeats = secToBeat(this.endTimeSec, this.bpm);
    }

    _like(values) {
        return new TimeGrid(values, { startTimeSec: this.startTimeSec, endTimeSec: this.endTimeSec, bpm: this.bpm, ticksPerBeat: this.ticksPerBeat });
    }

    /** numElements random positions as a TimeGrid with the same span and tempo. */
    sample(numElements) { return this._like(super.sample(numElements)); }

    // ------------------------------------------------------------------
    // Constructors
    // ------------------------------------------------------------------

    static series(startTimeSec, stepSec, size, { bpm = 60, ticksPerBeat = 480 } = {}) {
        return new TimeGrid(Grid.series(startTimeSec, stepSec, size), { startTimeSec, endTimeSec: startTimeSec + size * stepSec, bpm, ticksPerBeat });
    }

    static linearInterpolation(startTimeSec, endTimeSec, size, { bpm = 60, ticksPerBeat = 480, decimals = 4, includeEnd = true } = {}) {
        return new TimeGrid(Grid.linearInterpolation(startTimeSec, endTimeSec, size, { decimals, includeEnd }),
                            { startTimeSec, endTimeSec, bpm, ticksPerBeat });
    }

    /** Simultaneous beat subdivisions, e.g. [1, 2, 3]; each one is kept in layers["/ n"]. */
    static fromSubdivisions(subdivisions = null, { bpm = 60, startTimeBeats = 0, durationBeats, ticksPerBeat = 480 } = {}) {
        const startSec = beatToSec(startTimeBeats, bpm);
        const layers = {};
        for (const sd of subdivisions || [1]) {
            layers[`/ ${sd}`] = TimeGrid.series(startSec, beatToSec(1 / sd, bpm), Math.trunc(durationBeats * sd), { bpm, ticksPerBeat });
        }
        const tg = new TimeGrid(Object.values(layers).flatMap(l => [...l]),
                                { startTimeSec: startSec, endTimeSec: beatToSec(startTimeBeats + durationBeats, bpm), bpm, ticksPerBeat });
        tg.layers = layers;
        return tg;
    }

    /** Onsets of an RQQ from startTimeSec (the RQQ is not changed). */
    static fromRQQ(rqq, { startTimeSec = 0, bpm = 60, ticksPerBeat = 480 } = {}) {
        const values = rqq.startsBeats.map(b => roundTo(startTimeSec + beatToSec(b - rqq.startOffsetBeats, bpm), 10));
        return new TimeGrid(values, { startTimeSec, endTimeSec: startTimeSec + beatToSec(rqq.durationBeats, bpm), bpm, ticksPerBeat });
    }

    /**
     * Integer L-System over a palette of RQQs: productionRules [[pred, [succ, ...]], ...],
     * optional window of durationsCutoffBeats from the 'start', 'end' or 'middle'.
     */
    static RQQfromLSystem(rqqs, productionRules, numIterations = 5, {
        axiom = null, startTimeSec = 0, bpm = 60, ticksPerBeat = 480, durationsCutoffBeats = null, cutoffMode = "start",
    } = {}) {
        const { LSystem, ProductionRules, ProductionRule } = load("LSystem");
        const lind = new LSystem(axiom || [0], new ProductionRules(productionRules.map(([p, s]) => new ProductionRule(p, s))));
        lind.iterate(numIterations);
        const sequence = lind.currentGeneration().filter(i => i >= 0 && i < rqqs.length).map(i => rqqs[i]);
        if (!sequence.length) return new TimeGrid([], { startTimeSec, bpm, ticksPerBeat });
        const durationBeats = sequence.reduce((a, r) => a + r.durationBeats, 0);
        const tg = TimeGrid.fromRQQ(new RQQ(durationBeats, sequence), { startTimeSec, bpm, ticksPerBeat });
        if (durationsCutoffBeats === null) return tg;
        const windowSec = beatToSec(durationsCutoffBeats, bpm);
        const spare = Math.max(0, beatToSec(durationBeats, bpm) - windowSec);
        const offset = cutoffMode === "end" ? spare : cutoffMode === "middle" ? spare / 2 : 0;
        const start = startTimeSec + offset;
        return new TimeGrid(tg.sorted().filter(t => start - 1e-9 <= t && t < start + windowSec).map(t => t - offset),
                            { startTimeSec, endTimeSec: startTimeSec + windowSec, bpm, ticksPerBeat });
    }

    /** Euclidean rhythm on `steps` equal steps (duration: durationSec, durationBeats or one beat per step). */
    static fromEuclidean(pulses, steps, rotation = 0, { durationBeats = null, durationSec = null, startTimeSec = 0, bpm = 60, ticksPerBeat = 480 } = {}) {
        if (pulses < 0 || steps <= 0) throw new RangeError(`TimeGrid.fromEuclidean: need steps > 0 and pulses >= 0, got pulses=${pulses}, steps=${steps}`);
        const pattern = rotate(bjorklund(pulses, steps), rotation);
        const total = totalSecOf(durationSec, durationBeats, bpm, steps), step = total / steps;
        return new TimeGrid(pattern.flatMap((v, i) => (v ? [startTimeSec + i * step] : [])),
                            { startTimeSec, endTimeSec: startTimeSec + total, bpm, ticksPerBeat });
    }

    /** Euclidean rhythm on the union of beat subdivisions (default [1, 2, 4], 4 beats). */
    static fromPulsesEuclidean(pulses, subdivisions = null, rotation = 0, { durationBeats = null, durationSec = null, startTimeSec = 0, bpm = 60, ticksPerBeat = 480 } = {}) {
        const total = totalSecOf(durationSec, durationBeats, bpm, 4);
        const times = subdivisionTimes(startTimeSec, total, subdivisions || [1, 2, 4], bpm);
        if (!times.length) return new TimeGrid([], { startTimeSec, bpm, ticksPerBeat });
        const pattern = rotate(bjorklund(pulses, times.length), rotation);
        return new TimeGrid(times.filter((_, i) => pattern[i]), { startTimeSec, endTimeSec: startTimeSec + total, bpm, ticksPerBeat });
    }

    /** fromPulsesEuclidean with pulses = round(densityHz * duration). */
    static fromDensityEuclidean(densityHz = 4, subdivisions = null, rotation = 0, { durationBeats = null, durationSec = null, startTimeSec = 0, bpm = 60, ticksPerBeat = 480 } = {}) {
        const total = totalSecOf(durationSec, durationBeats, bpm, 4);
        return TimeGrid.fromPulsesEuclidean(Math.round(densityHz * total), subdivisions, rotation,
                                            { durationSec: total, startTimeSec, bpm, ticksPerBeat });
    }

    /**
     * Random onsets with expected density densityHz, leaning -1 (dense start) .. 1 (dense end);
     * candidates on beat subdivisions or every millisecond.
     */
    static fromDensity(startTimeSec = 0, durationSec = 4, densityHz = 5, leaning = 0, subdivisions = null, {
        leaningIntensity = 5, bpm = 60, ticksPerBeat = 480, leaningMin = 0.01, leaningMax = 0.99, leaningCurve = "exponential",
    } = {}) {
        const candidates = subdivisions && subdivisions.length
            ? subdivisionTimes(startTimeSec, durationSec, subdivisions, bpm, true)
            : Array.from({ length: Math.trunc(durationSec / 0.001) + 1 }, (_, i) => roundTo(startTimeSec + i * 0.001, 8));
        if (!candidates.length) return new TimeGrid([], { startTimeSec, bpm, ticksPerBeat });
        const weights = leaningWeights(candidates.length, leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve);
        return new TimeGrid(bernoulliPick(candidates, densityHz * durationSec, weights, leaning),
                            { startTimeSec, endTimeSec: startTimeSec + durationSec, bpm, ticksPerBeat });
    }

    /** Probabilistic selection from this grid's positions, same logic as fromDensity. */
    leaningSample(densityHz = 5, leaning = 0, { leaningIntensity = 5, leaningMin = 0.01, leaningMax = 0.99, leaningCurve = "exponential" } = {}) {
        const candidates = this.sorted();
        if (!candidates.length) return this._like([]);
        const weights = leaningWeights(candidates.length, leaning, leaningIntensity, leaningMin, leaningMax, leaningCurve);
        return this._like(bernoulliPick(candidates, densityHz * this.durationSec, weights, leaning));
    }

    // ------------------------------------------------------------------
    // Analysis
    // ------------------------------------------------------------------

    /** Inter-onset intervals; unit 'seconds' | 'beats'. */
    toRelativeTimes(unit = "seconds") {
        const srt = this.sorted();
        const d = srt.slice(1).map((t, i) => t - srt[i]);
        return unit === "beats" || unit === "b" ? d.map(x => secToBeat(x, this.bpm)) : d;
    }

    /** Events per second in a window of lookBackFrame ending at each lookbackInterval step. */
    getDensityCurve(lookbackInterval = 1, lookBackFrame = 1, { lookBackUnit = "sec" } = {}) {
        let intervalSec, frameSec;
        if (["sec", "seconds", "s"].includes(lookBackUnit)) [intervalSec, frameSec] = [lookbackInterval, lookBackFrame];
        else if (["beats", "b"].includes(lookBackUnit)) [intervalSec, frameSec] = [beatToSec(lookbackInterval, this.bpm), beatToSec(lookBackFrame, this.bpm)];
        else throw new Error(`TimeGrid.getDensityCurve: invalid lookBackUnit '${lookBackUnit}'`);
        const points = this.sorted();
        const density = Array.from({ length: Math.ceil(this.durationSec / intervalSec) + 1 }, (_, i) => {
            const end = this.startTimeSec + i * intervalSec;
            const count = points.filter(t => end - frameSec <= t && t <= end).length;
            return frameSec > 0 ? count / frameSec : 0;
        });
        const max = Math.max(...density);
        const result = { density, minDensityHz: Math.min(...density), maxDensityHz: max,
                         relativeMaxPosition: density.indexOf(max) / density.length,
                         meanDensityHz: density.reduce((a, b) => a + b, 0) / density.length };
        this.densityCurve[`frame_${frameSec}_interval_${intervalSec}`] = result;
        return result;
    }

    /** Share of distinct inter-onset patterns (lengths 2..maxLength) that occur more than once, 0..maxVal. */
    getSelfSimilarity(maxVal = 1, maxLength = 8) {
        const iois = this.toRelativeTimes().map(d => roundTo(d, 6));
        const counts = new Map();
        for (let n = 2; n <= Math.min(maxLength, iois.length - 1); n++) {
            for (let i = 0; i + n <= iois.length; i++) {
                const k = iois.slice(i, i + n).join(",");
                counts.set(k, (counts.get(k) || 0) + 1);
            }
        }
        if (!counts.size) return 0;
        return maxVal * [...counts.values()].filter(c => c > 1).length / counts.size;
    }

    /** density (events per beat) and leaning (-1 early .. 1 late) of external times on this grid. */
    analyseExternalStartTimesSec(starts) {
        const grid = this.sorted();
        if (!grid.length || !starts.length) return { density: 0, leaning: 0 };
        const index = new Map(grid.map((t, i) => [t, i]));
        const positions = starts.map(s => (grid.length > 1 ? index.get(this.quantise(s)) / (grid.length - 1) : 0.5));
        return { density: this.durationBeats ? starts.length / this.durationBeats : 0,
                 leaning: 2 * positions.reduce((a, b) => a + b, 0) / positions.length - 1 };
    }

    /** The onsets as notes { startSec, durationSec (smallest IOI), pitch, bend }. */
    toEvents(pitch = 60) {
        const iois = this.toRelativeTimes();
        const dur = iois.length ? Math.min(...iois) : 0.25;
        return this.sorted().map(t => ({ startSec: t, durationSec: dur, pitch, bend: [0, 0] }));
    }

    toString() {
        return `TimeGrid(size=${this.size}, ${this.startTimeSec}s..${this.endTimeSec}s, bpm=${this.bpm}, ` +
               `layers=${JSON.stringify(Object.keys(this.layers))}, sorted=${JSON.stringify(this.sorted())})`;
    }
}

if (typeof exports !== "undefined") Object.assign(exports, { TimeGrid, RQQ, Rest, R, beatToSec, secToBeat, bjorklund });
