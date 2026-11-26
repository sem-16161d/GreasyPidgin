// gp_grid.js — [v8] example: quantise incoming pitches to a GreasyPidgin Grid
//
// inlet 0  : numbers to quantise, or the messages below
// outlet 0 : quantised pitch
// outlet 1 : the current grid as a list (for display)
//
// int / float                   pitch to snap to the nearest grid value
// list of numbers               use these pitches as the grid
// mode <pitch classes...>       e.g. mode 0 2 3 5 7 9 10 (dorian), expanded over the range
// range <low> <high>            MIDI range for "mode" (default 36 96)
// series <start> <step> <size>  arithmetic grid, e.g. series 48 3 13 (diminished)
// fib <size> <a> <b> <offset>   Fibonacci grid + offset, e.g. fib 8 0 1 48 -> 48 49 50 51 53 56 61
// rand <size> <low> <high>      random integer grid
// sieve <step> <offset>         keep every step-th value from offset on (Xenakis)
// show                          send the grid to outlet 1

autowatch = 1;
inlets = 1;
outlets = 2;

const { Grid } = require("Grid");

let low = 36, high = 96;
let grid = null;

function fromPitchClasses(pcs) {
    const set = new Set(pcs.map(pc => ((Math.round(pc) % 12) + 12) % 12));
    const pitches = [];
    for (let p = low; p <= high; p++) if (set.has(p % 12)) pitches.push(p);
    return new Grid(pitches);
}

function show() { outlet(1, grid.sorted()); }

function msg_int(pitch) { outlet(0, grid.quantise(pitch)); }

function msg_float(pitch) { msg_int(pitch); }

function list(...pitches) { grid = new Grid(pitches); show(); }

let lastMode = [0, 2, 3, 5, 7, 9, 10];
function mode(...pcs) { lastMode = pcs; grid = fromPitchClasses(pcs); show(); }

function range(lo, hi) { low = lo; high = hi; mode(...lastMode); }

function series(start = 48, step = 2, size = 13) { grid = Grid.series(start, step, size); show(); }

function fib(size = 8, a = 0, b = 1, offset = 48) {
    grid = new Grid(Grid.fib(size, a, b).sorted().map(v => v + offset));
    show();
}

function rand(size = 8, lo = 48, hi = 72) { grid = Grid.rand(size, lo, hi, { integer: true }); show(); }

function sieve(step = 2, offset = 0) { grid = grid.sieve(step, offset); show(); }

grid = fromPitchClasses(lastMode);
