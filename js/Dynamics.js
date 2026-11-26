/*
Dynamics.js — JavaScript port of GreasyPidgin/Dynamics.py

Dynamic markings (pp, mf, ff, ...) and hairpins ('pp-mp', 'pp<mp', 'ff>mp')
as MIDI velocity. A hairpin's separator ('-', '<', '>', '~') is cosmetic:
direction is always read left to right.

    Max:   var Dynamics = require("Dynamics");   Dynamics.parseDynamicMarking("pp-f")  // [33, 96]
    Node:  const { parseDynamicMarking } = require("./Dynamics");
*/

const DYNAMIC_MARKINGS = {
    pppp: 8, ppp: 16, pp: 33, p: 49, mp: 64, mf: 80, f: 96, ff: 112, fff: 120, ffff: 127,
};

// longest names first, so "ppp" isn't split into "pp" + "p"
const ALT = Object.keys(DYNAMIC_MARKINGS).sort((a, b) => b.length - a.length).join("|");
const HAIRPIN_RE = new RegExp(`^\\s*(${ALT})\\s*[-<>~]\\s*(${ALT})\\s*$`, "i");

/** Single marking ('pp', 'mf', ...) -> MIDI velocity. */
function dynamicMarkingToVelocity(marking) {
    const key = String(marking).trim().toLowerCase();
    if (!Object.hasOwn(DYNAMIC_MARKINGS, key)) {
        throw new Error(`Dynamics: unknown dynamic marking '${marking}'. Known markings: ${Object.keys(DYNAMIC_MARKINGS).join(", ")}`);
    }
    return DYNAMIC_MARKINGS[key];
}

/** 'mf' -> velocity; hairpin 'pp-mp' -> [startVelocity, endVelocity]. */
function parseDynamicMarking(text) {
    const m = HAIRPIN_RE.exec(text);
    return m ? [dynamicMarkingToVelocity(m[1]), dynamicMarkingToVelocity(m[2])] : dynamicMarkingToVelocity(text);
}

/** [start, end] markings (lowercase) for a hairpin, or null for a plain marking. */
function splitHairpin(text) {
    const m = HAIRPIN_RE.exec(text);
    return m ? [m[1].toLowerCase(), m[2].toLowerCase()] : null;
}

function isDynamicMarkingText(text) {
    return typeof text === "string" && (HAIRPIN_RE.test(text) || Object.hasOwn(DYNAMIC_MARKINGS, text.trim().toLowerCase()));
}

if (typeof exports !== "undefined") {
    Object.assign(exports, { DYNAMIC_MARKINGS, dynamicMarkingToVelocity, parseDynamicMarking, splitHairpin, isDynamicMarkingText });
}
