/*
Player.js — JavaScript port of GreasyPidgin/Player.py

A Player plays one or more instruments from a palette (default: the
standard palette). Without a name it is named after its instruments.

    Max:   var Player = require("Player").Player;
    Node:  const { Player } = require("./Player");

    new Player(["flute", "piccolo"]).name;   // "flute_piccolo"
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { STANDARD_INSTRUMENTS } = load("Instruments");
const { TemporalObject } = load("TemporalObject");

class Player {
    // instanceof by brand: Max loads a fresh copy of a module on every require(), so the same
    // class can exist twice; Symbol.for() names are shared, class objects are not.
    static [Symbol.hasInstance](x) {
        return Function.prototype[Symbol.hasInstance].call(this, x) ||
               (x != null && x[Symbol.for("GreasyPidgin." + this.name)] === true);
    }
    constructor(instruments = [], name = "", { instrumentPalette = STANDARD_INSTRUMENTS } = {}) {
        this.instrumentPalette = instrumentPalette;
        this.instruments = (typeof instruments === "string" ? [instruments] : instruments).map(key => {
            if (!Object.hasOwn(instrumentPalette, key)) throw new Error(`Player: Instrument '${key}' doesn't exist in given palette`);
            return instrumentPalette[key];
        });
        this.name = String(name) || this.instruments.map(i => i.name).join("_");
        this.temporalObjects = new TemporalObject();
    }

    toString() { return `Player(name='${this.name}', instruments=${JSON.stringify(this.instruments.map(i => i.name))})`; }
}

for (const C of [Player]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") exports.Player = Player;
