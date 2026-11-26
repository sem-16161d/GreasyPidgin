/*
Player.js — JavaScript port of GreasyPidgin/Player.py

A Player plays one or more instruments from a palette (default: the
standard palette). Without a name it is named after its instruments.

    Max:   var Player = require("Player").Player;
    Node:  const { Player } = require("./Player");

    new Player(["flute", "piccolo"]).name;   // "flute_piccolo"
*/

const load = name => { try { return require("./" + name); } catch (e) { return require(name); } };
const { STANDARD_INSTRUMENTS } = load("Instruments");
const { TemporalObject } = load("TemporalObject");

class Player {
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

if (typeof exports !== "undefined") exports.Player = Player;
