/*
Instrument.js — JavaScript port of GreasyPidgin/Instrument.py
(after Instrument.lsp from Michael Edwards' slippery chicken)

Range, transposition (written + transposition_semitones = sounding),
missing notes (written), microtones, clefs and dynamic range.

    Max:   var Instrument = require("Instrument").Instrument;
    Node:  const { Instrument } = require("./Instrument");

    const cl = new Instrument({ name: "b-flat-clarinet", rangeMidi: [50, 91], transposition_semitones: -2 });
    cl.in_range(49);   // [false, 0]  (too low)
*/

/** Python's round(): halves go to the even neighbour. */
const roundHalfEven = x => { const r = Math.round(x); return Math.abs(x % 1) === 0.5 && r % 2 ? r - 1 : r; };

class Instrument {
    constructor({
        name = "dummy", rangeMidi = [0, 127], numSystems = 1, initClefs = null, possibleClefs = null,
        chordsPossible = true, microTones = true, writtenDynamicRange = ["ppppp", "fffff"],
        physicalDynamicRangedB = [60, 100], transposition_semitones = 0, missing_notes = null, midi_program = 1,
    } = {}) {
        this.name = name;
        this.numSystems = numSystems;
        this.possibleClefs = possibleClefs || ["treble", "bass"];
        this.initClefs = initClefs || ["treble"];
        this.rangeMidi = [Number(rangeMidi[0]), Number(rangeMidi[1])];
        this.chordsPossible = chordsPossible;
        this.microTones = microTones;
        this.transposition_semitones = Number(transposition_semitones);
        [this.lowest_written_midi, this.highest_written_midi] = this.rangeMidi;
        this.lowest_sounding_midi = this.lowest_written_midi + this.transposition_semitones;
        this.highest_sounding_midi = this.highest_written_midi + this.transposition_semitones;
        this.missing_notes_written = new Set([...(missing_notes || [])].map(Number));
        this.missing_notes_sounding = new Set([...this.missing_notes_written].map(m => m + this.transposition_semitones));
        this.writtenDynamicRange = [...writtenDynamicRange];
        this.physicalDynamicRangedB = physicalDynamicRangedB.map(Number);
        this.midi_program = Math.trunc(midi_program);
    }

    _get_range(sounding) {
        return sounding ? [this.lowest_sounding_midi, this.highest_sounding_midi] : [this.lowest_written_midi, this.highest_written_midi];
    }

    /**
     * [inRange, extra]: extra 0 = too low, 1 = too high, null = in range or
     * rejected for a microtone / missing note. Missing notes are compared in
     * the same domain (written or sounding) as `midi`.
     */
    in_range(midi, { sounding = false, allow_microtones = false, allow_missing_notes = false } = {}) {
        if (midi === null || midi === undefined) throw new Error("in_range: midi cannot be null");
        midi = Number(midi);
        if (!Number.isInteger(midi) && !(this.microTones || allow_microtones)) return [false, null];
        const [low, high] = this._get_range(sounding);
        const missing = sounding ? this.missing_notes_sounding : this.missing_notes_written;
        if (!allow_missing_notes && [...missing].some(m => Math.abs(midi - m) < 1e-6)) return [false, null];
        if (midi < low) return [false, 0];
        if (midi > high) return [false, 1];
        return [true, null];
    }

    /** Move a pitch into range by octaves (rounded to a semitone first if microtones are not allowed). */
    force_in_range(midi, { sounding = false, allow_microtones = false, allow_missing_notes = false } = {}) {
        const opts = { sounding, allow_microtones, allow_missing_notes };
        midi = Number(midi);
        if (!Number.isInteger(midi) && !(this.microTones || allow_microtones)) midi = roundHalfEven(midi);
        const [ok, direction] = this.in_range(midi, opts);
        if (ok) return midi;
        const step = direction === 1 ? -12 : 12;
        let candidate = midi;
        for (let i = 0; i < 16; i++) {
            candidate += step;
            if (this.in_range(candidate, opts)[0]) return candidate;
        }
        const [low, high] = this._get_range(sounding);
        return Math.max(low, Math.min(high, candidate));
    }

    toString() {
        return `Instrument(name='${this.name}', rangeMidi=${JSON.stringify(this.rangeMidi)}, ` +
               `transposition=${this.transposition_semitones}, microTones=${this.microTones}, ` +
               `missing(written)=${JSON.stringify([...this.missing_notes_written])}, midi_program=${this.midi_program})`;
    }
}

if (typeof exports !== "undefined") exports.Instrument = Instrument;
