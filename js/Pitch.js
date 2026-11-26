/*
Pitch.js — JavaScript port of GreasyPidgin/Pitch.py
(after Pitch.lsp from Michael Edwards' slippery chicken)

Note names (SPN) <-> MIDI floats <-> Hz, with microtonal accidentals:
    s / f        sharp / flat               cs4, bf3
    qs / qf      quarter-tone sharp / flat  cqs4  (+0.5)
    ss / sf      sixth-tone sharp / flat    (+-1/3)
    ts / tf      twelfth-tone sharp / flat  (+-1/6)
    sqs, fqf, sss, ... combinations         (sharp + quarter-sharp etc.)

    Max:   var Pitch = require("Pitch");   Pitch.spntom("cqs4")  // 60.5
    Node:  const { spntom, mtof } = require("./Pitch");
*/

const NOTE_OFFSETS = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };

const ACCIDENTAL_OFFSETS = {
    "": 0, s: 1, f: -1, qs: 0.5, qf: -0.5, ss: 1 / 3, sf: -1 / 3, ts: 1 / 6, tf: -1 / 6,
    sqs: 1 + 0.5, sqf: 1 - 0.5, fqs: -1 + 0.5, fqf: -1 - 0.5,
    sss: 1 + 1 / 3, ssf: 1 - 1 / 3, fss: -1 + 1 / 3, fsf: -1 - 1 / 3,
    sts: 1 + 1 / 6, stf: 1 - 1 / 6, fts: -1 + 1 / 6, ftf: -1 - 1 / 6,
};

/** Note name like 'c4', 'bf3', 'cqs4', 'C-1' -> MIDI float. */
function spntom(spn) {
    const m = /^([a-g])([qsft]{0,3})(-?\d+)$/.exec(String(spn).trim().toLowerCase());
    if (!m) throw new Error(`Cannot parse note name: '${spn}'`);
    const [, letter, acc, octave] = m;
    if (!Object.hasOwn(ACCIDENTAL_OFFSETS, acc)) throw new Error(`Unknown accidental '${acc}' in note '${spn}'`);
    return 12 * (Number(octave) + 1) + NOTE_OFFSETS[letter] + ACCIDENTAL_OFFSETS[acc];
}

function mtof(midi, referenceA4 = 440) {
    if (referenceA4 <= 0) throw new RangeError(`a4 must be > 0, got ${referenceA4}`);
    return referenceA4 * 2 ** ((Number(midi) - 69) / 12);
}

function ftom(freq, referenceA4 = 440) {
    if (freq <= 0) throw new RangeError(`freq must be > 0, got ${freq}`);
    if (referenceA4 <= 0) throw new RangeError(`a4 must be > 0, got ${referenceA4}`);
    return 69 + 12 * Math.log2(Number(freq) / referenceA4);
}

function spntof(spn, referenceA4 = 440) {
    return mtof(spntom(spn), referenceA4);
}

/** Move a MIDI value by octaves until it lies in [lo, hi]. */
function forceIntoRangeMidi(value, lo, hi, maxIter = 10) {
    for (let i = 0; i < maxIter; i++) {
        if (value < lo) value += 12;
        else if (value > hi) value -= 12;
        else return value;
    }
    throw new Error(`forceIntoRangeMidi: cannot find a solution for ${value} higher than ${lo} and lower than ${hi}`);
}

if (typeof exports !== "undefined") Object.assign(exports, { spntom, mtof, ftom, spntof, forceIntoRangeMidi });
