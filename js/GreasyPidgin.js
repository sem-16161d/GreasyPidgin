/*
GreasyPidgin.js — JavaScript port of GreasyPidgin/GreasyPidgin.py

The top-level composition object: a TemporalObject with an Ensemble, a
TimeGrid, a PitchGrid and a DynamicGrid.

    Max:   var GreasyPidgin = require("GreasyPidgin").GreasyPidgin;
    Node:  const { GreasyPidgin } = require("./GreasyPidgin");

    const gp = new GreasyPidgin("piece", { ensemble: ["flute", "violin"], pitchGrid: [60, 62, 63, 65, 67] });
*/

// Max finds modules by name on its search path and returns an empty object (no error) when it
// can't; Node throws for a bare name and needs "./". Try the bare name first, then "./".
const load = name => {
    let m = null;
    try { m = require(name); } catch (e) { /* Node: not a package */ }
    return m && Object.keys(m).length ? m : require("./" + name);
};
const { TemporalObject } = load("TemporalObject");
const { Ensemble } = load("Ensemble");
const { TimeGrid } = load("TimeGrid");
const { PitchGrid } = load("PitchGrid");
const { DynamicGrid } = load("DynamicGrid");

const ensure = (value, Cls) => (value instanceof Cls ? value : new Cls(value));

class GreasyPidgin extends TemporalObject {
    constructor(name = "GreasyPidgin", {
        ensemble = null, timeGrid = null, pitchGrid = null, dynamicGrid = null,
        temporalObjects = null, startTimeSec = 0, durationSec = 0,
    } = {}) {
        super(startTimeSec, durationSec, temporalObjects);
        this.name = name;
        this.ensemble = ensemble === null ? new Ensemble() : ensure(ensemble, Ensemble);
        this.timeGrid = timeGrid === null ? new TimeGrid() : ensure(timeGrid, TimeGrid);
        this.pitchGrid = pitchGrid === null ? new PitchGrid() : ensure(pitchGrid, PitchGrid);
        if (dynamicGrid !== null && !(dynamicGrid instanceof DynamicGrid)) {
            throw new TypeError("GreasyPidgin: dynamicGrid must be a DynamicGrid (e.g. new DynamicGrid(3))");
        }
        this.dynamicGrid = dynamicGrid || new DynamicGrid();
    }

    toString() {
        return [
            "",
            "         ,--.",
            "        ( @° \\",
            "       <´,..·_\\",
            "         )_.-'/`·,",
            "        /-'``     `·,",
            "       |  GREASY   0)`·-___",
            "        \\ PIDGIN  0) 0)0 );)`--,__",
            "         \\,    _:0) 0)0_);;):;)-->>",
            "           \"-,   ,--´",
            "              \\,/",
            "            ,_//",
            "           ,_-'-,",
            "",
            `   name     : ${this.name}`,
            `   id       : ${this.id}`,
            `   start    : ${this.startTimeSec.toFixed(3)}`,
            `   dur      : ${this.durationSec.toFixed(3)}`,
            `   ensemble : ${this.ensemble}`,
            `   tmpObjs  : ${this.children.length}`,
        ].join("\n");
    }
}

if (typeof exports !== "undefined") exports.GreasyPidgin = GreasyPidgin;
