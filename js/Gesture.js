/*
Gesture.js — JavaScript port of GreasyPidgin/Gesture.py

A Gesture is a TemporalObject whose children are Phonons (or other
Gestures), with times relative to the Gesture's start.

Runs in Max 9 [v8] and in Node.

    Max:   var Gesture = require("Gesture").Gesture;
    Node:  const { Gesture } = require("./Gesture");

    const g = Gesture.fromLists(8, { startDeltas: [0.5, 0.25], pitches: [60, 62, [64, 67]], dynamics: ["p", "mf-ff"] });
    g.toEvents();   // [{ startSec, durationSec, pitch, bend, velocity, ... }, ...]

    // or think in note values (beats); negative = rest
    const r = Gesture.fromRhythm([1, 0.5, 0.5, -1, 1], { pitches: [60, 62, 64], bpm: 120 });

Differences from the Python version
-----------------------------------
- fromLists(size, options) takes every other parameter as an option.
- quantiseTime(grid, parentalStartSec = 0, durationThresholdSec = 0.001).
- No fromMidiFile() and no file exporters; toEvents() gives the playable notes.
- fromRhythm(rhythm, options): pitches and dynamics are options here, positional in Python.
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { TemporalObject } = load("TemporalObject");
const { Envelope } = load("Envelope");
const { Phonon, noteEvents } = load("Phonon");

const asList = v => (Array.isArray(v) ? v : [v]);

class Gesture extends TemporalObject {

    constructor(startTimeSec = 0, phonons = null, durationSec = 0, { bpm = 60, ticksPerBeat = 480 } = {}) {
        super(startTimeSec, durationSec, null, { data: { bpm, ticksPerBeat } });
        for (const p of phonons || []) {
            if (!(p instanceof Phonon || p instanceof Gesture)) {
                throw new TypeError(`Gesture: expected Phonon or Gesture, got ${p?.constructor?.name ?? typeof p}`);
            }
            // propagate tempo to children that haven't set their own
            p.data.bpm ??= bpm;
            p.data.ticksPerBeat ??= ticksPerBeat;
            this.children.push(p);
        }
        if (this.children.length && Number(durationSec) === 0) this._refresh();
    }

    /** Unfold every Phonon in the tree (see Phonon.unfold). */
    _unfoldAll(noteSelectKey = null) {
        for (const c of this.children) {
            if (c instanceof Gesture) c._unfoldAll(noteSelectKey);
            else if (c instanceof Phonon) c.unfold(noteSelectKey);
        }
    }

    _phonons() {
        return this.children.filter(c => c instanceof Phonon);
    }

    /** One marking per direct Phonon child, in order ('pp', 'mf', 'pp-mp', ...). */
    setDynamicMarkings(markings) {
        this._phonons().forEach((p, i) => { if (i < markings.length) p.setDynamicMarking(markings[i]); });
    }

    getDynamicMarkings() {
        return this._phonons().map(p => p.getDynamicMarking());
    }

    /** One lyric per direct Phonon child, in order. */
    setLyrics(lyrics, { offsetSec = 0 } = {}) {
        this._phonons().forEach((p, i) => { if (i < lyrics.length) p.setLyric(lyrics[i], offsetSec); });
    }

    getLyrics() {
        return this._phonons().map(p => p.getLyric());
    }

    /** Quantise all note times (absolute) to `grid`, then drop children shorter
        than durationThresholdSec. */
    quantiseTime(grid, parentalStartSec = 0, durationThresholdSec = 0.001) {
        super.quantiseTime(grid, parentalStartSec);
        this.children = this.children.filter(c => c.durationSec > durationThresholdSec);
        this._refresh();
    }

    /** Unfold all Phonons, then the playable notes (see noteEvents()). */
    toEvents(noteSelectKey = null) {
        this._unfoldAll(noteSelectKey);
        return noteEvents(this);
    }

    /**
     * Build a Gesture from parallel lists, each cycled modulo its length:
     *   startDeltas : inter-onset times (default 0.5)
     *   durations   : note lengths (default 1)
     *   pitches     : per note a pitch or a list (chord / sequence) (default [0])
     *   dynamics    : per note a number, a marking ('mf', 'pp-f') or an Envelope (default 64)
     * plus startOffset and the Phonon options timeUnit, pitchUnit, dynamicUnit,
     * chordOrSeq ('chord' by default), autoSortChords, bpm, ticksPerBeat, referenceA.
     */
    static fromLists(size = 0, {
        startOffset = 0, startDeltas = 0.5, durations = 1, pitches = [0], dynamics = 64,
        timeUnit = "seconds", pitchUnit = "midi", dynamicUnit = "midi", chordOrSeq = "chord",
        autoSortChords = true, bpm = 60, ticksPerBeat = 480, referenceA = 440,
    } = {}) {
        if (!Number.isInteger(size) || size < 0) throw new RangeError(`Gesture.fromLists: size must be a non-negative int, got ${size}`);
        const lists = { startDeltas: asList(startDeltas), durations: asList(durations),
                        pitches: asList(pitches), dynamics: asList(dynamics) };
        if (size > 0) {
            for (const [name, values] of Object.entries(lists)) {
                if (!values.length) throw new Error(`Gesture.fromLists: ${name} must not be empty when size > 0`);
            }
        }
        const at = (name, i) => lists[name][i % lists[name].length];
        const startSec = timeUnit === "beats" || timeUnit === "b" ? startOffset * 60 / bpm : Number(startOffset);

        // Phonon times are relative to the Gesture, which already starts at startSec
        const phonons = [];
        let start = 0;
        for (let i = 0; i < size; i++) {
            if (i > 0) start += Number(at("startDeltas", i));
            const d = at("dynamics", i);
            phonons.push(new Phonon(start, at("durations", i), asList(at("pitches", i)),
                typeof d === "string" || d instanceof Envelope || Array.isArray(d) ? d : Number(d), bpm,
                { timeUnit, pitchUnit, dynamicUnit, chordOrSeq, autoSortChords, ticksPerBeat, referenceA }));
        }
        return new Gesture(startSec, phonons, 0, { bpm, ticksPerBeat });
    }

    /**
     * Build a Gesture from a rhythm: a list of note values played one after another.
     * Each value is how long that note lasts (in beats by default); a negative value is a rest.
     * Pitches and dynamics cycle over the sounding notes, so they can have any length.
     *
     *   Gesture.fromRhythm([1, 0.5, 0.5, -1, 1], { pitches: [60, 62, 64], bpm: 120 })
     *   -> quarter C, eighth D, eighth E, quarter rest, quarter C
     *
     * legato scales the sounding length (1 = full value, 0.5 = staccato);
     * repeats plays the rhythm several times in a row.
     */
    static fromRhythm(rhythm, {
        pitches = [60], dynamics = 64, legato = 1, repeats = 1, startOffset = 0,
        timeUnit = "beats", pitchUnit = "midi", dynamicUnit = "midi", chordOrSeq = "chord",
        autoSortChords = true, bpm = 60, ticksPerBeat = 480, referenceA = 440,
    } = {}) {
        const values = asList(rhythm).map(Number);
        if (!values.length || values.some(v => !Number.isFinite(v) || v === 0)) {
            throw new RangeError(`Gesture.fromRhythm: rhythm must be non-zero numbers (negative = rest), got [${asList(rhythm)}]`);
        }
        if (!Number.isInteger(repeats) || repeats < 1) throw new RangeError(`Gesture.fromRhythm: repeats must be an int >= 1, got ${repeats}`);
        if (!(legato > 0)) throw new RangeError(`Gesture.fromRhythm: legato must be > 0, got ${legato}`);
        const p = asList(pitches), dyn = asList(dynamics);
        if (!p.length || !dyn.length) throw new Error("Gesture.fromRhythm: pitches and dynamics must not be empty");
        const toSec = v => (timeUnit === "beats" || timeUnit === "b" ? v * 60 / bpm : v);

        const phonons = [];
        let start = 0, n = 0;
        for (let r = 0; r < repeats; r++) {
            for (const v of values) {
                if (v > 0) {
                    const d = dyn[n % dyn.length];
                    phonons.push(new Phonon(start, v * legato, asList(p[n % p.length]),
                        typeof d === "string" || d instanceof Envelope || Array.isArray(d) ? d : Number(d), bpm,
                        { timeUnit, pitchUnit, dynamicUnit, chordOrSeq, autoSortChords, ticksPerBeat, referenceA }));
                    n++;
                }
                start += Math.abs(v);
            }
        }
        // the Gesture lasts the whole rhythm, trailing rests included
        return new Gesture(toSec(startOffset), phonons, toSec(start), { bpm, ticksPerBeat });
    }

    toString() {
        const f = x => x.toFixed(3);
        return `Gesture(id=${this.id}, start=${f(this.startTimeSec)}s, dur=${f(this.durationSec)}s, ` +
               `end=${f(this.endTimeSec)}s, bpm=${this.data.bpm}, children=${this.children.length})`;
    }
}

for (const C of [Gesture]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") exports.Gesture = Gesture;
