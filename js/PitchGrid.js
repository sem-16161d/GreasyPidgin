/*
PitchGrid.js — JavaScript port of GreasyPidgin/PitchGrid.py

A PitchGrid is a Grid of MIDI floats from a TuningSystem within a register.
MIDI floats are the unit everywhere (69 = A4, 60.5 = quarter-tone above C4);
referenceAHz only matters for Hz input / output.

    Max:   var PitchGrid = require("PitchGrid").PitchGrid;
    Node:  const { PitchGrid } = require("./PitchGrid");

    // E dorian, tuning rooted on Bb, Werckmeister I, A = 419 Hz, E4-E5
    const pg = PitchGrid.fromMask("werckmeister1", "dorian", "e4", "e5", "bf3", "e4", { referenceAHz: 419 });
    pg.quantise(66.2);

Differences from the Python version
-----------------------------------
- Keyword arguments become an options object.
- No toMidi() file export; toEvents() returns the grid as a sequence of
  notes ({ startSec, durationSec, pitch, bend }) to play from Max.
*/

const load = name => { try { return require("./" + name); } catch (e) { return require(name); } };
const { Grid } = load("Grid");
const { Envelope } = load("Envelope");
const { mtof, mtospn, forceIntoRangeMidi } = load("Pitch");
const { TUNING_SYSTEMS, toMidi, circDist } = load("TuningSystem");

const roundTo = (x, d) => Number(Number(x).toFixed(d));
const mod = (a, b) => ((a % b) + b) % b;
const pick = arr => arr[Math.floor(Math.random() * arr.length)];
const roundHalfEven = x => { const r = Math.round(x); return Math.abs(x % 1) === 0.5 && r % 2 ? r - 1 : r; };

function resolveTS(ts) {
    if (typeof ts !== "string") return ts;
    if (!Object.hasOwn(TUNING_SYSTEMS, ts)) {
        throw new Error(`PitchGrid: unknown tuning system '${ts}'. Available: ${JSON.stringify(Object.keys(TUNING_SYSTEMS))}`);
    }
    return TUNING_SYSTEMS[ts];
}

/** Sorted, unique pitch classes, shifted so the lowest is 0 (transposition-invariant). */
function pcNorm(midiList, interval) {
    const pcs = [...new Set(midiList.map(m => roundTo(mod(m, interval), 6)))].sort((a, b) => a - b);
    const mn = pcs.length ? pcs[0] : 0;
    return pcs.map(p => roundTo(p - mn, 6));
}

/** Mean squared circular distance from each target class to its nearest reference class. */
function fitError(tgtNorm, refPCs, interval) {
    if (!tgtNorm.length || !refPCs.length) return Infinity;
    const ref = refPCs.map(p => roundTo(p - refPCs[0], 6));
    return tgtNorm.reduce((acc, p) => acc + Math.min(...ref.map(q => circDist(p, q, interval) ** 2)), 0) / tgtNorm.length;
}

const byErrorThenName = (a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0);

class PitchGrid extends Grid {

    /** values: MIDI floats or SPN strings. */
    constructor(values = null, { referenceAHz = 440 } = {}) {
        super([...(values || [])].map(v => toMidi(v, referenceAHz)));
        this.lowestPitch = this.size ? Math.min(...this) : 0;
        this.highestPitch = this.size ? Math.max(...this) : 0;
        this.referenceAHz = referenceAHz;
        this.tuningSystemName = "undefined";
        this.maskName = null;
        this.tuningSystemRoot = null;
        this.scaleRoot = null;
    }

    // ------------------------------------------------------------------
    // Constructors
    // ------------------------------------------------------------------

    /** All pitches of `ts` within [lowestPitch, highestPitch]; pitchUnit 'midi' | 'hz' | 'spn'. */
    static fromTuningSystem(ts, lowestPitch = 48, highestPitch = 84, tuningSystemRoot = null,
                            { pitchUnit = "midi", referenceAHz = 440 } = {}) {
        return PitchGrid.fromMask(ts, null, lowestPitch, highestPitch, tuningSystemRoot, null, { pitchUnit, referenceAHz });
    }

    /** Pitches of `ts` filtered by mask `maskName` (null = all), with key (tuningSystemRoot)
        and mode root (scaleRoot). */
    static fromMask(ts, maskName, lowestPitch = 48, highestPitch = 84, tuningSystemRoot = null, scaleRoot = null,
                    { pitchUnit = "midi", referenceAHz = 440, useAscending = false } = {}) {
        ts = resolveTS(ts);
        if (maskName !== null && !Object.hasOwn(ts.scaleMasks, maskName)) {
            throw new Error(`PitchGrid.fromMask: mask '${maskName}' not in '${ts.name}'. Available: ${JSON.stringify(Object.keys(ts.scaleMasks))}`);
        }
        const m = v => (v === null ? null : toMidi(v, referenceAHz, pitchUnit));
        const low = m(lowestPitch), high = m(highestPitch);
        const pg = new PitchGrid(ts.generatePitches(low, high, {
            referenceAHz, tuningSystemRoot: m(tuningSystemRoot), scaleRoot: m(scaleRoot),
            mask: maskName === null ? null : ts.scaleMasks[maskName], useAscending,
        }), { referenceAHz });
        Object.assign(pg, { lowestPitch: low, highestPitch: high, tuningSystemName: ts.name, maskName,
                            tuningSystemRoot: m(tuningSystemRoot), scaleRoot: m(scaleRoot) });
        return pg;
    }

    /**
     * Best-fitting TuningSystem + ScaleMask for `targetPitch` (transposition-invariant).
     * possibleSystems / possibleMasks restrict the search; possibleScaleRoots picks the
     * best mode root from a list; applyMask=false returns the whole tuning system.
     */
    static fromCorrelation(targetPitch, lowestPitch = 48, highestPitch = 84, {
        pitchUnit = "midi", referenceAHz = 440, possibleSystems = null, possibleMasks = null,
        possibleScaleRoots = null, applyMask = true,
    } = {}) {
        if (!targetPitch || !targetPitch.length) throw new Error("PitchGrid.fromCorrelation: targetPitch is empty");
        const m = v => toMidi(v, referenceAHz, pitchUnit);
        const low = m(lowestPitch), high = m(highestPitch);
        const tgt = targetPitch.map(m);
        const roots = possibleScaleRoots === null ? null : possibleScaleRoots.map(m);

        const candidates = [];
        for (const tsName of possibleSystems || Object.keys(TUNING_SYSTEMS)) {
            if (!Object.hasOwn(TUNING_SYSTEMS, tsName)) continue;
            const ts = TUNING_SYSTEMS[tsName];
            for (const mName of possibleMasks || Object.keys(ts.scaleMasks)) {
                if (Object.hasOwn(ts.scaleMasks, mName)) candidates.push([tsName, mName]);
            }
        }
        if (!candidates.length) throw new Error("PitchGrid.fromCorrelation: no valid candidates");

        let best = null;
        for (const [tsName, mName] of candidates) {
            const ts = TUNING_SYSTEMS[tsName];
            const interval = ts.repeatIntervalSemitones || 12;
            const maskPCs = ts.scaleMasks[mName].pitchClasses(ts);
            if (!maskPCs.length) continue;
            const err = fitError(pcNorm(tgt, interval), maskPCs, interval);
            if (best === null || err < best[0]) best = [err, tsName, mName];
        }
        if (best === null) throw new Error("PitchGrid.fromCorrelation: no match found");
        const [, tsName, mName] = best;

        let bestRoot = null;
        if (roots !== null && applyMask) {
            const interval = TUNING_SYSTEMS[tsName].repeatIntervalSemitones || 12;
            const tgtNorm = pcNorm(tgt, interval);
            let bestErr = Infinity;
            for (const root of roots) {
                const pg = PitchGrid.fromMask(tsName, mName, low, high, null, root, { referenceAHz });
                const pcs = [...new Set([...pg].map(x => roundTo(mod(x, interval), 6)))].sort((a, b) => a - b);
                if (!pcs.length) continue;
                const err = fitError(tgtNorm, pcs, interval);
                if (err < bestErr) [bestErr, bestRoot] = [err, root];
            }
        }
        return applyMask
            ? PitchGrid.fromMask(tsName, mName, low, high, null, bestRoot, { referenceAHz })
            : PitchGrid.fromTuningSystem(tsName, low, high, null, { referenceAHz });
    }

    // ------------------------------------------------------------------
    // Analysis
    // ------------------------------------------------------------------

    /** [[error, systemName], ...] best first. */
    findClosestTuningSystem(possibleSystems = null) {
        if (!this.size) throw new Error("PitchGrid.findClosestTuningSystem: grid is empty");
        const ratings = [];
        for (const name of possibleSystems || Object.keys(TUNING_SYSTEMS)) {
            const ts = TUNING_SYSTEMS[name];
            if (!ts || !ts.pitchClasses.length) continue;
            const interval = ts.repeatIntervalSemitones || 12;
            ratings.push([roundTo(fitError(pcNorm([...this], interval), ts.pitchClasses, interval), 8), name]);
        }
        return ratings.sort(byErrorThenName);
    }

    /** [[error, maskName], ...] within one tuning system, best first. */
    findClosestMask(tuningSystemName = "edo12", possibleMasks = null) {
        if (!this.size) throw new Error("PitchGrid.findClosestMask: grid is empty");
        const ts = TUNING_SYSTEMS[tuningSystemName];
        if (!ts) throw new Error(`PitchGrid.findClosestMask: unknown system '${tuningSystemName}'`);
        const interval = ts.repeatIntervalSemitones || 12;
        const gridNorm = pcNorm([...this], interval);
        const ratings = [];
        for (const mName of possibleMasks || Object.keys(ts.scaleMasks)) {
            const mask = ts.scaleMasks[mName];
            if (!mask) continue;
            const pcs = mask.pitchClasses(ts);
            if (pcs.length) ratings.push([roundTo(fitError(gridNorm, pcs, interval), 8), mName]);
        }
        return ratings.sort(byErrorThenName);
    }

    /** New PitchGrid with every pitch octave-folded into [lowestPitch, highestPitch]. */
    constrainToRange(lowestPitch = 48, highestPitch = 84, { pitchUnit = "midi", referenceAHz = null } = {}) {
        const ref = referenceAHz === null ? this.referenceAHz : referenceAHz;
        const low = toMidi(lowestPitch, ref, pitchUnit), high = toMidi(highestPitch, ref, pitchUnit);
        if (low > high) throw new RangeError(`PitchGrid.constrainToRange: lowestPitch (${low}) must not exceed highestPitch (${high})`);
        const pg = new PitchGrid([...this].map(p => forceIntoRangeMidi(p, low, high)), { referenceAHz: ref });
        Object.assign(pg, { lowestPitch: low, highestPitch: high, tuningSystemName: this.tuningSystemName,
                            maskName: this.maskName, tuningSystemRoot: this.tuningSystemRoot, scaleRoot: this.scaleRoot });
        return pg;
    }

    /** numNotes pitches following `env` (scaled lowestPitch..highestPitch, quantised);
        without an envelope a new random 5-point contour on every call. */
    melodicContourFromEnvelope(env = null, numNotes = 16) {
        if (env === null) env = new Envelope(Array.from({ length: 5 }, Math.random));
        return Array.from({ length: numNotes }, (_, n) => {
            const y = env.getValue(numNotes > 1 ? n / (numNotes - 1) : 0, true, true);
            return this.quantise(this.lowestPitch + y * (this.highestPitch - this.lowestPitch));
        });
    }

    // ------------------------------------------------------------------
    // Conversion
    // ------------------------------------------------------------------

    toHzList() { return this.sorted().map(m => mtof(m, this.referenceAHz)); }

    toMidiList() { return this.sorted(); }

    /** The grid as an ascending sequence of notes: { startSec, durationSec, pitch, bend }. */
    toEvents(noteDurationSec = 2) {
        return this.sorted().map((m, i) => {
            const anchor = roundHalfEven(m);
            return { startSec: i * noteDurationSec, durationSec: noteDurationSec, pitch: anchor, bend: [m - anchor, m - anchor] };
        });
    }

    /**
     * Chord built downward from `topNote` with this grid as a sieve:
     * numPrimaryNotes steps of random primaryIntervals, each quantised; with
     * clusterChance a neighbour from clusterIntervals; all folded into
     * [minPitch, topNote] (pitches that cannot fit are dropped); topNote first,
     * then a random selection, numMaxNotes in total, in pitchUnit.
     */
    makeChordFromTopNote(topNote, {
        primaryIntervals = [1, 7, 9], numPrimaryNotes = 4, numMaxNotes = 8, clusterChance = 0.1,
        minPitch = 48, clusterIntervals = [-2, -1, 1, 2], pitchUnit = "midi", referenceAHz = 440,
    } = {}) {
        const top = toMidi(topNote, referenceAHz, pitchUnit), lo = toMidi(minPitch, referenceAHz, pitchUnit);
        const primary = [top];
        for (let i = 0; i < numPrimaryNotes; i++) primary.push(this.quantise(primary[primary.length - 1] - pick(primaryIntervals)));
        primary.shift();

        const cluster = [];
        for (const pm of primary) {
            if (Math.random() < clusterChance) {
                const cands = [...new Set(clusterIntervals.map(iv => this.quantise(pm + iv)))].filter(c => c !== pm);
                if (cands.length) cluster.push(pick(cands));
            }
        }
        const potential = [];
        for (const p of primary.concat(cluster)) {
            let folded;
            try { folded = this.quantise(forceIntoRangeMidi(p, lo, top)); } catch (e) { continue; }
            if (lo <= folded && folded <= top) potential.push(folded);
        }
        for (let i = potential.length - 1; i > 0; i--) {             // shuffle, then take n
            const j = Math.floor(Math.random() * (i + 1));
            [potential[i], potential[j]] = [potential[j], potential[i]];
        }
        const chosen = [top, ...potential.slice(0, Math.max(0, Math.min(numMaxNotes - 1, potential.length)))];
        if (pitchUnit === "hz") return chosen.map(x => mtof(x, referenceAHz));
        if (pitchUnit === "spn") return chosen.map(mtospn);
        return chosen;
    }

    toString() {
        if (!this.size) return "PitchGrid(empty)";
        const r = x => (x === null ? null : roundTo(x, 3));
        const preview = this.sorted().slice(0, 6).map(r);
        return `PitchGrid(size=${this.size}, range=${r(this.lowestPitch)}-${r(this.highestPitch)} MIDI, ` +
               `system='${this.tuningSystemName}', mask=${JSON.stringify(this.maskName)}, ` +
               `tsRoot=${r(this.tuningSystemRoot)}, scaleRoot=${r(this.scaleRoot)}, refA=${this.referenceAHz} Hz, ` +
               `preview=${JSON.stringify(preview)}${this.size > 6 ? " ..." : ""})`;
    }
}

if (typeof exports !== "undefined") exports.PitchGrid = PitchGrid;
