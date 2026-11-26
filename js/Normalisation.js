/*
Normalisation.js — JavaScript port of GreasyPidgin/Normalisation.py

    Max:   var N = require("Normalisation");   N.scale(64, 0, 127, 0, 1)
    Node:  const { scale } = require("./Normalisation");
*/

const isNumber = (...args) => args.every(x => typeof x === "number" && !Number.isNaN(x));

/** Map value from [inLo, inHi] to [outLo, outHi], like Max's [scale]. A reversed
    input range inverts the mapping; exponent != 1 curves the normalized position
    (sign kept below the input range). */
function scale(value, inLo, inHi, outLo, outHi, exponent = 1, clipToRange = false) {
    if (!isNumber(value, inLo, inHi, outLo, outHi, exponent)) throw new TypeError("scale: all arguments must be numbers");
    if (inLo === inHi) return outLo;
    if (clipToRange) value = Math.min(Math.max(value, Math.min(inLo, inHi)), Math.max(inLo, inHi));
    let t = (value - inLo) / (inHi - inLo);
    if (exponent !== 1) t = Math.sign(t) * Math.abs(t) ** exponent;
    return outLo + t * (outHi - outLo);
}

function scaleValues(values, inLo, inHi, outLo, outHi, exponent = 1, clipToRange = true) {
    values = [...(values || [])];
    if (!values.length) throw new Error("scaleValues: values is empty");
    return values.map(v => scale(v, inLo, inHi, outLo, outHi, exponent, clipToRange));
}

/** value from [lo..hi] into [0..1] (warns via post / console if outside); null if not a number. */
function normaliseIntoRange(value, lo, hi, clipToRange = true) {
    if (!isNumber(value, lo, hi)) return null;
    if (lo !== hi && !(Math.min(lo, hi) <= value && value <= Math.max(lo, hi))) {
        const msg = "Value out of bounds" + (clipToRange ? "; clipping to 0..1" : "");
        if (typeof post === "function") post(msg + "\n"); else console.warn(msg);
    }
    return scale(value, lo, hi, 0, 1, 1, clipToRange);
}

function normaliseValuesIntoRange(values, lo, hi, clipToRange = true) {
    return scaleValues(values, lo, hi, 0, 1, 1, clipToRange);
}

/** Normalise numbers into [0..1] by their own min / max. */
function normaliseValues(values) {
    if (values === null || typeof values !== "object" || !(Symbol.iterator in values)) {
        throw new Error("normaliseValues: Wrong Type! values is not iterable");
    }
    values = [...values];
    if (!values.length) throw new Error("normaliseValues: values is empty");
    return normaliseValuesIntoRange(values, Math.min(...values), Math.max(...values), true);
}

if (typeof exports !== "undefined") {
    Object.assign(exports, { scale, scaleValues, normaliseIntoRange, normaliseValuesIntoRange, normaliseValues });
}
