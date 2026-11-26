// gp_sequencer.js — [v8] example: Envelope + Grid + TemporalObject together
//
// A phrase is built as a TemporalObject container with one child per note:
//   pitch    = contour envelope, scaled into the range, quantised to a scale Grid
//   velocity = dynamics envelope (a hairpin)
//   onsets   = rhythm (inter-onset times in beats, cycled), optionally
//              humanized and then snapped to a time Grid
// bang flattens the phrase and sends one "pitch velocity durMs delayMs" list
// per note to outlet 0 -> [pipe 0 0 0 0] -> [makenote] -> [noteout].
//
// notes <n>                 number of notes (default 16)
// contour <values...>       pitch contour, e.g. contour 0 1 0.2 0.7
// periodic <periods> <shape>  contour from a periodic shape, e.g. periodic 2 triangle
// mode <pitch classes...>   scale, e.g. mode 0 2 4 7 9 (pentatonic)
// range <low> <high>        MIDI range (default 48 84)
// dynamics <values...>      velocity envelope 1..127, e.g. dynamics 30 110 50
// rhythm <beats...>         inter-onset times in beats, cycled, e.g. rhythm 0.5 0.25 0.25
// legato <0..1>             note length as part of the inter-onset time (default 0.9)
// tempo <bpm>               default 100
// humanize <beats>          random onset deviation (default 0)
// quantise <per beat>       snap onsets to 1/n beat (4 = 16ths), 0 = off (default 0)
// print                     post the phrase to the Max console
// bang                      build and play
//
// outlet 1 : total phrase length in ms

autowatch = 1;
inlets = 1;
outlets = 2;

const { Envelope } = require("Envelope");
const { Grid } = require("Grid");
const { TemporalObject } = require("TemporalObject");

const s = {
    notes: 16, low: 48, high: 84, bpm: 100, legato: 0.9, humanize: 0, quantise: 0,
    pcs: [0, 2, 3, 5, 7, 9, 10],
    rhythm: [0.5, 0.25, 0.25, 1],
    contour: new Envelope([0, 1, 0.3, 0.8, 0]),
    dynamics: new Envelope([[0, 30, "easeIn"], [1, 110], [2, 50]]),
};
let phrase = null;

const beat = () => 60 / s.bpm;

function scaleGrid() {
    const set = new Set(s.pcs.map(pc => ((Math.round(pc) % 12) + 12) % 12));
    const pitches = [];
    for (let p = s.low; p <= s.high; p++) if (set.has(p % 12)) pitches.push(p);
    return new Grid(pitches.length ? pitches : [s.low]);
}

function build() {
    const pitchGrid = scaleGrid();
    const iois = Array.from({ length: s.notes }, (_, i) => s.rhythm[i % s.rhythm.length] * beat());
    const total = iois.reduce((a, b) => a + b, 0);
    const step = s.quantise > 0 ? beat() / s.quantise : 0;
    const timeGrid = step ? Grid.series(0, step, Math.ceil(total / step) + 2) : null;

    phrase = new TemporalObject(0, 0, null, { data: { bpm: s.bpm } });
    let t = 0;
    for (let i = 0; i < s.notes; i++) {
        const pos = s.notes > 1 ? i / (s.notes - 1) : 0;
        let start = Math.max(0, t + (Math.random() * 2 - 1) * s.humanize * beat());
        if (timeGrid) start = timeGrid.quantise(start);   // snap the onset, keep the length
        const pitch = pitchGrid.quantise(s.low + s.contour.getValue(pos, true, true) * (s.high - s.low));
        const velocity = Math.round(Math.min(127, Math.max(1, s.dynamics.getValue(pos, true, false))));
        phrase.addChild(new TemporalObject(start, iois[i] * s.legato, null,
                                           { data: { pitchMidi: pitch, velocity } }));
        t += iois[i];
    }
}

function bang() {
    build();
    for (const note of phrase.flatten()) {
        outlet(0, note.data.pitchMidi, note.data.velocity,
               Math.round(note.durationSec * 1000), Math.round(note.startTimeSec * 1000));
    }
    outlet(1, Math.round(phrase.endTimeSec * 1000));
}

function print() {
    if (!phrase) build();
    post(String(phrase) + "\n");
    for (const c of phrase.children) post("  " + String(c) + "\n");
}

function notes(n) { s.notes = Math.max(1, Math.trunc(n)); }
function contour(...values) { s.contour = new Envelope(values); }
function periodic(periods = 2, shape = "triangle") { s.contour = Envelope.periodic(periods, 16, { shape }); }
function mode(...pcs) { s.pcs = pcs; }
function range(lo, hi) { s.low = Math.min(lo, hi); s.high = Math.max(lo, hi); }
function dynamics(...values) { s.dynamics = new Envelope(values); }
function rhythm(...beats) { s.rhythm = beats.filter(b => b > 0); if (!s.rhythm.length) s.rhythm = [1]; }
function legato(f) { s.legato = Math.max(0.01, f); }
function tempo(bpm) { s.bpm = Math.max(1, bpm); }
function humanize(beats) { s.humanize = Math.max(0, beats); }
function quantise(perBeat) { s.quantise = Math.max(0, Math.trunc(perBeat)); }
