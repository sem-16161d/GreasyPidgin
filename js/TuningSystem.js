/*
TuningSystem.js — JavaScript port of GreasyPidgin/TuningSystemAndScaleMask.py

A TuningSystem is a pitch space of MIDI-float offsets from its unison
(C = 0), repeating every repeatIntervalSemitones (12 = octave, ~19.02 =
tritave), or non-repeating. A ScaleMask picks step indices from it.

    Max:   var T = require("TuningSystem");   T.TUNING_SYSTEMS.werckmeister1
    Node:  const { TuningSystem, ScaleMask, TUNING_SYSTEMS } = require("./TuningSystem");

    TUNING_SYSTEMS.werckmeister1.generatePitches("e4", "e5",
        { tuningSystemRoot: "bf3", scaleRoot: "e4", mask: TUNING_SYSTEMS.werckmeister1.scaleMasks.dorian });

Differences from the Python version: keyword arguments become an options
object; the module is TuningSystem.js (TuningSystem + ScaleMask + presets).
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { spntom, mtof, ftom } = load("Pitch");

const roundTo = (x, d) => Number(Number(x).toFixed(d));
const mod = (a, b) => ((a % b) + b) % b;

/** Pitch value -> MIDI float. Strings are always SPN; 'hz' reads numbers as Hz,
    'midi' and 'spn' read numbers as MIDI. */
function toMidi(value, referenceAHz = 440, pitchUnit = "midi") {
    if (typeof value === "string") return spntom(value);
    if (pitchUnit === "hz") return ftom(Number(value), referenceAHz);
    if (pitchUnit === "midi" || pitchUnit === "spn") return Number(value);
    throw new Error(`unknown pitchUnit '${pitchUnit}' (use 'midi', 'hz' or 'spn')`);
}

/** Circular distance within a repeat interval (in semitones). */
function circDist(a, b, interval) {
    const d = Math.abs(mod(a - b, interval));
    return Math.min(d, interval - d);
}

class ScaleMask {
    /** indices: 0-based steps of the (rotated) tuning system; ascending: optional
        separate ascending form (melodic minor, maqamat, ragas). */
    constructor(name, indices, { description = "", ascending = null } = {}) {
        this.name = String(name);
        this.indices = [...indices];
        this.description = String(description);
        this.ascending = ascending ? [...ascending] : null;
    }

    /** MIDI semitone offsets of this mask's steps within `ts`. */
    pitchClasses(ts, { useAscending = false } = {}) {
        const idx = useAscending && this.ascending ? this.ascending : this.indices;
        return idx.filter(i => i < ts.pitchClasses.length).map(i => ts.pitchClasses[i]);
    }

    toString() {
        return `ScaleMask('${this.name}', indices=${JSON.stringify(this.indices)}` +
               (this.ascending ? `, ascending=${JSON.stringify(this.ascending)}` : "") + ")";
    }
}

class TuningSystem {

    constructor(name, pitchClasses, { repeatIntervalSemitones = 12, scaleMasks = null, metadata = null, stepSemitones = null } = {}) {
        this.name = String(name);
        this.repeatIntervalSemitones = repeatIntervalSemitones === null ? null : Number(repeatIntervalSemitones);
        // equal step of a non-repeating equal-division system (fromRatio), else null
        this.stepSemitones = stepSemitones ? Number(stepSemitones) : null;
        // within one repeat interval: a value equal to the interval is the next unison
        const ri = this.repeatIntervalSemitones;
        this.pitchClasses = [...new Set(pitchClasses.map(p => (ri ? roundTo(mod(Number(p), ri), 10) : Number(p))))]
            .sort((a, b) => a - b);
        this.scaleMasks = { ...(scaleMasks || {}) };
        this.metadata = { ...(metadata || {}) };
    }

    /** n equal divisions of the octave. */
    static fromEDO(n, { name = null, scaleMasks = null, metadata = null } = {}) {
        const step = 12 / n;
        return new TuningSystem(name || `edo${n}`, Array.from({ length: n }, (_, i) => roundTo(i * step, 10)), {
            repeatIntervalSemitones: 12, scaleMasks, metadata: metadata || { description: `${n}-tone equal temperament` },
        });
    }

    /**
     * Equal division from a frequency ratio between steps.
     * groupRatio: ratio between groups (default stepRatio ** stepsPerGroup);
     * repeatInterval: semitones, null = from groupRatio, false = non-repeating
     * (every step of the lattice, no octave identity).
     */
    static fromRatio(name, stepRatio, stepsPerGroup, { groupRatio = null, repeatInterval = null, scaleMasks = null, metadata = null } = {}) {
        if (groupRatio === null) groupRatio = stepRatio ** stepsPerGroup;
        const stepSemitones = 12 * Math.log2(stepRatio);
        const pc = Array.from({ length: stepsPerGroup }, (_, i) => roundTo(i * stepSemitones, 10));
        const ri = repeatInterval === null ? 12 * Math.log2(groupRatio) : repeatInterval === false ? null : Number(repeatInterval);
        return new TuningSystem(name, pc, { repeatIntervalSemitones: ri, scaleMasks, metadata,
                                            stepSemitones: ri === null ? stepSemitones : null });
    }

    /**
     * Explicit semitone offsets from unison (JI, historical temperaments, maqam
     * approximations). Unison is added if missing. Repeat interval: the last
     * value if >= 12 (then a boundary, not a pitch), else the octave.
     */
    static fromSemitones(name, semitones, { repeatInterval = null, scaleMasks = null, metadata = null } = {}) {
        let pc = [...new Set(semitones.map(Number))].sort((a, b) => a - b);
        if (pc[0] !== 0) pc.unshift(0);
        let ri;
        if (repeatInterval === null) {
            if (pc[pc.length - 1] >= 12) {
                ri = pc[pc.length - 1];
                pc = pc.filter(p => p < ri);
            } else {
                ri = 12;
            }
        } else {
            ri = Number(repeatInterval);
        }
        return new TuningSystem(name, pc, { repeatIntervalSemitones: ri, scaleMasks, metadata });
    }

    /** Measured frequencies (gamelan, instruments) relative to referenceHz;
        repeatIntervalHz null = non-repeating. */
    static fromHz(name, frequencies, referenceHz, { repeatIntervalHz = null, scaleMasks = null, metadata = null } = {}) {
        const pc = [...frequencies].map(Number).sort((a, b) => a - b).map(f => 12 * Math.log2(f / referenceHz));
        return new TuningSystem(name, pc, {
            repeatIntervalSemitones: repeatIntervalHz === null ? null : 12 * Math.log2(repeatIntervalHz / referenceHz),
            scaleMasks, metadata,
        });
    }

    /**
     * MIDI floats within [lowestPitch, highestPitch] (MIDI or SPN).
     *
     * tuningSystemRoot : note that pitch class 0 sits on (null = C)
     * scaleRoot        : note where the mask starts (nearest system pitch)
     * mask             : ScaleMask sieve; null = every step
     * useAscending     : use the mask's ascending form
     * referenceAHz     : only for Hz conversion of inputs
     */
    generatePitches(lowestPitch, highestPitch, { referenceAHz = 440, tuningSystemRoot = null, scaleRoot = null, mask = null, useAscending = false } = {}) {
        const EPS = 1e-6;
        const low = toMidi(lowestPitch, referenceAHz), high = toMidi(highestPitch, referenceAHz);
        const nSteps = this.pitchClasses.length;
        const anchor = tuningSystemRoot === null ? 0 : toMidi(tuningSystemRoot, referenceAHz);

        const chromatic = [];   // [midi, pcIndex]
        const keep = (midi, i) => { if (low - EPS <= midi && midi <= high + EPS) chromatic.push([roundTo(midi, 8), i]); };
        if (this.repeatIntervalSemitones !== null || this.stepSemitones !== null) {
            // repeating: anchor + g*interval + pc[i]; non-repeating equal steps: anchor + k*step
            const lattice = this.repeatIntervalSemitones === null;
            const interval = lattice ? this.stepSemitones : this.repeatIntervalSemitones;
            const classes = lattice ? [0] : this.pitchClasses;
            const gMin = Math.floor((low - anchor) / interval) - 1, gMax = Math.ceil((high - anchor) / interval) + 1;
            for (let g = gMin; g <= gMax; g++) {
                classes.forEach((p, i) => keep(anchor + g * interval + p, lattice ? mod(g, nSteps) : i));
            }
        } else {
            this.pitchClasses.forEach((p, i) => keep(anchor + p, i));   // finite set
        }
        chromatic.sort((a, b) => a[0] - b[0]);
        if (!chromatic.length) return [];

        let srPCIdx = chromatic[0][1];
        if (scaleRoot !== null) {
            const sr = toMidi(scaleRoot, referenceAHz);
            let best = 0;
            chromatic.forEach(([m], i) => { if (Math.abs(m - sr) < Math.abs(chromatic[best][0] - sr)) best = i; });
            srPCIdx = chromatic[best][1];
        }
        if (mask === null) return chromatic.map(([m]) => m);
        const maskSet = new Set(useAscending && mask.ascending ? mask.ascending : mask.indices);
        return chromatic.filter(([, i]) => maskSet.has(mod(i - srPCIdx, nSteps))).map(([m]) => m);
    }

    midiToHz(midi, referenceAHz = 440) { return mtof(midi, referenceAHz); }

    hzToMidi(hz, referenceAHz = 440) { return ftom(hz, referenceAHz); }

    /** Pitch class within the repeat interval; null if non-repeating. */
    pitchClassOf(midi) {
        return this.repeatIntervalSemitones === null ? null : mod(midi, this.repeatIntervalSemitones);
    }

    addMask(mask) { this.scaleMasks[mask.name] = mask; }

    addMasks(masks) { masks.forEach(m => this.addMask(m)); }

    toString() {
        const ri = this.repeatIntervalSemitones ? `${this.repeatIntervalSemitones.toFixed(4)} semitones` : "non-repeating";
        return `TuningSystem('${this.name}', steps=${this.pitchClasses.length}, repeat=${ri}, masks=${JSON.stringify(Object.keys(this.scaleMasks))})`;
    }
}

// ---------------------------------------------------------------------------
// Predefined tuning systems
// ---------------------------------------------------------------------------

const TUNING_SYSTEMS = {};
const reg = ts => (TUNING_SYSTEMS[ts.name] = ts);
const ji = (...ratios) => ratios.map(r => roundTo(12 * Math.log2(r), 8));
const edo24steps = (...steps) => steps.map(s => roundTo(s * 0.5, 8));
const phi = (1 + Math.sqrt(5)) / 2;

for (const n of [12, 24, 31, 53, 72]) reg(TuningSystem.fromEDO(n));

reg(TuningSystem.fromRatio("bohlenPierce", 3 ** (1 / 13), 13,
    { metadata: { description: "Bohlen-Pierce, tritave repeat (~19.02 semitones)" } }));
reg(TuningSystem.fromRatio("studieII", 5 ** (1 / 5), 5, { groupRatio: 5 ** (1 / 5), repeatInterval: false,
    metadata: { description: "Stockhausen Studie II, self-similar 5^(1/5)", source: "Karlheinz Stockhausen, Studie II (1954)" } }));
reg(TuningSystem.fromRatio("stria", phi, 1, { groupRatio: phi, repeatInterval: false,
    metadata: { description: "Chowning Stria, golden ratio phi", source: "John Chowning, Stria (1977)" } }));

const temperaments = {   // semitone offsets = cents / 100
    werckmeister1: ["Werckmeister I (III)", [0, 0.90, 1.92, 2.94, 3.90, 4.98, 5.88, 6.96, 7.92, 8.88, 9.96, 10.92]],
    werckmeister2: ["Werckmeister II (IV)", [0, 0.82, 1.96, 2.94, 3.92, 4.98, 5.88, 6.94, 7.84, 8.90, 10.04, 10.86]],
    werckmeister3: ["Werckmeister III (V)", [0, 0.96, 2.04, 3.00, 3.96, 5.04, 6.00, 7.02, 7.92, 9.00, 10.02, 10.98]],
    werckmeister4: ["Werckmeister IV (VI)", [0, 0.90, 1.87, 2.98, 3.95, 4.98, 5.95, 6.98, 7.92, 8.93, 10.00, 10.97]],
    kirnberger2:   ["Kirnberger II",        [0, 0.90, 2.04, 2.94, 3.86, 4.98, 5.92, 7.02, 7.92, 8.95, 9.96, 10.88]],
    kirnberger3:   ["Kirnberger III",       [0, 0.90, 1.95, 2.94, 3.86, 4.98, 5.90, 6.97, 7.92, 8.92, 9.96, 10.88]],
    meantoneQC:    ["Quarter-comma meantone", [0, 0.76, 1.93, 3.10, 3.86, 5.03, 5.79, 6.97, 8.14, 8.90, 10.07, 10.83]],
    pythagorean:   ["Pythagorean tuning",   [0, 1.14, 2.04, 2.94, 4.08, 4.98, 6.12, 7.02, 8.16, 9.06, 9.96, 11.10]],
    zeta12:        ["Zeta-12: Margo Schulter, Centaur-inspired JI", [0, 1.39, 2.04, 2.67, 3.47, 4.98, 6.37, 7.02, 7.65, 8.41, 9.69, 10.49]],
};
for (const [name, [description, pcs]] of Object.entries(temperaments)) {
    reg(TuningSystem.fromSemitones(name, pcs, { metadata: { description } }));
}

reg(TuningSystem.fromSemitones("JI_5limit_major", ji(1, 9 / 8, 5 / 4, 4 / 3, 3 / 2, 5 / 3, 15 / 8),
    { repeatInterval: 12, metadata: { description: "Ptolemy's intense diatonic / 5-limit JI major" } }));
reg(TuningSystem.fromSemitones("JI_7limit", ji(1, 9 / 8, 7 / 6, 9 / 7, 3 / 2, 7 / 4, 15 / 8),
    { repeatInterval: 12, metadata: { description: "7-limit JI with harmonic seventh" } }));
reg(TuningSystem.fromSemitones("harmonicSeries8_16", ji(8 / 8, 9 / 8, 10 / 8, 11 / 8, 12 / 8, 13 / 8, 14 / 8, 15 / 8, 16 / 8),
    { repeatInterval: 12, metadata: { description: "Harmonic series partials 8-16" } }));

reg(TuningSystem.fromSemitones("maqamRast", edo24steps(0, 4, 7, 10, 14, 18, 21),
    { repeatInterval: 12, metadata: { description: "Maqam Rast — 24-EDO approximation" } }));
reg(TuningSystem.fromSemitones("maqamBayati", edo24steps(0, 3, 6, 10, 14, 18, 21),
    { repeatInterval: 12, metadata: { description: "Maqam Bayati — 24-EDO approximation" } }));
reg(TuningSystem.fromSemitones("maqamHijaz", edo24steps(0, 2, 8, 10, 14, 16, 20),
    { repeatInterval: 12, metadata: { description: "Maqam Hijaz — 24-EDO approximation" } }));

reg(TuningSystem.fromHz("slendro_approx", [260.4, 295.2, 325.0, 390.5, 433.2], 260.4,
    { repeatIntervalHz: 2 * 260.4, metadata: { description: "Approximate Javanese Sléndro" } }));
reg(TuningSystem.fromHz("pelog_approx", [260.4, 277.2, 309.4, 347.6, 390.5, 416.2, 463.5], 260.4,
    { repeatIntervalHz: 2 * 260.4, metadata: { description: "Approximate Javanese Pélog" } }));

reg(TuningSystem.fromSemitones("AstridsBontempi",
    [0, 19, 21, 114, 119, 208, 210, 318, 322, 397, 415, 508, 514, 621, 621, 702, 718, 819, 820, 928, 935,
     1029, 1035, 1124, 1129].map(c => c / 100),
    { metadata: { description: "Bontempi organ of Astrid Ribeiro Albuquerque Wendt" } }));

// ScaleMasks for 12-step systems (12-step indices only fit 12 steps)
const DIATONIC_MASKS = [
    ["ionian", [0, 2, 4, 5, 7, 9, 11], "Major scale"], ["dorian", [0, 2, 3, 5, 7, 9, 10]],
    ["phrygian", [0, 1, 3, 5, 7, 8, 10]], ["lydian", [0, 2, 4, 6, 7, 9, 11]],
    ["mixolydian", [0, 2, 4, 5, 7, 9, 10]], ["aeolian", [0, 2, 3, 5, 7, 8, 10], "Natural minor"],
    ["locrian", [0, 1, 3, 5, 6, 8, 10]],
    ["harmonicMinor", [0, 2, 3, 5, 7, 8, 11], "HM mode 1"], ["locrianSharp6", [0, 1, 3, 5, 6, 9, 10], "HM mode 2"],
    ["ionianSharp5", [0, 2, 4, 5, 8, 9, 11], "HM mode 3"], ["dorianSharp4", [0, 2, 3, 6, 7, 9, 10], "HM mode 4"],
    ["phrygianDominant", [0, 1, 4, 5, 7, 8, 10], "HM mode 5"], ["lydianSharp2", [0, 3, 4, 6, 7, 9, 11], "HM mode 6"],
    ["ultraLocrian", [0, 1, 3, 4, 6, 8, 9], "HM mode 7"],
    ["melodicMinor", [0, 2, 3, 5, 7, 9, 11], "MM mode 1", [0, 2, 3, 5, 7, 9, 11]],
    ["dorianFlat2", [0, 1, 3, 5, 7, 9, 10], "MM mode 2"], ["lydianAugmented", [0, 2, 4, 6, 8, 9, 11], "MM mode 3"],
    ["lydianDominant", [0, 2, 4, 6, 7, 9, 10], "MM mode 4"], ["mixolydianFlat6", [0, 2, 4, 5, 7, 8, 10], "MM mode 5"],
    ["locrianSharp2", [0, 2, 3, 5, 6, 8, 10], "MM mode 6"], ["altered", [0, 1, 3, 4, 6, 8, 10], "MM mode 7 / superlocrian"],
    ["wholeTone", [0, 2, 4, 6, 8, 10], "Messiaen mode 1"], ["halfWholeDim", [0, 1, 3, 4, 6, 7, 9, 10], "Messiaen mode 2"],
    ["messiaen3", [0, 2, 3, 4, 6, 7, 8, 10, 11]], ["messiaen4", [0, 1, 2, 5, 6, 7, 8, 11]],
    ["messiaen5", [0, 1, 5, 6, 7, 11]], ["messiaen6", [0, 2, 4, 5, 6, 8, 10, 11]],
    ["messiaen7", [0, 1, 2, 3, 5, 6, 7, 8, 9, 11]],
    ["majorPentatonic", [0, 2, 4, 7, 9]], ["minorPentatonic", [0, 3, 5, 7, 10]],
    ["chromatic", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]],
].map(([name, idx, description = "", ascending = null]) => new ScaleMask(name, idx, { description, ascending }));

for (const ts of Object.values(TUNING_SYSTEMS)) {
    if (ts.pitchClasses.length === 12) ts.addMasks(DIATONIC_MASKS);
}
// "chromatic" = every step, for every system that has no mask of that name yet
for (const ts of Object.values(TUNING_SYSTEMS)) {
    if (!("chromatic" in ts.scaleMasks)) ts.addMask(new ScaleMask("chromatic", ts.pitchClasses.map((_, i) => i)));
}

TUNING_SYSTEMS.bohlenPierce.addMasks([
    new ScaleMask("lambda", [0, 1, 2, 4, 5, 7, 8, 9, 11, 12], { description: "BP Lambda mode (most consonant)" }),
    new ScaleMask("walker", [0, 2, 3, 5, 6, 8, 9, 11, 12], { description: "BP Walker mode" }),
]);

if (typeof exports !== "undefined") Object.assign(exports, { TuningSystem, ScaleMask, TUNING_SYSTEMS, toMidi, circDist });
