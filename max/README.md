# GreasyPidgin in Max — step-by-step examples

Nine patches, one per tutorial step. Each patch holds one `[v8.codebox]` with
the full code, the message boxes to try, and the output chain. They need
**Max 9**: the older `[js]` object cannot run GreasyPidgin's modern JavaScript.

## Setup (once)

The codeboxes load modules with `require("Grid")`, `require("Phonon")` and so
on, so Max has to find the `js/` folder:

1. In Max open **Options ▸ File Preferences**.
2. Add the `GreasyPidgin` folder and tick **Subfolders**.
3. Open the Max Console (**Window ▸ Max Console**). Every `post()` and every
   error appears there.

Edit code in a codebox, then click outside it to compile.

## Patches

| patch | module | JavaScript introduced | output |
|-------|--------|-----------------------|--------|
| `01_first_codebox.maxpat` | Pitch | `require`, `{ }` imports, `post`, `outlet`, message functions | sine tone |
| `02_grid_scale.maxpat` | Grid | arrays, `for` loops, `new`, methods, `...values`, `let` vs `const` | MIDI |
| `03_envelope.maxpat` | Envelope | options objects `{ shape: "saw" }`, class methods, copies vs. originals | multislider |
| `04_phonon.maxpat` | Phonon | constructor arguments, objects with `.` properties, helper functions | MIDI |
| `05_gesture.maxpat` | Gesture | state + setters + one action, one-line functions | MIDI, loop |
| `06_pitchgrid_tunings.maxpat` | PitchGrid, TuningSystem | arrow functions, `.map`, `for ... in` | sine tone (microtones) |
| `07_timegrid_rhythm.maxpat` | TimeGrid, RQQ | default arguments, several imports | MIDI drums |
| `08_markov_ca.maxpat` | MarkovChains, CellularAutomata | nested loops, arrays of arrays, `if` / `===` | MIDI |
| `09_generative_piece.maxpat` | all of the above | one settings object, build vs. play | MIDI, loop |

MIDI patches send one list per note, `pitch velocity durationMs delayMs`, to
`[pipe 0 0 0 0]` → `[makenote]` → `[noteout]`. The button next to them stops
all notes.

The tutorial text (concepts, tasks, troubleshooting) is in the GreasyPidgin
tutorial doc. Every module file in `../js/` starts with a comment that shows
how to use it.
