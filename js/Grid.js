/*
Grid.js — JavaScript port of GreasyPidgin/Grid.py

A grid is a Set of numbers with helper methods: quantising, sieving,
sampling, and SuperCollider-style constructors (series, geom, fib, ...).
Like any Set it drops duplicates, so Grid.fill(5, 7) has a single value.

Runs in Max 9 [v8] and in Node.

    Max:   var Grid = require("Grid").Grid;
    Node:  const { Grid } = require("./Grid");

Example
-------
    const g = Grid.series(0, 0.5, 10);
    g.quantise(1.23);             // 1
    g.quantise([1.2, 2.3]);       // [1, 2.5]
    g.sieve(3, 1);                // Grid {0.5, 2, 3.5}
*/

// float noise (0.1 + 0.2 = 0.30000000000000004) is rounded away at this precision
const DECIMALS = 10;

const round = (x, decimals) => Number(x.toFixed(decimals));

class Grid extends Set {

    constructor(values = null) {
        super(values || []);
        this.latestSieveID = -1;
        this.sieved = {};
        this.sampled = {};
        this.sampleID = -1;
    }

    /** Grid values in ascending order. */
    sorted() {
        return [...this].sort((a, b) => a - b);
    }

    /** Snap a number (or each number in an array / Set) to the nearest grid value.
        On a tie the lower grid value wins. */
    quantise(value) {
        if (typeof value === "number") {
            let best = null;
            for (const x of this) {
                const d = Math.abs(x - value);
                const bd = best === null ? Infinity : Math.abs(best - value);
                if (d < bd || (d === bd && x < best)) best = x;
            }
            if (best === null) throw new Error("Grid.quantise: grid is empty");
            return best;
        }
        if (Array.isArray(value)) return value.map(v => this.quantise(v));
        if (value instanceof Set) return new Set([...value].map(v => this.quantise(v)));
        throw new Error(`Grid.quantise: Value ${value} of type ${typeof value} cannot be quantised!`);
    }

    /**
     * Keep every stepSize-th value from offsetIndex on (Xenakis sieve).
     *
     * discardOffset : drop the values before offsetIndex (default) or keep them
     * inverse       : keep the values the sieve would drop instead
     * reverse       : sieve from the highest value downwards
     * rotation      : shift the sieve's phase by this many positions
     *
     * The result is stored in this.sieved["sieved_<n>"] and also returned.
     */
    sieve(stepSize = 1, offsetIndex = 0,
          { discardOffset = true, inverse = false, reverse = false, rotation = 0 } = {}) {
        if (stepSize < 1) throw new RangeError(`Grid.sieve: stepSize must be >= 1, got ${stepSize}`);
        const values = this.sorted();
        if (reverse) values.reverse();
        const head = discardOffset ? [] : values.slice(0, offsetIndex);
        let tail = values.slice(offsetIndex);
        if (tail.length) {
            const r = ((rotation % tail.length) + tail.length) % tail.length;
            tail = tail.slice(r).concat(tail.slice(0, r));
        }
        const kept = tail.filter((v, i) => (i % stepSize === 0) !== inverse);

        const key = `sieved_${++this.latestSieveID}`;
        this.sieved[key] = {
            sievedGrid: new Grid(head.concat(kept)),
            stepSize, offsetIndex, discardOffset, inverse, reverse, rotation,
        };
        return this.sieved[key].sievedGrid;
    }

    /** Pick numElements distinct random values; stored in this.sampled["sampled_<n>"] and returned. */
    sample(numElements) {
        const pool = this.sorted();
        if (numElements < 0 || numElements > pool.length) {
            throw new RangeError("Grid.sample: sample larger than grid or negative");
        }
        for (let i = 0; i < numElements; i++) {                 // partial Fisher-Yates
            const j = i + Math.floor(Math.random() * (pool.length - i));
            [pool[i], pool[j]] = [pool[j], pool[i]];
        }
        const key = `sampled_${++this.sampleID}`;
        this.sampled[key] = pool.slice(0, numElements);
        return this.sampled[key];
    }

    // ------------------------------------------------------------------
    // Constructors (after SuperCollider's Array methods)
    // ------------------------------------------------------------------

    static _checkSize(size, minimum = 0) {
        if (size < minimum) throw new RangeError(`size must be >= ${minimum}`);
    }

    static _build(size, f) {
        return new this(Array.from({ length: size }, (_, i) => f(i)));
    }

    /** `size` values: funcOrValue(i) if it is a function, else the value repeated
        (a Set, so a repeated value gives a Grid of length 1). */
    static fill(size, funcOrValue) {
        this._checkSize(size);
        return this._build(size, typeof funcOrValue === "function" ? funcOrValue : () => funcOrValue);
    }

    /** Arithmetic series: start, start + step, ... (`size` values). */
    static series(start, step, size) {
        this._checkSize(size);
        return this._build(size, i => round(start + i * step, DECIMALS));
    }

    /** Geometric series: start * ratio**i (`size` values), optionally rounded. */
    static geom(start, ratio, size, { decimals = null } = {}) {
        this._checkSize(size);
        return this._build(size, i => {
            const v = start * ratio ** i;
            return decimals === null ? v : round(v, decimals);
        });
    }

    /** `size` points evenly spaced from start to end (end excluded if includeEnd=false). */
    static linearInterpolation(start, end, size, { decimals = null, includeEnd = true } = {}) {
        this._checkSize(size, 1);
        const steps = includeEnd ? Math.max(size - 1, 1) : size;
        const d = decimals === null ? DECIMALS : decimals;
        return this._build(size, i => round(start + (end - start) * i / steps, d));
    }

    /** `size` random values in [low, high]; distinct integers if integer=true. */
    static rand(size, low = 0, high = 1, { integer = false } = {}) {
        this._checkSize(size);
        if (integer) {
            const lo = Math.trunc(low);
            const ints = new Grid(Array.from({ length: Math.trunc(high) - lo + 1 }, (_, i) => lo + i));
            return new this(ints.sample(size));
        }
        return this._build(size, () => low + Math.random() * (high - low));
    }

    /** Fibonacci-style sequence of `size` values starting a, b (duplicates collapse). */
    static fib(size, a = 0, b = 1) {
        this._checkSize(size);
        const values = [a, b].slice(0, size);
        while (values.length < size) values.push(values[values.length - 1] + values[values.length - 2]);
        return new this(values);
    }

    /**
     * Deltas between consecutive sorted values. The first entry is 0, or the
     * first value itself with copyFirst=true (SuperCollider's differentiate).
     *
     *     new Grid([3, 7, 10, 15]).differentiate()   // [0, 4, 3, 5]
     */
    differentiate(copyFirst = false) {
        const srt = this.sorted();
        if (!srt.length) return [];
        return [copyFirst ? srt[0] : 0, ...srt.slice(1).map((v, i) => v - srt[i])];
    }

    toString() {
        const name = this.constructor.name;
        if (!this.size) return `${name}(size=0)`;
        const srt = this.sorted();
        return `${name}(size=${srt.length}, range=(${srt[0]}, ${srt[srt.length - 1]}), preview=[${srt.join(", ")}])`;
    }
}

if (typeof exports !== "undefined") exports.Grid = Grid;
