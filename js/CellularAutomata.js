/*
CellularAutomata.js — JavaScript port of GreasyPidgin/CellularAutomata.py

Wolfram elementary cellular automata (1D, 2 states, 3-cell neighbourhood,
wrapping edges). Generations are stored in a Map {index: [0/1 cells]}.

    Max:   var CA = require("CellularAutomata");
    Node:  const { CellularAutomaton, CellularRules } = require("./CellularAutomata");

    const ca = new CellularAutomaton({ rules: CellularRules.elementaryWolfram(30) });
    ca.gen0fromSingleCell(32);
    ca.iterate(20);
    ca.printGenerations();
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { Envelope } = load("Envelope");

/** Integer -> binary digits, MSB first, padded to `size` (-1 = minimal width). */
function intToBinary(n, size = -1) {
    if (n < 0) throw new RangeError(`intToBinary: n must be >= 0, got ${n}`);
    const s = Math.trunc(n).toString(2);
    return [...(size > 0 ? s.padStart(size, "0") : s)].map(Number);
}

/** Binary digits (MSB first) -> integer. */
const binaryToInt = bits => bits.reduce((acc, b) => acc * 2 + Number(b), 0);

class CellularRules {
    constructor() {
        this.name = "nil";
        this.ruleType = "wolfram";
        this.dimensions = 1;
        this.numStates = 2;
        this.minVal = 0;
        this.maxVal = 1;
        this.lookup = {};   // "110" -> "1"
    }

    /** Wolfram elementary rule 0..255. */
    static elementaryWolfram(ruleNumber = 0) {
        if (!(ruleNumber >= 0 && ruleNumber <= 255)) throw new RangeError(`CellularRules.elementaryWolfram: ruleNumber must be 0–255, got ${ruleNumber}`);
        const obj = new CellularRules();
        obj.name = ruleNumber;
        const bits = ruleNumber.toString(2).padStart(8, "0");
        for (let i = 0; i < 8; i++) obj.lookup[(7 - i).toString(2).padStart(3, "0")] = bits[i];
        return obj;
    }

    /** Next state for a neighbourhood string like "010". */
    apply(neighbourhood) {
        if (this.ruleType !== "wolfram") throw new Error(`CellularRules.apply: ruleType '${this.ruleType}' not implemented`);
        return Number(this.lookup[neighbourhood]);
    }

    toString() { return `CellularRule(name=${this.name}, type=${this.ruleType}, lookup=${JSON.stringify(this.lookup)})`; }
}

class CellularAutomaton {
    constructor({ rules = null, dimension = 1, gen0 = null, neighbourhoodType = "moore" } = {}) {
        this.rules = rules || new CellularRules();
        this.dimension = dimension;
        this.gen0 = gen0 ? [...gen0] : [0];
        this.neighbourhoodType = neighbourhoodType;
        this.generations = new Map([[0, [...this.gen0]]]);
        if (dimension < 1) throw new RangeError(`CellularAutomaton: dimension must be >= 1, got ${dimension}`);
        const gen0Dims = Array.isArray(this.gen0[0]) ? 2 : 1;
        if (!(dimension === this.rules.dimensions && dimension === gen0Dims)) {
            throw new Error(`CellularAutomaton: dimension mismatch — dimension=${dimension}, rules.dimensions=${this.rules.dimensions}, gen0 dims=${gen0Dims}`);
        }
    }

    _setGen0(bits) {
        this.gen0 = bits;
        this.generations = new Map([[0, [...bits]]]);
    }

    /** gen0 from the binary digits of n (padded to maxNumCells, -1 = minimal width). */
    gen0fromInteger(n, maxNumCells = -1) { this._setGen0(intToBinary(n, maxNumCells)); }

    /** One active cell (default: in the middle) among `size` cells. */
    gen0fromSingleCell(size = 32, position = null) {
        const bits = new Array(size).fill(0);
        bits[position === null ? size >> 1 : position] = 1;
        this._setGen0(bits);
    }

    _lastGenerationKey() { return Math.max(...this.generations.keys()); }

    /** One step from generation fromKey (edges wrap). */
    elementaryWolframStep(fromKey) {
        const last = this.generations.get(fromKey), n = last.length;
        this.generations.set(fromKey + 1, last.map((cur, i) => this.rules.apply(`${last[(i - 1 + n) % n]}${cur}${last[(i + 1) % n]}`)));
    }

    /** numIterations steps from startIndex (default: the latest); later generations are recomputed. */
    iterate(numIterations, { startIndex = null } = {}) {
        if (!Object.keys(this.rules.lookup).length) {
            throw new Error("CellularAutomaton.iterate: no rule set, use e.g. new CellularAutomaton({ rules: CellularRules.elementaryWolfram(30) })");
        }
        let fromKey = startIndex === null ? this._lastGenerationKey() : startIndex;
        if (!this.generations.has(fromKey)) {
            throw new RangeError(`CellularAutomaton.iterate: ${startIndex} not in generations ${JSON.stringify([...this.generations.keys()])}`);
        }
        for (const k of [...this.generations.keys()]) if (k > fromKey) this.generations.delete(k);
        if (this.rules.ruleType !== "wolfram") throw new Error(`CellularAutomaton.iterate: ruleType '${this.rules.ruleType}' not implemented`);
        for (let i = 0; i < numIterations; i++) this.elementaryWolframStep(fromKey++);
    }

    _sortedKeys() { return [...this.generations.keys()].sort((a, b) => a - b); }

    /** Envelope with one breakpoint per generation: x = index, y = cells read as a binary number. */
    generationsToEnvelope() {
        return new Envelope(this._sortedKeys().map(k => [k, binaryToInt(this.generations.get(k))]));
    }

    /** All generations as one flat array. */
    concatenateGenerations() { return this._sortedKeys().flatMap(k => this.generations.get(k)); }

    /** All generations as an array of rows. */
    generationsAsArray() { return this._sortedKeys().map(k => [...this.generations.get(k)]); }

    /** Print all generations as text (Max console / Node) and return the string. */
    printGenerations(on = "█", off = "·") {
        const text = this._sortedKeys().map(k => `${String(k).padStart(4)} | ${this.generations.get(k).map(c => (c ? on : off)).join("")}`).join("\n");
        if (typeof post === "function") post(text + "\n"); else console.log(text);
        return text;
    }

    toString() {
        return `CellularAutomaton(rule=${this.rules.name} (${this.rules.ruleType}), gen0 size=${this.gen0.length}, ` +
               `generations=${this.generations.size} (0 → ${this._lastGenerationKey()}))`;
    }
}

if (typeof exports !== "undefined") Object.assign(exports, { CellularRules, CellularAutomaton, intToBinary, binaryToInt });
