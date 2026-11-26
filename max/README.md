# GreasyPidgin in Max — [v8] examples

Examples for the JavaScript port in `../js/` (Envelope, Grid, TemporalObject).
They use the `[v8]` object, so they need **Max 9**. The classic `[js]` object
does not understand the modern JavaScript the port is written in.

## Setup (once)

The scripts load the modules with `require("Envelope")`, `require("Grid")` and
`require("TemporalObject")`, so Max has to find the `js/` folder:

1. In Max open **Options ▸ File Preferences**.
2. Add the `GreasyPidgin` folder and tick **Subfolders**.

Then open any patch below. Messages print errors to the Max console.

## Examples

| patch | script | shows |
|-------|--------|-------|
| `01_envelope.maxpat` | `gp_envelope.js` | build envelopes from values or pairs, segment curves, periodic shapes, moving bounds, jitter, reduction; sampled into a `[multislider]` |
| `02_grid_quantise.maxpat` | `gp_grid.js` | pitch grids from modes, series, Fibonacci, random values and sieves; keyboard / slider input snapped to the grid and played via `[noteout]` |
| `03_sequencer.maxpat` | `gp_sequencer.js` | all three together: a phrase as a TemporalObject tree, pitch from a contour envelope quantised to a scale grid, velocity from a dynamics envelope, onsets humanized and snapped to a time grid; played through `[pipe]` and `[makenote]`, optionally looped |

Every script lists its messages in a comment at the top.

Writing your own script works the same way:

```js
autowatch = 1;
const { Envelope } = require("Envelope");
const { Grid } = require("Grid");

const scale = new Grid([60, 62, 63, 65, 67, 69, 70, 72]);
const contour = Envelope.periodic(2, 16, { shape: "triangle" });

function bang() {
    for (let i = 0; i < 8; i++) {
        const y = contour.getValue(i / 7, true, true);   // normalized x and y
        outlet(0, scale.quantise(60 + y * 12));
    }
}
```
