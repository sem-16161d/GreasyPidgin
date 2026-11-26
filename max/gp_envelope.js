// gp_envelope.js — [v8] example: build, shape and sample a GreasyPidgin Envelope
//
// inlet 0  : messages below
// outlet 0 : the envelope sampled at `resolution` points -> [multislider]
//            (also sends "size n" and "setminmax lo hi", lo/hi = y range joined with 0..1)
// outlet 1 : value at a normalized x (send a float)
//
// list of numbers          values -> breakpoints, e.g. 0 1 0.3 0.8 0
// pairs x y x y ...        breakpoint pairs in your own units
// curve <name|number>      same curve on every segment: exp, log, easeIn, easeOut,
//                          easeInOut, smooth, step, linear, or a curvature like -4
// periodic <periods> <res> <shape>   sine, cosine, triangle, saw, saw_down, square
// bounds <min> <max>       squeeze the shape between a floor and a ceiling (0..1)
// jitter <amount>          random deviation, 0.2 = up to +-20 %
// reduce <minima> <maxima> keep only the endpoints and the strongest extrema
// resolution <n>           number of samples sent to outlet 0
// float                    value at normalized x (0..1) -> outlet 1
// ascii                    print the envelope to the Max console
// bang                     send the samples again

autowatch = 1;
inlets = 1;
outlets = 2;

const { Envelope } = require("Envelope");

let env = new Envelope([0, 1, 0.3, 0.8, 0]);
let size = 32;

function render() {
    const samples = Array.from({ length: size }, (_, i) => env.getValue(i / (size - 1), true, false));
    const [lo, hi] = env.y_range;
    outlet(0, "size", size);
    outlet(0, "setminmax", Math.min(0, lo, hi), Math.max(1, lo, hi));
    outlet(0, samples);
}

function bang() { render(); }

function list(...values) { env = new Envelope(values); render(); }

function pairs(...flat) {
    const pts = [];
    for (let i = 0; i + 1 < flat.length; i += 2) pts.push([flat[i], flat[i + 1]]);
    env = new Envelope(pts);
    render();
}

function curve(shape) {
    env = env.withCurves(new Array(env.points.length - 1).fill(shape));
    render();
}

function periodic(periods = 1, resolution = 16, shape = "sine") {
    env = Envelope.periodic(periods, resolution, { shape });
    render();
}

function bounds(lo = 0, hi = 1) { env = env.withBounds(lo, hi); render(); }

function jitter(amount = 0.1) { env = env.withJitter(amount); render(); }

function reduce(minima = 2, maxima = 2) { env = env.reduceEnvPoints(minima, maxima, size); render(); }

function resolution(n) { size = Math.max(2, Math.trunc(n)); render(); }

function msg_float(x) { outlet(1, env.getValue(x, true, false)); }

function msg_int(x) { msg_float(x); }

function ascii() { env.displayAscii(40, 12); }
