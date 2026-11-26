/*
Ensemble.js — JavaScript port of GreasyPidgin/Ensemble.py

A Map of Players by name. Players can be Player objects, instrument names
from the palette ("flute") or plain names. A name used twice gets a
number: "flute", "flute_2", ...; `players` keeps the names in order.

    Max:   var Ensemble = require("Ensemble").Ensemble;
    Node:  const { Ensemble } = require("./Ensemble");

    const e = new Ensemble(["flute", "flute", "violin"]);
    e.getPlayer("flute_2");
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { STANDARD_INSTRUMENTS } = load("Instruments");
const { Player } = load("Player");

class Ensemble extends Map {
    constructor(players = [], { instrumentPalette = STANDARD_INSTRUMENTS } = {}) {
        super();
        this.instrumentPalette = instrumentPalette;
        this.players = [];
        for (const p of Array.isArray(players) ? players : [players]) {
            let player;
            if (p instanceof Player) player = p;
            else if (typeof p === "string") player = Object.hasOwn(instrumentPalette, p) ? new Player(p, "", { instrumentPalette }) : new Player([], p, { instrumentPalette });
            else throw new Error(`Ensemble: can't make a Player from ${p}!`);
            let name = player.name;
            for (let k = 2; this.has(name); k++) name = `${player.name}_${k}`;
            player.name = name;
            this.players.push(name);
            this.set(name, player);
        }
    }

    /** The Player with this name, or null. */
    getPlayer(name) { return this.get(String(name)) ?? null; }

    toString() { return `Ensemble(players=${this.players.length}, names=${JSON.stringify(this.players)})`; }
}

if (typeof exports !== "undefined") exports.Ensemble = Ensemble;
