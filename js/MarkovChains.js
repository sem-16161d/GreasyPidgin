/*
MarkovChains.js — JavaScript port of GreasyPidgin/MarkovChains.py

Markov chains of any order. A state is an array of the last `order`
symbols; symbols can be numbers, strings, null (e.g. a rest) or anything
JSON can describe (states are compared by their JSON text).

    Max:   var M = require("MarkovChains");
    Node:  const { MarkovChain, MarkovRule, MarkovRules } = require("./MarkovChains");

    const chain = new MarkovChain();
    chain.generateRulesFromList([60, 62, 64, 62, 60, 67, 64, 62], { order: 2 });
    chain.getNElements({ seed: [60, 62], n: 16 });
*/

const asState = x => (Array.isArray(x) ? [...x] : [x]);
const keyOf = state => JSON.stringify(asState(state));

class MarkovRule {
    /** element: current state (a single symbol is wrapped); weights are normalised. */
    constructor(element, nextElements, weights) {
        this.element = asState(element);
        this.order = this.element.length;
        if (nextElements.length !== weights.length) {
            throw new Error(`MarkovRule: nextElements (${nextElements.length}) and weights (${weights.length}) must have the same length`);
        }
        if (!nextElements.length) throw new Error("MarkovRule: nextElements cannot be empty");
        const total = weights.reduce((a, b) => a + b, 0);
        if (!(total > 0)) throw new Error("Weights must sum to a positive number");
        this.nextElements = [...nextElements];
        this.weights = weights.map(w => w / total);
    }

    /** One next symbol, drawn by weight. */
    sample() {
        let r = Math.random();
        for (let i = 0; i < this.weights.length; i++) {
            if ((r -= this.weights[i]) < 0) return this.nextElements[i];
        }
        return this.nextElements[this.nextElements.length - 1];
    }

    toString() {
        return `MarkovRule(${JSON.stringify(this.element)} → ` +
               this.nextElements.map((ne, i) => `${JSON.stringify(ne)}:${this.weights[i].toFixed(4)}`).join(" | ") + ")";
    }
}

class MarkovRules {
    /** All rules need the same order; continuity (every reachable state has a rule) is checked. */
    constructor(rules = []) {
        this.rules = new Map();    // JSON key -> MarkovRule
        this.order = null;
        this.elements = [];
        this.flatElements = new Set();
        this.missingRules = [];
        this.isContinuous = true;
        for (const mr of rules) {
            if (!(mr instanceof MarkovRule)) throw new TypeError("MarkovRules: expected MarkovRule");
            if (this.order === null) this.order = mr.order;
            else if (mr.order !== this.order) throw new Error(`MarkovRules: order mismatch — expected ${this.order}, got ${mr.order} for ${JSON.stringify(mr.element)}`);
            const key = keyOf(mr.element);
            if (this.rules.has(key)) throw new Error(`MarkovRules: duplicate rule for ${key}`);
            this.rules.set(key, mr);
            this.elements.push(mr.element);
            [...mr.element, ...mr.nextElements].forEach(s => this.flatElements.add(s));
        }
        if (this.rules.size) this.isContinuous = this._checkContinuity();
    }

    _checkContinuity() {
        const missing = new Map();
        for (const rule of this.rules.values()) {
            for (const next of rule.nextElements) {
                const state = [...rule.element.slice(1), next];
                if (!this.rules.has(keyOf(state))) missing.set(keyOf(state), state);
            }
        }
        this.missingRules = [...missing.values()];
        if (this.missingRules.length) {
            const msg = `MarkovRules: chain is not continuous — missing rules for: ${JSON.stringify(this.missingRules)}`;
            if (typeof post === "function") post(msg + "\n"); else console.log(msg);
            return false;
        }
        return true;
    }

    has(state) { return this.rules.has(keyOf(state)); }

    get(state) { return this.rules.get(keyOf(state)); }

    get size() { return this.rules.size; }

    toString() {
        return `MarkovRules(order=${this.order}, numRules=${this.rules.size}, isContinuous=${this.isContinuous})\n` +
               [...this.rules.values()].map(r => "  " + r).join("\n");
    }
}

class MarkovChain {
    constructor({ rules = null, seed = null, order = 1, n = 0 } = {}) {
        this.rules = rules || new MarkovRules();
        this.seed = seed;
        this.order = this.rules.order !== null ? this.rules.order : order;
        this.n = n;
    }

    /** Next symbol from a state, or undefined if no rule exists (null can be a real symbol). */
    nextElement(state) {
        if (!this.rules.has(state)) {
            const msg = `MarkovChain.nextElement: no rule for state ${keyOf(state)}`;
            if (typeof post === "function") post(msg + "\n"); else console.log(msg);
            return undefined;
        }
        return this.rules.get(state).sample();
    }

    /** The seed symbols followed by n generated ones (stops early if the chain breaks). */
    getNElements({ seed = null, n = null, order = null } = {}) {
        seed = seed !== null ? seed : this.seed;
        n = n !== null ? n : this.n;
        order = order !== null ? order : this.order;
        if (seed === null) throw new Error("MarkovChain.getNElements: no seed provided");
        if (n < 1) throw new RangeError(`MarkovChain.getNElements: n must be >= 1, got ${n}`);
        if (order < 1) throw new RangeError(`MarkovChain.getNElements: order must be >= 1, got ${order}`);
        const out = asState(seed);
        for (let i = 0; i < n; i++) {
            const state = out.slice(-order);
            if (!this.rules.has(state)) {
                const msg = `MarkovChain.getNElements: chain broken at state ${keyOf(state)}, stopping early`;
                if (typeof post === "function") post(msg + "\n"); else console.log(msg);
                break;
            }
            out.push(this.rules.get(state).sample());
        }
        return out;
    }

    /** Learn transition counts from a sequence; wrap connects the end to the start. */
    generateRulesFromList(list, { order = 1, wrap = true } = {}) {
        if (list.length < order + 1) {
            throw new Error(`MarkovChain.generateRulesFromList: sequence too short (length ${list.length}) for order ${order} — need at least ${order + 1}`);
        }
        const seq = wrap ? [...list, ...list.slice(0, order)] : [...list];
        const stateMap = new Map();   // key -> [state, Map(nextKey -> [symbol, count])]
        for (let i = 0; i + order < seq.length; i++) {
            const state = seq.slice(i, i + order), next = seq[i + order];
            if (!stateMap.has(keyOf(state))) stateMap.set(keyOf(state), [state, new Map()]);
            const counts = stateMap.get(keyOf(state))[1], nk = JSON.stringify(next);
            counts.set(nk, [next, (counts.get(nk)?.[1] || 0) + 1]);
        }
        this.rules = new MarkovRules([...stateMap.values()].map(([state, counts]) =>
            new MarkovRule(state, [...counts.values()].map(c => c[0]), [...counts.values()].map(c => c[1]))));
        this.order = order;
    }

    toString() { return `MarkovChain(seed=${JSON.stringify(this.seed)}, order=${this.order}, n=${this.n}, rules=${this.rules.size})`; }
}

if (typeof exports !== "undefined") Object.assign(exports, { MarkovRule, MarkovRules, MarkovChain });
