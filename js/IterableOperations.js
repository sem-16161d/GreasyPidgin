/*
IterableOperations.js — JavaScript port of GreasyPidgin/IterableOperations.py

    Max:   var I = require("IterableOperations");   I.flatten([1, [2, [3]]])   // [1, 2, 3]
    Node:  const { flatten } = require("./IterableOperations");
*/

/** Items of arbitrarily nested arrays as one flat array; strings stay whole. */
const flatten = x => (Array.isArray(x) ? x.flatMap(flatten) : [x]);

/** True for a non-empty array / Set whose items are all arrays. */
const isNested = it => (Array.isArray(it) || it instanceof Set) && [...it].length > 0 && [...it].every(Array.isArray);

/** Wrap a single number / string in an array; a Set becomes an array. */
function ensureList(value) {
    if (typeof value === "number" || typeof value === "string") return [value];
    if (value instanceof Set) return [...value];
    return value;
}

if (typeof exports !== "undefined") Object.assign(exports, { flatten, isNested, ensureList });
