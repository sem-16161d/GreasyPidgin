/*
Phonon.js — JavaScript port of GreasyPidgin/Phonon.py

A Phonon is a note event: a TemporalObject with pitch (midi / hz / spn),
dynamic, and chord / sequence structure. unfold() resolves it into leaf
notes; toEvents() returns those notes ready to play in Max.

Pitch is stored as chordSlots, evenly spaced over the duration:
    'seq'      one single-pitch slot per pitch         [[60], [62], [64]]
    'chord'    one slot holding every pitch            [[60, 64, 67]]
    'chordSeq' one slot per chord, [] is a rest        [[60, 64], [], [62]]

Runs in Max 9 [v8] and in Node.

    Max:   var Phonon = require("Phonon").Phonon;
    Node:  const { Phonon } = require("./Phonon");

    const p = new Phonon(0, 2, ["c4", "eqf4", "g4"], "pp-f", 90, { pitchUnit: "spn" });
    p.toEvents();   // [{ startSec, durationSec, pitch, bend, velocity, ... }, ...]

Differences from the Python version
-----------------------------------
- Keyword arguments become an options object after `bpm`.
- No file exporters (MIDI / MusicXML / JSON / CSV); toEvents() and
  noteEvents() give the same notes, velocities and pitch bends the MIDI
  exporter would write, for playing from Max.
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
const { spntom, ftom } = load("Pitch");
const { parseDynamicMarking } = load("Dynamics");

// noteSelectKey used by unfold() when none is given, per chordOrSeq
const DEFAULT_SELECT = { seq: "seq", s: "seq", chord: "chord", c: "chord", chordSeq: "chordSeq", cs: "chordSeq" };

// dB <-> MIDI velocity calibration for dynamicUnit 'midi'
const MIN_DB = 20, MAX_DB = 120, MIN_VEL = 1, MAX_VEL = 127;
const CAL_KEYS = ["minDb", "maxDb", "minVelocity", "maxVelocity"];

const clip = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const roundTo = (x, d) => Number(Number(x).toFixed(d));
const secToBeat = (sec, bpm) => sec * bpm / 60;
const beatToSec = (beat, bpm) => beat * 60 / bpm;

/** Max-style linear scale with clipping to the input range (Normalisation.scale). */
function scale(v, inLo, inHi, outLo, outHi) {
    if (inLo === inHi) return outLo;
    v = clip(v, Math.min(inLo, inHi), Math.max(inLo, inHi));
    return outLo + (v - inLo) / (inHi - inLo) * (outHi - outLo);
}

/** Python's round(): halves go to the even neighbour (60.5 -> 60, 61.5 -> 62). */
function roundHalfEven(x) {
    const r = Math.round(x);
    return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

/** MIDI velocity of a leaf, exactly as MidiExporter computes it. */
function velocityOf(leaf) {
    const d = leaf.data;
    const minDb = d.minDb ?? 0, maxDb = d.maxDb ?? 100;
    const minVel = d.minVelocity ?? 0, maxVel = d.maxVelocity ?? 127;
    const norm = scale(d.dynamicdB ?? 100, minDb, maxDb, 0, 1);
    return clip(Math.round(minVel + norm * (maxVel - minVel)), 1, 127);
}

/**
 * Leaf notes of any TemporalObject tree as plain objects, sorted by start:
 *   { startSec, durationSec, pitch (MIDI note), bend: [startSemitones, endSemitones],
 *     velocity, aftertouch (Envelope in velocity units or null), lyric, dynamicMarking }
 */
function noteEvents(to) {
    return to.flatten()
        .map(leaf => ({
            startSec: leaf.startTimeSec,
            durationSec: leaf.durationSec,
            pitch: leaf.data.pitchMidi ?? 0,
            bend: leaf.data.pitchwheel ? [...leaf.data.pitchwheel] : [0, 0],
            velocity: velocityOf(leaf),
            aftertouch: leaf.envelopes.aftertouch || null,
            lyric: leaf.annotations.length ? leaf.annotations[0][1] : null,
            dynamicMarking: leaf.data.dynamicMarking ?? null,
        }))
        .sort((a, b) => a.startSec - b.startSec || a.pitch - b.pitch);
}

class Phonon extends TemporalObject {

    constructor(startTime = 0, duration = 0, pitch = 0, dynamic = 64, bpm = 60, {
        timeUnit = "seconds", pitchUnit = "midi", dynamicUnit = "midi", chordOrSeq = "seq",
        autoSortChords = true, ticksPerBeat = 480, envelopes = null, referenceA = 440, lyric = null,
    } = {}) {
        const [startSec, durSec] = Phonon._toSeconds(startTime, duration, timeUnit, bpm);
        super(startSec, durSec, null, { envelopes, data: { bpm, ticksPerBeat } });
        this._updateBeats();

        this.pitchUnit = pitchUnit;
        this.autoSortChords = autoSortChords;
        this.referenceA = referenceA;
        this.chordOrSeq = chordOrSeq;

        // allPitches     : flat list of every MIDI value, in order
        // chordSlots     : list of chords (arrays of MIDI values), evenly spaced
        // pitchEnvelopes : one step Envelope per voice, x in seconds (analysis)
        this.allPitches = [];
        this.chordSlots = [];
        this.pitchEnvelopes = [];
        this._parsePitch(pitch, pitchUnit, chordOrSeq);
        this._parseDynamic(dynamic, dynamicUnit, durSec);
        if (lyric !== null) this.setLyric(lyric);
    }

    _updateBeats() {
        const bpm = Number(this.data.bpm ?? 60);
        this.startTimeBeats = secToBeat(this.startTimeSec, bpm);
        this.durationBeats = secToBeat(this.durationSec, bpm);
        this.endTimeBeats = this.startTimeBeats + this.durationBeats;
    }

    static _toSeconds(startTime, duration, timeUnit, bpm) {
        if (timeUnit === "seconds" || timeUnit === "s") return [Number(startTime), Number(duration)];
        if (timeUnit === "beats" || timeUnit === "b") return [beatToSec(startTime, bpm), beatToSec(duration, bpm)];
        throw new Error(`Phonon: '${timeUnit}' is not a valid timeUnit. Use 's', 'seconds', 'b', or 'beats'.`);
    }

    // ------------------------------------------------------------------
    // Pitch parsing
    // ------------------------------------------------------------------

    /** One pitch value -> MIDI float (strings are always note names). */
    _toMidi(p, pitchUnit) {
        if (typeof p === "string") return spntom(p);
        if (pitchUnit === "midi") return Number(p);
        if (pitchUnit === "hz") return ftom(p, this.referenceA);
        if (pitchUnit === "spn") return spntom(String(p));
        throw new Error(`Phonon: unknown pitchUnit '${pitchUnit}'`);
    }

    _parsePitch(pitch, pitchUnit, chordOrSeq) {
        const toMidi = p => this._toMidi(p, pitchUnit);
        const sortChord = c => (this.autoSortChords ? [...c].sort((a, b) => a - b) : c);
        const flat = Array.isArray(pitch) ? pitch : [pitch];

        if (["seq", "s", "chord", "c"].includes(chordOrSeq)) {
            if (flat.some(Array.isArray)) {
                throw new Error("Phonon: nested pitch list passed to seq/chord mode. Use chordOrSeq='cs' for chord sequences.");
            }
            const pitches = flat.map(toMidi);
            this.chordSlots = chordOrSeq === "seq" || chordOrSeq === "s" ? pitches.map(p => [p]) : [sortChord(pitches)];
        } else if (chordOrSeq === "chordSeq" || chordOrSeq === "cs") {
            if (!Array.isArray(pitch)) throw new Error("Phonon: chordSeq requires a list of chords (nested list).");
            this.chordSlots = pitch.map(slot => (Array.isArray(slot) ? sortChord(slot.map(toMidi)) : [toMidi(slot)]));
        } else {
            throw new Error(`Phonon: unknown chordOrSeq '${chordOrSeq}'. Use 'seq'/'s', 'chord'/'c', or 'chordSeq'/'cs'.`);
        }

        this.allPitches = this.chordSlots.flat();
        if (!this.allPitches.length) throw new Error("Phonon: pitch is empty");
        this.pitchEnvelopes = this._voiceEnvelopes();
    }

    /** One step envelope per voice (voice v = v-th pitch of each chord), x in seconds. */
    _voiceEnvelopes() {
        const dur = this.durationSec;
        const slotDur = dur / this.chordSlots.length;
        const nVoices = Math.max(...this.chordSlots.map(c => c.length));
        const envs = [];
        for (let v = 0; v < nVoices; v++) {
            let pts = [];
            this.chordSlots.forEach((c, i) => { if (v < c.length) pts.push([i * slotDur, c[v]]); });
            if (pts.length === 1 || dur === 0) pts = [pts[0], [dur, pts[0][1]]];
            envs.push(new Envelope(pts, { curves: new Array(pts.length - 1).fill("step") }));
        }
        return envs;
    }

    // ------------------------------------------------------------------
    // Dynamic parsing
    // ------------------------------------------------------------------

    /**
     * number          -> data.dynamicdB (note-on velocity), flat envelopes.dynamic
     * array/Envelope  -> envelopes.dynamic (dB) and envelopes.aftertouch (velocity);
     *                    note-on velocity = first value. An array is spread evenly,
     *                    an Envelope keeps its shape and curves over the duration.
     * marking string  -> 'mf' (flat) or hairpin 'pp-mp' (time-varying), velocity scale
     * dynamicUnit 'midi': velocities 1..127 <-> 20..120 dB (exact round trip);
     * 'dB': the exporter's 0..100 dB -> 0..127 window.
     */
    _parseDynamic(dynamic, dynamicUnit, durationSec) {
        if (typeof dynamic === "string") {
            this.data.dynamicMarking = dynamic.trim();
            dynamic = parseDynamicMarking(dynamic);
            dynamicUnit = "midi";
        }
        let toDB, toVel;
        if (dynamicUnit === "midi") {
            toDB = v => scale(v, MIN_VEL, MAX_VEL, MIN_DB, MAX_DB);
            toVel = dB => scale(dB, MIN_DB, MAX_DB, MIN_VEL, MAX_VEL);
            Object.assign(this.data, { minDb: MIN_DB, maxDb: MAX_DB, minVelocity: MIN_VEL, maxVelocity: MAX_VEL });
        } else if (dynamicUnit === "dB") {
            toDB = Number;
            toVel = dB => scale(dB, 0, 100, 0, 127);
            for (const k of CAL_KEYS) delete this.data[k];
        } else {
            throw new Error(`Phonon: unknown dynamicUnit '${dynamicUnit}'`);
        }

        let pts, curves = null;
        if (dynamic instanceof Envelope) {
            const [sorted, c] = dynamic._sorted_points_and_curves();
            pts = sorted.map(([x, y]) => [x * durationSec, dynamic._y_from_norm(y, false)]);
            curves = c;
        } else if (Array.isArray(dynamic)) {
            if (!dynamic.length) throw new Error("Phonon: dynamic list is empty");
            const n = dynamic.length;
            pts = dynamic.map((v, i) => [n > 1 ? i * durationSec / (n - 1) : 0, Number(v)]);
        } else {
            pts = [[0, Number(dynamic)]];
        }

        const timeVarying = pts.length > 1;
        if (!timeVarying) pts = [pts[0], [durationSec, pts[0][1]]];
        const dBPts = pts.map(([t, v]) => [t, toDB(v)]);

        this.data.dynamicdB = dBPts[0][1];
        this.envelopes.dynamic = new Envelope(dBPts, { autosort: false, curves });
        if (timeVarying) {
            this.envelopes.aftertouch = new Envelope(dBPts.map(([t, dB]) => [t, toVel(dB)]), { autosort: false, curves });
        } else {
            delete this.envelopes.aftertouch;
        }
    }

    // ------------------------------------------------------------------
    // Pitch selection
    // ------------------------------------------------------------------

    /** 'all', 'lowest', 'highest', 'mostCommon', 'leastCommon', 'chord' / 'allSet'. */
    calculatePitch(key = "all") {
        const counts = new Map();
        for (const p of this.allPitches) {
            const k = roundTo(p, 6);
            counts.set(k, (counts.get(k) || 0) + 1);
        }
        switch (key) {
            case "all": return [...this.allPitches];
            case "chord":
            case "allSet": return [...new Set(this.allPitches)].sort((a, b) => a - b);
            case "lowest": return [Math.min(...this.allPitches)];
            case "highest": return [Math.max(...this.allPitches)];
            case "mostCommon": {
                let best = null, n = -1;
                for (const [k, c] of counts) if (c > n) [best, n] = [k, c];
                return [best];
            }
            case "leastCommon": {
                let best = null, n = Infinity;
                for (const [k, c] of counts) if (c <= n) [best, n] = [k, c];
                return [best];
            }
            default: throw new Error(`Phonon.calculatePitch: unknown key '${key}'`);
        }
    }

    // ------------------------------------------------------------------
    // Glissando, markings, lyrics
    // ------------------------------------------------------------------

    /** Glissando from startPitch to endPitch: anchor note + moving pitchwheel. */
    glissando(startPitch, endPitch, pitchUnit = null) {
        const unit = pitchUnit || this.pitchUnit;
        const startMidi = this._toMidi(startPitch, unit);
        const endMidi = this._toMidi(endPitch, unit);
        const anchor = roundHalfEven(startMidi);
        this.data.pitchMidi = anchor;
        this.data.pitchwheel = [startMidi - anchor, endMidi - anchor];
        this.data.glissandoMidi = [startMidi, endMidi];
    }

    /** Re-set the dynamic from a marking or hairpin; null only clears the label. */
    setDynamicMarking(text) {
        if (text === null) { delete this.data.dynamicMarking; return; }
        this._parseDynamic(text, "midi", this.durationSec);
    }

    getDynamicMarking() { return this.data.dynamicMarking ?? null; }

    /** Lyric on the first resolved note (offsetSec from its start); null clears it. */
    setLyric(text, offsetSec = 0) {
        if (text === null) { delete this.data.lyric; delete this.data.lyricOffsetSec; return; }
        this.data.lyric = String(text);
        this.data.lyricOffsetSec = Number(offsetSec);
    }

    getLyric() { return this.data.lyric ?? null; }

    // ------------------------------------------------------------------
    // Quantisation
    // ------------------------------------------------------------------

    /** Snap this note's absolute start and end to `grid` as one event;
        earlier unfolded leaves are dropped (unfold runs again on export). */
    quantiseTime(grid, parentalStartSec = 0) {
        this.children = this.children.filter(c => c instanceof Phonon);
        for (const c of this.children) c.quantiseTime(grid, parentalStartSec + this.startTimeSec);
        const start = Number(grid.quantise(parentalStartSec + this.startTimeSec));
        const end = Number(grid.quantise(parentalStartSec + this.endTimeSec));
        this.startTimeSec = start - parentalStartSec;
        this.setDuration(Math.max(end, start) - start);
        this._updateBeats();
    }

    // ------------------------------------------------------------------
    // Unfold
    // ------------------------------------------------------------------

    _leaf(startSec, durSec, pitchMidi, pitchwheel = null) {
        const anchor = roundHalfEven(pitchMidi);
        const diff = pitchMidi - anchor;
        return new TemporalObject(startSec, durSec, null, { data: {
            pitchMidi: anchor,
            pitchwheel: pitchwheel ? [...pitchwheel] : [diff, diff],
            dynamicdB: Number(this.data.dynamicdB ?? 80),
            bpm: Number(this.data.bpm ?? 60),
            ticksPerBeat: Math.trunc(this.data.ticksPerBeat ?? 480),
        } });
    }

    /**
     * Resolve pitch and dynamic into leaf children.
     *
     * noteSelectKey: null (default) follows chordOrSeq; 'seq' = one note per
     * slot (lowest voice); 'chordSeq' = every pitch of every slot; any
     * calculatePitch() key = those pitches held for the full duration.
     */
    unfold(noteSelectKey = null) {
        const key = noteSelectKey || DEFAULT_SELECT[this.chordOrSeq] || "seq";
        for (const c of this.children) if (c instanceof Phonon) c.unfold(noteSelectKey);

        const dur = this.durationSec;
        const slotDur = dur / this.chordSlots.length;
        let leaves;
        if ("glissandoMidi" in this.data) {
            leaves = [this._leaf(0, dur, this.data.pitchMidi, this.data.pitchwheel)];
        } else if (key === "seq") {
            leaves = this.chordSlots.flatMap((c, i) => (c.length ? [this._leaf(i * slotDur, slotDur, c[0])] : []));
        } else if (key === "chordSeq") {
            leaves = this.chordSlots.flatMap((c, i) => c.map(p => this._leaf(i * slotDur, slotDur, p)));
        } else {
            leaves = this.calculatePitch(key).map(p => this._leaf(0, dur, p));
        }

        if (leaves.length && "lyric" in this.data) leaves[0].annotations.push([this.data.lyricOffsetSec ?? 0, this.data.lyric]);
        const cal = Object.fromEntries(CAL_KEYS.filter(k => k in this.data).map(k => [k, this.data[k]]));
        const passthrough = Object.fromEntries(Object.entries(this.envelopes).filter(([k]) => k !== "pitchwheel" && k !== "dynamic"));
        for (const leaf of leaves) {
            Object.assign(leaf.data, cal);
            // full-duration notes carry the CC / aftertouch envelopes and the marking
            if (Math.abs(leaf.startTimeSec) < 1e-9 && Math.abs(leaf.durationSec - dur) < 1e-9) {
                Object.assign(leaf.envelopes, passthrough);
                if ("dynamicMarking" in this.data) leaf.data.dynamicMarking = this.data.dynamicMarking;
            }
        }
        this.children = this.children.filter(c => c instanceof Phonon).concat(leaves);
        this._refresh();
    }

    /** unfold(), then the playable notes (see noteEvents()). */
    toEvents(noteSelectKey = null) {
        this.unfold(noteSelectKey);
        return noteEvents(this);
    }

    toString() {
        const f = x => x.toFixed(3);
        return `Phonon(id=${this.id}, start=${f(this.startTimeSec)}s, dur=${f(this.durationSec)}s, ` +
               `bpm=${this.data.bpm}, chordOrSeq=${this.chordOrSeq}, ` +
               `pitches=${JSON.stringify([...new Set(this.allPitches.map(p => roundTo(p, 3)))].sort((a, b) => a - b))}, ` +
               `voices=${this.pitchEnvelopes.length}, envelopes=${JSON.stringify(Object.keys(this.envelopes))}, ` +
               `dynamicMark=${JSON.stringify(this.data.dynamicMarking ?? null)}, lyric=${JSON.stringify(this.data.lyric ?? null)}, ` +
               `children=${this.children.length})`;
    }
}

if (typeof exports !== "undefined") Object.assign(exports, { Phonon, noteEvents, velocityOf });
