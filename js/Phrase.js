/*
Phrase.js — JavaScript port of GreasyPidgin/Phrase.py

A polyphonic structure from a palette of elements:
  elements : { index: TemporalObject | null }   index 0 is always a rest
  voices   : { name: Envelope }   step functions of (time, elementIndex)
             breakpoints, time in timeUnit (seconds or beats), relative
             to the Phrase start; each slot lasts until the next breakpoint
             (the last one: the element's own duration, else one beat).

    Max:   var Phrase = require("Phrase").Phrase;
    Node:  const { Phrase } = require("./Phrase");

    const p = new Phrase(0, { 0: null, 1: new Phonon(0, 1, "c4"), 2: new Phonon(0, 1, "e4") },
                         { soprano: new Envelope([[0, 1], [1, 2], [2, 0]]) }, { bpm: 120 });
    p.toEvents();
*/

const load = name => { try { return require("./" + name); } catch (e) { return require(name); } };
const { TemporalObject } = load("TemporalObject");
const { Phonon, noteEvents } = load("Phonon");
const { Gesture } = load("Gesture");

class Phrase extends TemporalObject {
    constructor(startTimeSec = 0, elements = null, voices = null, { bpm = 60, timeUnit = "seconds", ticksPerBeat = 480 } = {}) {
        super(startTimeSec, 0, null, { data: { bpm, ticksPerBeat } });
        if (!["seconds", "s", "beats", "b"].includes(timeUnit)) {
            throw new Error(`Phrase: '${timeUnit}' is not a valid timeUnit. Use 's', 'seconds', 'b', or 'beats'.`);
        }
        this.elements = { ...(elements || { 0: null }) };
        this.voices = { ...(voices || {}) };
        this.bpm = Number(bpm);
        this.timeUnit = timeUnit;
        if (!(0 in this.elements)) this.elements[0] = null;
        if (Object.keys(this.voices).length) this._assemble();
    }

    /** [timeSec, elementIndex] breakpoints of a voice envelope. */
    _readBreakpoints(env) {
        if (!env.points.length || env.y_range === null) return [];
        const [yMin, yMax] = env.y_range, [xMin, xMax] = env.x_range;
        const ySpan = yMax !== yMin ? yMax - yMin : 1, xSpan = xMax !== xMin ? xMax - xMin : 1;
        const toSec = this.timeUnit === "beats" || this.timeUnit === "b" ? t => t * 60 / this.bpm : Number;
        return [...env.points].sort((a, b) => a[0] - b[0])
            .map(([xn, yn]) => [toSec(xMin + xn * xSpan), Math.round(yMin + yn * ySpan)]);
    }

    _assemble() {
        this.children = [];
        let latestEnd = 0;
        for (const env of Object.values(this.voices)) {
            const bps = this._readBreakpoints(env);
            bps.forEach(([timeSec, index], i) => {
                const elem = index !== 0 ? this.elements[index] ?? null : null;
                const next = i + 1 < bps.length ? bps[i + 1][0]
                    : timeSec + (elem && elem.durationSec > 0 ? elem.durationSec : 60 / this.bpm);
                const slotDur = next - timeSec;
                if (!elem) { latestEnd = Math.max(latestEnd, next); return; }
                // clone, override start and duration; containers are stretched to fit,
                // a Phonon drops old leaves (rebuilt on unfold)
                const child = elem.clone();
                child.startTimeSec = timeSec;
                if (child instanceof Phonon) child.children = child.children.filter(c => c instanceof Phonon);
                if (child.children.length && child.durationSec > 0) child.stretchTime(slotDur / child.durationSec);
                child.setDuration(slotDur);
                if (child instanceof Phonon) child._updateBeats();
                child.data.bpm ??= this.bpm;
                child.data.ticksPerBeat ??= this.data.ticksPerBeat;
                this.children.push(child);
                latestEnd = Math.max(latestEnd, timeSec + slotDur);
            });
        }
        if (latestEnd > 0) this.setDuration(latestEnd);
    }

    _unfoldAll(noteSelectKey = null) {
        for (const c of this.children) {
            if (c instanceof Phrase || c instanceof Gesture) c._unfoldAll(noteSelectKey);
            else if (c instanceof Phonon) c.unfold(noteSelectKey);
        }
    }

    /** Unfold everything, then the playable notes (see noteEvents()). */
    toEvents(noteSelectKey = null) {
        this._unfoldAll(noteSelectKey);
        return noteEvents(this);
    }

    toString() {
        return `Phrase(id=${this.id}, start=${this.startTimeSec.toFixed(3)}s, dur=${this.durationSec.toFixed(3)}s, ` +
               `bpm=${this.bpm}, elements=${JSON.stringify(Object.keys(this.elements))}, voices=${JSON.stringify(Object.keys(this.voices))}, children=${this.children.length})`;
    }
}

if (typeof exports !== "undefined") exports.Phrase = Phrase;
