/*
TemporalObject.js — JavaScript port of GreasyPidgin/TemporalObject.py

A TemporalObject is a time interval that can contain other TemporalObjects
and carry arbitrary payload data and time-varying envelopes.

It knows nothing about export formats, MIDI, audio, video, or pitch.
All domain-specific data lives in `data`. Exporters interpret it.

    TemporalObject
        startTimeSec, durationSec, endTimeSec   — time
        children: TemporalObject[]               — structure (relative times)
        envelopes: {name: Envelope}              — time-varying behaviour
        annotations: [offsetSec, text][]         — time-stamped text labels
        data: {}                                 — everything else

Runs in Max 9 [v8] and in Node.

    Max:   var TemporalObject = require("TemporalObject").TemporalObject;
    Node:  const { TemporalObject } = require("./TemporalObject");

Example
-------
    // A MIDI note
    new TemporalObject(0, 2, null, { data: { pitchMidi: 60, dynamicdB: 80, bpm: 120 } });

    // A container: children times are relative to it
    const g = new TemporalObject(10, 0, [new TemporalObject(0, 1), new TemporalObject(1, 1)]);
    g.flatten();   // copies of the leaves at absolute times 10 and 11
*/

// Deep copy that keeps class prototypes (structuredClone would turn an
// Envelope into a plain object) and keeps shared references shared.
function deepCopy(value, memo = new Map()) {
    if (value === null || typeof value !== "object") return value;
    if (memo.has(value)) return memo.get(value);
    let out;
    if (Array.isArray(value)) {
        out = [];
        memo.set(value, out);
        for (const v of value) out.push(deepCopy(v, memo));
        return out;
    }
    // Set / Map subclasses (e.g. Grid) need the built-in's internal storage,
    // so they are created via Reflect.construct without running their constructor
    if (value instanceof Map) {
        out = Reflect.construct(Map, [], value.constructor);
        memo.set(value, out);
        for (const [k, v] of value) out.set(deepCopy(k, memo), deepCopy(v, memo));
    } else if (value instanceof Set) {
        out = Reflect.construct(Set, [], value.constructor);
        memo.set(value, out);
        for (const v of value) out.add(deepCopy(v, memo));
    } else {
        out = Object.create(Object.getPrototypeOf(value));
        memo.set(value, out);
    }
    for (const k of Object.keys(value)) out[k] = deepCopy(value[k], memo);
    return out;
}

class TemporalObject {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }

    static _allocateId() {
        // one counter on the base class, shared by every subclass
        return TemporalObject._nextId++;
    }

    constructor(startTimeSec = 0, durationSec = 0, children = null,
                { envelopes = null, annotations = null, data = null } = {}) {
        this.id = TemporalObject._allocateId();
        this.startTimeSec = Number(startTimeSec);
        this.setDuration(durationSec);
        this.envelopes   = { ...(envelopes || {}) };
        this.annotations = [...(annotations || [])];
        this.data        = { ...(data || {}) };
        this.children    = [...(children || [])];
        this._refresh();
    }

    // ------------------------------------------------------------------
    // Internal bookkeeping
    // ------------------------------------------------------------------

    setDuration(durationSec) {
        this.durationSec = Number(durationSec);
        this.endTimeSec  = this.startTimeSec + this.durationSec;
    }

    /** Latest absolute end time among this node's leaves. */
    _leafEnd(parentalStartSec) {
        if (!this.children.length) return parentalStartSec + this.endTimeSec;
        return Math.max(...this.children.map(c => c._leafEnd(parentalStartSec + this.startTimeSec)));
    }

    /** Recompute endTimeSec / durationSec from the leaves (containers only). */
    _refresh() {
        if (this.children.length) this.setDuration(this._leafEnd(0) - this.startTimeSec);
    }

    // ------------------------------------------------------------------
    // Identity / copying
    // ------------------------------------------------------------------

    /** Deep copy with fresh ids, including every subclass property. */
    clone() {
        const obj = Object.create(Object.getPrototypeOf(this));
        const memo = new Map();
        for (const k of Object.keys(this)) {
            if (k !== "children") obj[k] = deepCopy(this[k], memo);
        }
        obj.id = TemporalObject._allocateId();
        obj.children = this.children.map(c => c.clone());
        return obj;
    }

    // ------------------------------------------------------------------
    // Container interface
    // ------------------------------------------------------------------

    isContainer() {
        return this.children.length > 0;
    }

    /** Append a deep copy of `child`. Child time is relative to this. */
    addChild(child) {
        if (!(child instanceof TemporalObject)) {
            throw new TypeError(`addChild: expected TemporalObject, got ${child?.constructor?.name ?? typeof child}`);
        }
        this.children.push(child.clone());
        this._refresh();
    }

    /** Drop children whose duration is at or below `thresholdSec`. */
    removeShortChildren(thresholdSec = 0.01) {
        this.children = this.children.filter(c => c.durationSec > thresholdSec);
        this._refresh();
    }

    sortChildren() {
        this.children.sort((a, b) => a.startTimeSec - b.startTimeSec || a.durationSec - b.durationSec);
    }

    /** Remove all children; the node keeps its current duration. */
    clear() {
        this.children.length = 0;
    }

    // ------------------------------------------------------------------
    // Time operations
    // ------------------------------------------------------------------

    /** Shift start and end by `deltaSec` (children move along, their times are relative). */
    shiftTime(deltaSec) {
        this.startTimeSec += Number(deltaSec);
        this.endTimeSec   += Number(deltaSec);
    }

    /** Scale duration by `factor`; children's starts and durations scale with it. */
    stretchTime(factor) {
        factor = Number(factor);
        for (const c of this.children) {
            c.startTimeSec *= factor;
            c.stretchTime(factor);
        }
        this.setDuration(this.durationSec * factor);
    }

    // ------------------------------------------------------------------
    // Overlap helpers
    // ------------------------------------------------------------------

    overlaps(other) {
        return this.startTimeSec < other.endTimeSec && other.startTimeSec < this.endTimeSec;
    }

    /**
     * Trim overlapping adjacent children so none overlap. A child that
     * would end up shorter than `minDurationSec` is cut to that length
     * instead and the next child is pushed later (or dropped if too short).
     */
    resolveChildOverlaps(minDurationSec = 0) {
        this.sortChildren();
        const minDur = Number(minDurationSec);
        let i = 0;
        while (i < this.children.length - 1) {
            const a = this.children[i];
            const b = this.children[i + 1];
            if (a.endTimeSec > b.startTimeSec) {
                a.setDuration(Math.max(b.startTimeSec - a.startTimeSec, minDur));
                if (a.endTimeSec > b.startTimeSec) {            // b must make room
                    const cut = a.endTimeSec - b.startTimeSec;
                    b.startTimeSec = a.endTimeSec;
                    b.setDuration(b.durationSec - cut);
                    if (b.durationSec <= 0 || b.durationSec < minDur) {
                        this.children.splice(i + 1, 1);
                        continue;
                    }
                }
            }
            i++;
        }
        this._refresh();
    }

    // ------------------------------------------------------------------
    // Quantisation
    // ------------------------------------------------------------------

    /** Snap the absolute start/end times of all leaves to `grid` (anything with quantise(number)). */
    quantiseTime(grid, parentalStartSec = 0) {
        if (this.children.length) {
            for (const child of this.children) child.quantiseTime(grid, parentalStartSec + this.startTimeSec);
            this._refresh();
            return;
        }
        const start = Number(grid.quantise(parentalStartSec + this.startTimeSec));
        const end   = Number(grid.quantise(parentalStartSec + this.endTimeSec));
        this.startTimeSec = start - parentalStartSec;
        this.setDuration(Math.max(end, start) - start);
    }

    // ------------------------------------------------------------------
    // Flattening  (non-mutating)
    // ------------------------------------------------------------------

    /** Return absolute-time copies of all leaf descendants. Nothing is mutated. */
    flatten(parentalStartSec = 0) {
        if (!this.children.length) {
            const leaf = this.clone();
            leaf.shiftTime(parentalStartSec);
            return [leaf];
        }
        const absStart = this.startTimeSec + parentalStartSec;
        return this.children.flatMap(child => child.flatten(absStart));
    }

    // ------------------------------------------------------------------
    // Export hook
    // ------------------------------------------------------------------

    /** Export via `exporter` (any object with export(temporalObject)). */
    export(exporter) {
        exporter.export(this);
    }

    // ------------------------------------------------------------------
    // Repr
    // ------------------------------------------------------------------

    toString() {
        let tail;
        if (this.children.length) {
            tail = `children=${this.children.length}`;
        } else {
            const keys = Object.keys(this.data);
            const preview = Object.fromEntries(keys.slice(0, 3).map(k => [k, this.data[k]]));
            if (keys.length > 3) preview["..."] = `(${keys.length} keys total)`;
            tail = `data=${JSON.stringify(preview)}`;
        }
        const f = x => x.toFixed(3);
        return `${this.constructor.name}(id=${this.id}, start=${f(this.startTimeSec)}, ` +
               `dur=${f(this.durationSec)}, end=${f(this.endTimeSec)}, ${tail})`;
    }
}

TemporalObject._nextId = 0;

for (const C of [TemporalObject]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") exports.TemporalObject = TemporalObject;
