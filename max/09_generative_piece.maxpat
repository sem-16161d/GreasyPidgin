{
 "patcher": {
  "fileversion": 1,
  "appversion": {
   "major": 9,
   "minor": 0,
   "revision": 0,
   "architecture": "x64",
   "modernui": 1
  },
  "classnamespace": "box",
  "bglocked": 0,
  "openinpresentation": 0,
  "default_fontsize": 12.0,
  "default_fontface": 0,
  "default_fontname": "Arial",
  "gridonopen": 1,
  "gridsize": [
   15.0,
   15.0
  ],
  "autosave": 0,
  "dependency_cache": [],
  "rect": [
   60,
   60,
   1000,
   1324
  ],
  "boxes": [
   {
    "box": {
     "id": "obj-1",
     "maxclass": "comment",
     "patching_rect": [
      20,
      10,
      900,
      31.0
     ],
     "text": "Step 9 - Put it together: a small generative piece",
     "numinlets": 1,
     "numoutlets": 0,
     "fontsize": 18
    }
   },
   {
    "box": {
     "id": "obj-2",
     "maxclass": "comment",
     "patching_rect": [
      20,
      42,
      900,
      22.0
     ],
     "text": "Rhythm from a Euclidean TimeGrid, pitches from a Markov chain snapped to a PitchGrid, loudness from an Envelope, collected in a Gesture.",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-3",
     "maxclass": "comment",
     "patching_rect": [
      20,
      60,
      900,
      22.0
     ],
     "text": "Setup once: Options > File Preferences, add the GreasyPidgin folder, tick Subfolders. Open the Max Console (Window > Max Console).",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-4",
     "maxclass": "comment",
     "patching_rect": [
      20,
      78,
      900,
      22.0
     ],
     "text": "Edit the code in the box; click outside it to compile. Errors appear in the Max Console.",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-5",
     "maxclass": "toggle",
     "patching_rect": [
      20,
      108,
      24,
      24
     ],
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      "int"
     ],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "obj-6",
     "maxclass": "newobj",
     "patching_rect": [
      60,
      110,
      86,
      22
     ],
     "text": "metro 2400",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      "bang"
     ]
    }
   },
   {
    "box": {
     "id": "obj-7",
     "maxclass": "comment",
     "patching_rect": [
      160,
      112,
      300,
      22.0
     ],
     "text": "start / stop the loop",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-8",
     "maxclass": "message",
     "patching_rect": [
      20,
      158,
      70,
      22
     ],
     "text": "pulses 7",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-9",
     "maxclass": "message",
     "patching_rect": [
      100,
      158,
      77,
      22
     ],
     "text": "pulses 11",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-10",
     "maxclass": "message",
     "patching_rect": [
      187,
      158,
      70,
      22
     ],
     "text": "pulses 5",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-11",
     "maxclass": "message",
     "patching_rect": [
      267,
      158,
      77,
      22
     ],
     "text": "tempo 100",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-12",
     "maxclass": "message",
     "patching_rect": [
      354,
      158,
      77,
      22
     ],
     "text": "tempo 140",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-13",
     "maxclass": "message",
     "patching_rect": [
      441,
      158,
      91,
      22
     ],
     "text": "mode dorian",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-14",
     "maxclass": "message",
     "patching_rect": [
      542,
      158,
      105,
      22
     ],
     "text": "mode phrygian",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-15",
     "maxclass": "message",
     "patching_rect": [
      657,
      158,
      91,
      22
     ],
     "text": "mode lydian",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-16",
     "maxclass": "message",
     "patching_rect": [
      758,
      158,
      196,
      22
     ],
     "text": "theme 62 64 65 69 67 65 64",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-17",
     "maxclass": "message",
     "patching_rect": [
      20,
      188,
      238,
      22
     ],
     "text": "theme 62 65 64 62 69 67 65 64 62",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-18",
     "maxclass": "message",
     "patching_rect": [
      268,
      188,
      140,
      22
     ],
     "text": "loudness 40 110 60",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-19",
     "maxclass": "message",
     "patching_rect": [
      418,
      188,
      119,
      22
     ],
     "text": "loudness 100 30",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-20",
     "maxclass": "v8.codebox",
     "patching_rect": [
      20,
      238,
      600,
      856
     ],
     "code": "inlets = 1;\noutlets = 2;\n\nconst { Phonon } = require(\"Phonon\");\nconst { Gesture } = require(\"Gesture\");\nconst { PitchGrid } = require(\"PitchGrid\");\nconst { TimeGrid } = require(\"TimeGrid\");\nconst { Envelope } = require(\"Envelope\");\nconst { MarkovChain } = require(\"MarkovChains\");\n\nconst s = {\n    bpm: 100,\n    pulses: 7,\n    steps: 16,\n    tuning: \"edo12\",\n    mask: \"dorian\",\n    theme: [62, 65, 64, 62, 69, 67, 65, 64, 62],\n    loudness: new Envelope([40, 110, 60]),   // velocity over the phrase\n};\n\nconst chain = new MarkovChain();\n\nfunction play(events) {\n    for (const e of events) {\n        outlet(0, e.pitch, e.velocity, Math.round(e.durationSec * 1000), Math.round(e.startSec * 1000));\n    }\n}\n\nfunction build() {\n    // 1. when: a Euclidean rhythm over one bar\n    const onsets = TimeGrid.fromEuclidean(s.pulses, s.steps, 0, { durationBeats: 4, bpm: s.bpm }).sorted();\n    const step = 4 * 60 / s.bpm / s.steps;   // seconds per step\n\n    // 2. which pitches: a Markov chain learned from the theme, snapped to the mode\n    chain.generateRulesFromList(s.theme, { order: 1 });\n    const scale = PitchGrid.fromMask(s.tuning, s.mask, \"d3\", \"d5\");\n    const melody = scale.quantise(chain.getNElements({ seed: [s.theme[0]], n: onsets.length - 1 }));\n\n    // 3. one Phonon per onset, loudness from the envelope\n    const phonons = [];\n    for (let i = 0; i < onsets.length; i++) {\n        const position = i / Math.max(1, onsets.length - 1);\n        const velocity = Math.round(s.loudness.getValue(position, true, false));\n        phonons.push(new Phonon(onsets[i], step * 1.8, melody[i], velocity, s.bpm));\n    }\n    return new Gesture(0, phonons, 4 * 60 / s.bpm, { bpm: s.bpm });\n}\n\nfunction bang() {\n    const phrase = build();\n    play(phrase.toEvents());\n    outlet(1, Math.round(phrase.durationSec * 1000));   // -> metro's right inlet = loop length\n}\n\nfunction pulses(n) { s.pulses = n; }\nfunction tempo(b) { s.bpm = b; }\nfunction mode(name) { s.mask = name; }\nfunction theme(...pitches) { s.theme = pitches; }\nfunction loudness(...values) { s.loudness = new Envelope(values); }\n",
     "filename": "none",
     "text": "",
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "",
      ""
     ],
     "fontname": "Menlo",
     "fontsize": 11.0
    }
   },
   {
    "box": {
     "id": "obj-21",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      1119,
      100,
      22
     ],
     "text": "pipe 0 0 0 0",
     "numinlets": 4,
     "numoutlets": 3,
     "outlettype": [
      "",
      "",
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-22",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      1159,
      128,
      22
     ],
     "text": "makenote 100 250",
     "numinlets": 3,
     "numoutlets": 2,
     "outlettype": [
      "float",
      "float"
     ]
    }
   },
   {
    "box": {
     "id": "obj-23",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      1199,
      65,
      22
     ],
     "text": "noteout",
     "numinlets": 3,
     "numoutlets": 0,
     "outlettype": []
    }
   },
   {
    "box": {
     "id": "obj-24",
     "maxclass": "comment",
     "patching_rect": [
      150,
      1121,
      360,
      22.0
     ],
     "text": "one list per note: pitch velocity durationMs delayMs",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-25",
     "maxclass": "button",
     "patching_rect": [
      350,
      1159,
      24,
      24
     ],
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      "bang"
     ],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "obj-26",
     "maxclass": "newobj",
     "patching_rect": [
      350,
      1191,
      51,
      22
     ],
     "text": "t b b",
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "bang",
      "bang"
     ]
    }
   },
   {
    "box": {
     "id": "obj-27",
     "maxclass": "message",
     "patching_rect": [
      350,
      1223,
      42,
      22
     ],
     "text": "stop",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-28",
     "maxclass": "message",
     "patching_rect": [
      400,
      1223,
      49,
      22
     ],
     "text": "clear",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-29",
     "maxclass": "comment",
     "patching_rect": [
      380,
      1161,
      200,
      22.0
     ],
     "text": "panic: stop all notes",
     "numinlets": 1,
     "numoutlets": 0
    }
   },
   {
    "box": {
     "id": "obj-30",
     "maxclass": "comment",
     "patching_rect": [
      620,
      1121,
      320,
      22.0
     ],
     "text": "right outlet sets the metro to the phrase length",
     "numinlets": 1,
     "numoutlets": 0
    }
   }
  ],
  "lines": [
   {
    "patchline": {
     "source": [
      "obj-5",
      0
     ],
     "destination": [
      "obj-6",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-8",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-9",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-10",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-11",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-12",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-13",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-14",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-15",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-16",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-17",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-18",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-19",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-6",
      0
     ],
     "destination": [
      "obj-20",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-20",
      0
     ],
     "destination": [
      "obj-21",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-21",
      0
     ],
     "destination": [
      "obj-22",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-21",
      1
     ],
     "destination": [
      "obj-22",
      1
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-21",
      2
     ],
     "destination": [
      "obj-22",
      2
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-22",
      0
     ],
     "destination": [
      "obj-23",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-22",
      1
     ],
     "destination": [
      "obj-23",
      1
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-25",
      0
     ],
     "destination": [
      "obj-26",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-26",
      0
     ],
     "destination": [
      "obj-27",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-26",
      1
     ],
     "destination": [
      "obj-28",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-27",
      0
     ],
     "destination": [
      "obj-22",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-28",
      0
     ],
     "destination": [
      "obj-21",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-20",
      1
     ],
     "destination": [
      "obj-6",
      1
     ]
    }
   }
  ]
 }
}