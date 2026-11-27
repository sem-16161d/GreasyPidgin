/*
DynamicGrid.js — JavaScript port of GreasyPidgin/DynamicGrid.py

A Grid of dB levels, one per dynamic marking (ppppp .. fffff by default),
dynamicStepdB apart below maxdB, with a MIDI velocity for each marking.

    Max:   var DynamicGrid = require("DynamicGrid").DynamicGrid;
    Node:  const { DynamicGrid } = require("./DynamicGrid");

    const dg = new DynamicGrid();
    dg.dynamicMapping.mf;        // { velMidi: 75, db: 85 }
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { Grid } = load("Grid");

const MARKINGS = ["ppppp", "pppp", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "ffff", "fffff"];

/** Python's round(): halves go to the even neighbour. */
const roundHalfEven = x => { const r = Math.round(x); return Math.abs(x % 1) === 0.5 && r % 2 ? r - 1 : r; };

class DynamicGrid extends Grid {
    constructor(dynamicStepdB = 3, maxdB = 100, possibleDynamicsString = null, minVelMidi = 20, maxVelMidi = 120) {
        const names = possibleDynamicsString || MARKINGS;
        const values = Grid.series(Number(maxdB), -Number(dynamicStepdB), names.length);
        super(values);
        this.possibleDynamicsString = [...names];
        this.dynamicStepdB = Number(dynamicStepdB);
        this.maxdB = Number(maxdB);
        this.mindB = Math.min(...values);
        this.minVelMidi = Math.trunc(minVelMidi);
        this.maxVelMidi = Math.trunc(maxVelMidi);
        // quiet -> low dB, loud -> high dB
        const span = this.maxdB - this.mindB;
        this.dynamicMapping = {};
        values.sorted().forEach((dB, i) => {
            if (i >= names.length) return;
            const vel = span ? this.minVelMidi + (dB - this.mindB) / span * (this.maxVelMidi - this.minVelMidi) : this.minVelMidi;
            this.dynamicMapping[names[i]] = { velMidi: roundHalfEven(vel), db: dB };
        });
    }
}

for (const C of [DynamicGrid]) C.prototype[Symbol.for("GreasyPidgin." + C.name)] = true;

if (typeof exports !== "undefined") exports.DynamicGrid = DynamicGrid;
