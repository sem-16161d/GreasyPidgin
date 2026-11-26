/*
LSystem.js — JavaScript port of GreasyPidgin/LSystem.py

Lindenmayer systems: ProductionRule (predecessor -> successor), ProductionRules
(constants get identity rules automatically), LSystem (iterates and stores
every generation) and Turtle (turns a generation into line segments).

    Max:   var L = require("LSystem");   L.LSystem.fromStrings("F++F++F", { F: "F-F++F-F" })
    Node:  const { LSystem, Turtle } = require("./LSystem");

    const ls = LSystem.fromStrings("F++F++F", { F: "F-F++F-F" });
    ls.iterate(3);
    const svg = Turtle.toSvg(ls.interpret({ angle: 60 }));

Symbols can be strings, numbers or objects (compared by identity).
Differences from the Python version: Turtle options are an options object;
Turtle.plot() (matplotlib) does not exist, use Turtle.toSvg().
*/

const flatten = x => (Array.isArray(x) ? x.flatMap(flatten) : [x]);
const show = s => (typeof s === "string" ? `'${s}'` : typeof s === "object" ? (s.constructor?.name ?? "object") : String(s));

class ProductionRule {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }
    /** predecessor -> successor (a single value is wrapped in an array). */
    constructor(predecessor, successor) {
        this.predecessor = predecessor;
        this.successor = Array.isArray(successor) ? [...successor] : [successor];
    }

    toString() { return `ProductionRule(${show(this.predecessor)} → [${this.successor.map(show).join(", ")}])`; }
}

class ProductionRules {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }
    /** Duplicate predecessors are rejected; symbols that only appear in successors
        become constants with identity rules. */
    constructor(productionRules = []) {
        this.rules = [];
        this.predecessors = [];
        this.lookup = new Map();
        for (const pr of productionRules) {
            if (!(pr instanceof ProductionRule)) throw new TypeError(`ProductionRules: expected ProductionRule, got ${typeof pr}`);
            if (this.lookup.has(pr.predecessor)) throw new Error(`ProductionRules: duplicate predecessor ${show(pr.predecessor)}`);
            this.predecessors.push(pr.predecessor);
            this.rules.push(pr);
            this.lookup.set(pr.predecessor, pr.successor);
        }
        const successorSymbols = new Set(flatten(this.rules.map(r => r.successor)));
        this.constants = new Set([...successorSymbols].filter(s => !this.lookup.has(s)));
        for (const c of [...this.constants].sort((a, b) => (String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0))) {
            const rule = new ProductionRule(c, [c]);
            this.predecessors.push(c);
            this.rules.push(rule);
            this.lookup.set(c, rule.successor);
        }
        this.alphabet = new Set(this.predecessors);
    }

    /** Rules from strings, one character per symbol: fromStrings({ F: "F-F++F-F" }).
        Characters of extraSymbols without a rule (e.g. the axiom's) get identity rules. */
    static fromStrings(rules, extraSymbols = "") {
        const list = Object.entries(rules).map(([pred, succ]) => new ProductionRule(pred, typeof succ === "string" ? [...succ] : succ));
        const known = new Set(Object.keys(rules));
        for (const c of extraSymbols) {
            if (!known.has(c) && c.trim()) { list.push(new ProductionRule(c, [c])); known.add(c); }
        }
        return new ProductionRules(list);
    }

    toString() {
        return `ProductionRules(\n  alphabet  : ${[...this.alphabet].map(show).join(", ")}\n  constants : ${[...this.constants].map(show).join(", ")}\n` +
               `  rules:\n${this.rules.map(r => "  " + r).join("\n")}\n)`;
    }
}

class LSystem {
    /** axiom: array of symbols (a single value is wrapped); every symbol needs a rule. */
    constructor(axiom, productionRules) {
        if (!Array.isArray(axiom)) axiom = [axiom];
        if (!axiom.length) throw new Error("LSystem: axiom is empty");
        if (!(productionRules instanceof ProductionRules)) throw new TypeError("LSystem: expected ProductionRules");
        this.axiom = [...axiom];
        this.productionRules = productionRules;
        this.generations = new Map([[0, [...axiom]]]);
        const missing = axiom.filter(a => !productionRules.lookup.has(a));
        if (missing.length) {
            throw new Error(`LSystem: axiom symbols ${missing.map(show).join(", ")} have no production rule. ` +
                            `Known symbols: ${[...productionRules.lookup.keys()].map(show).join(", ")}`);
        }
    }

    /** LSystem.fromStrings("F++F++F", { F: "F-F++F-F" }) — one character per symbol, spaces ignored. */
    static fromStrings(axiom, rules) {
        const symbols = [...axiom].filter(c => c.trim());
        return new LSystem(symbols, ProductionRules.fromStrings(rules, symbols.join("")));
    }

    /** Draw a generation (default: the latest) with a Turtle or Turtle options. */
    interpret(turtleOrOptions = {}, generation = null) {
        const turtle = turtleOrOptions instanceof Turtle ? turtleOrOptions : new Turtle(turtleOrOptions);
        return turtle.run(generation === null ? this.currentGeneration() : this.generationAt(generation));
    }

    _lastGenerationKey() { return Math.max(...this.generations.keys()); }

    /** One rewriting step from the latest generation. */
    step() {
        const next = [];
        for (const symbol of this.currentGeneration()) {
            const succ = this.productionRules.lookup.get(symbol);
            if (succ === undefined) throw new Error(`LSystem.step: no rule for symbol ${show(symbol)}`);
            next.push(...succ);
        }
        this.generations.set(this._lastGenerationKey() + 1, next);
        return next;
    }

    /** numIterations steps (from the axiom with fromStart); returns the final generation. */
    iterate(numIterations, { fromStart = false } = {}) {
        if (fromStart) this.reset();
        for (let i = 0; i < numIterations; i++) this.step();
        return this.currentGeneration();
    }

    reset() { this.generations = new Map([[0, [...this.axiom]]]); }

    currentGeneration() { return this.generations.get(this._lastGenerationKey()); }

    generationAt(index) {
        if (!this.generations.has(index)) {
            throw new RangeError(`LSystem.generationAt: generation ${index} not computed yet. Available: 0–${this._lastGenerationKey()}`);
        }
        return this.generations.get(index);
    }

    lengths() { return Object.fromEntries([...this.generations].map(([k, v]) => [k, v.length])); }

    toString() {
        const cur = this.currentGeneration();
        return `LSystem(generation=${this._lastGenerationKey()}, length=${cur.length}, ` +
               `current=[${cur.slice(0, 12).map(show).join(", ")}]${cur.length > 12 ? "..." : ""})`;
    }
}

/**
 * Turtle graphics for L-System generations. Default symbols:
 *   F draw forward, f move, + left, - right, | turn around,
 *   [ push, ] pop, > step *= lengthScale, < step /= lengthScale
 * Other symbols are ignored. Each action option takes a list of symbols,
 * e.g. new Turtle({ draw: ["F", "A", "B"] }).
 */
class Turtle {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }
    constructor({
        angle = 90, stepLength = 1, lengthScale = 1, startPosition = [0, 0], startHeading = 90,
        draw = ["F"], move = ["f"], left = ["+"], right = ["-"], turnAround = ["|"],
        push = ["["], pop = ["]"], scaleUp = [">"], scaleDown = ["<"],
    } = {}) {
        if (lengthScale <= 0) throw new RangeError("Turtle: lengthScale must be > 0");
        Object.assign(this, { angle, stepLength, lengthScale, startPosition: [...startPosition], startHeading });
        this.actions = new Map();
        const actions = { draw, move, left, right, turnAround, push, pop, scaleUp, scaleDown };
        for (const [action, symbols] of Object.entries(actions)) {
            for (const sym of typeof symbols === "string" ? [symbols] : symbols) {
                if (this.actions.has(sym) && this.actions.get(sym) !== action) {
                    throw new Error(`Turtle: symbol '${sym}' is assigned to both '${this.actions.get(sym)}' and '${action}'`);
                }
                this.actions.set(sym, action);
            }
        }
    }

    /** Interpret symbols; returns { segments: [{ start, end, heading, depth, index, length }], bounds, maxDepth }. */
    run(symbols) {
        let [x, y] = this.startPosition;
        let heading = this.startHeading, step = this.stepLength, depth = 0, maxDepth = 0;
        const stack = [], segments = [], xs = [x], ys = [y];
        [...symbols].forEach((sym, i) => {
            switch (this.actions.get(sym)) {
                case "draw":
                case "move": {
                    const rad = heading * Math.PI / 180;
                    const nx = x + step * Math.cos(rad), ny = y + step * Math.sin(rad);
                    if (this.actions.get(sym) === "draw") segments.push({ start: [x, y], end: [nx, ny], heading, depth, index: i, length: step });
                    [x, y] = [nx, ny];
                    xs.push(x); ys.push(y);
                    break;
                }
                case "left": heading += this.angle; break;
                case "right": heading -= this.angle; break;
                case "turnAround": heading += 180; break;
                case "push": stack.push([x, y, heading, step]); maxDepth = Math.max(maxDepth, ++depth); break;
                case "pop":
                    if (!stack.length) throw new Error(`Turtle.run: unmatched '${sym}' at index ${i}`);
                    [x, y, heading, step] = stack.pop();
                    depth--;
                    break;
                case "scaleUp": step *= this.lengthScale; break;
                case "scaleDown": step /= this.lengthScale; break;
            }
        });
        if (stack.length) throw new Error(`Turtle.run: ${stack.length} unclosed branch(es) -- a pop symbol is missing`);
        return { segments, bounds: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], maxDepth };
    }

    /** SVG string of a run() result (y axis flipped so up is up). */
    static toSvg(result, { size = 600, margin = 10, stroke = "black", strokeWidth = 1, background = null } = {}) {
        const [x0, y0, x1, y1] = result.bounds;
        const scale = (size - 2 * margin) / Math.max(x1 - x0, y1 - y0, 1e-12);
        const w = (x1 - x0) * scale + 2 * margin, h = (y1 - y0) * scale + 2 * margin;
        const tx = x => (margin + (x - x0) * scale).toFixed(2), ty = y => (margin + (y1 - y) * scale).toFixed(2);
        const parts = [`<svg xmlns="http://www.w3.org/2000/svg" width="${w.toFixed(1)}" height="${h.toFixed(1)}" viewBox="0 0 ${w.toFixed(1)} ${h.toFixed(1)}">`];
        if (background) parts.push(`<rect width="100%" height="100%" fill="${background}"/>`);
        parts.push(`<g stroke="${stroke}" stroke-width="${strokeWidth}" stroke-linecap="round" fill="none">`);
        for (const s of result.segments) parts.push(`<line x1="${tx(s.start[0])}" y1="${ty(s.start[1])}" x2="${tx(s.end[0])}" y2="${ty(s.end[1])}"/>`);
        parts.push("</g></svg>");
        return parts.join("\n");
    }
}

for (const C of [ProductionRule, ProductionRules, Turtle]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") Object.assign(exports, { ProductionRule, ProductionRules, LSystem, Turtle });
