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
   1034
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
     "text": "Step 8 - Generators: Markov chain and cellular automaton",
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
     "text": "A Markov chain learns which note follows which. A cellular automaton grows rows of cells; each row is one step.",
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
     "maxclass": "message",
     "patching_rect": [
      20,
      108,
      77,
      22
     ],
     "text": "markov 12",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-6",
     "maxclass": "message",
     "patching_rect": [
      107,
      108,
      77,
      22
     ],
     "text": "markov 24",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-7",
     "maxclass": "message",
     "patching_rect": [
      194,
      108,
      238,
      22
     ],
     "text": "learn 60 62 64 65 67 65 64 62 60",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ]
    }
   },
   {
    "box": {
     "id": "obj-8",
     "maxclass": "message",
     "patching_rect": [
      442,
      108,
      196,
      22
     ],
     "text": "learn 60 67 65 64 62 60 72",
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
      648,
      108,
      49,
      22
     ],
     "text": "ca 30",
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
      707,
      108,
      49,
      22
     ],
     "text": "ca 90",
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
      766,
      108,
      56,
      22
     ],
     "text": "ca 110",
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
      832,
      108,
      56,
      22
     ],
     "text": "ca 150",
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
     "maxclass": "v8.codebox",
     "patching_rect": [
      20,
      158,
      600,
      646
     ],
     "code": "inlets = 1;\noutlets = 1;\n\nconst { MarkovChain } = require(\"MarkovChains\");\nconst { CellularAutomaton, CellularRules } = require(\"CellularAutomata\");\n\nfunction play(pitches, stepMs) {\n    for (let i = 0; i < pitches.length; i++) {\n        outlet(0, pitches[i], 80, stepMs * 0.9, i * stepMs);\n    }\n}\n\n// --- Markov chain: learn from a melody, then improvise on it ---\nconst chain = new MarkovChain();\nchain.generateRulesFromList([60, 62, 64, 62, 60, 67, 64, 62, 60], { order: 1 });\n\nfunction markov(n) {\n    const melody = chain.getNElements({ seed: [60], n: n });\n    post(\"markov:\", melody.join(\" \"), \"\\n\");\n    play(melody, 200);\n}\n\nfunction learn(...melody) {\n    chain.generateRulesFromList(melody, { order: 1 });\n    post(\"learned\", melody.length, \"notes\\n\");\n}\n\n// --- Cellular automaton: each row is one step, each live cell plays a pitch ---\nconst cellPitches = [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84];\n\nfunction ca(rule) {\n    const automaton = new CellularAutomaton({ rules: CellularRules.elementaryWolfram(rule) });\n    automaton.gen0fromSingleCell(cellPitches.length);\n    automaton.iterate(15);\n    const rows = automaton.generationsAsArray();\n    for (let step = 0; step < rows.length; step++) {\n        for (let cell = 0; cell < rows[step].length; cell++) {\n            if (rows[step][cell] === 1) {\n                outlet(0, cellPitches[cell], 70, 120, step * 150);\n            }\n        }\n    }\n    automaton.printGenerations();\n}\n",
     "filename": "none",
     "text": "",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "fontname": "Menlo",
     "fontsize": 11.0
    }
   },
   {
    "box": {
     "id": "obj-14",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      829,
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
     "id": "obj-15",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      869,
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
     "id": "obj-16",
     "maxclass": "newobj",
     "patching_rect": [
      20,
      909,
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
     "id": "obj-17",
     "maxclass": "comment",
     "patching_rect": [
      150,
      831,
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
     "id": "obj-18",
     "maxclass": "button",
     "patching_rect": [
      350,
      869,
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
     "id": "obj-19",
     "maxclass": "newobj",
     "patching_rect": [
      350,
      901,
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
     "id": "obj-20",
     "maxclass": "message",
     "patching_rect": [
      350,
      933,
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
     "id": "obj-21",
     "maxclass": "message",
     "patching_rect": [
      400,
      933,
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
     "id": "obj-22",
     "maxclass": "comment",
     "patching_rect": [
      380,
      871,
      200,
      22.0
     ],
     "text": "panic: stop all notes",
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
      "obj-13",
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
      "obj-13",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-7",
      0
     ],
     "destination": [
      "obj-13",
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
      "obj-13",
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
      "obj-13",
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
      "obj-13",
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
      "obj-13",
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
      "obj-13",
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
      "obj-14",
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
      "obj-15",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-14",
      1
     ],
     "destination": [
      "obj-15",
      1
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-14",
      2
     ],
     "destination": [
      "obj-15",
      2
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
      "obj-16",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-15",
      1
     ],
     "destination": [
      "obj-16",
      1
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
      "obj-19",
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
      "obj-19",
      1
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
      0
     ],
     "destination": [
      "obj-15",
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
      "obj-14",
      0
     ]
    }
   }
  ]
 }
}