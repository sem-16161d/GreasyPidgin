--[[
PitchGrid.pd_lua — pdlua object

A pitch quantisation object. Feed it a pitch, get back the nearest pitch
in the selected tuning grid.

Internal representation: MIDI floats throughout.
    69.0 = A4, 60.0 = C4, fractional = microtonal, >127 = BP etc.
referenceAHz is only used when converting to/from Hz for audio output.

Creation arguments:
    [PitchGrid <system> <low> <high> <tsRoot>]
    e.g. [PitchGrid werckmeister1 48 84 c4]
    Defaults: edo12, 48, 84, no tsRoot

Inlet 1 (left):
    float   — pitch to quantise (unit set by pitchUnit)
    bang    — output full grid as list on outlet 2

Inlet 2 (right) — control messages:
    system <name>               — switch tuning system (rebuilds grid)
    tsRoot <pitch>              — set tuning system root
    scaleRoot <pitch>           — set scale root (where mask begins)
    mask <name>                 — apply a scale mask
    mask none                   — remove mask
    low <pitch>                 — set lower register bound
    high <pitch>                — set upper register bound
    range <low> <high>          — set both bounds at once
    pitchUnit midi|hz|spn       — input/output unit (default: midi)
    referenceA <hz>             — set physical A4 frequency (default 440)

Outlet 1: quantised pitch (in pitchUnit)
Outlet 2: full grid as list (bang on inlet 1)

Predefined systems:
    edo12, edo24, edo31, edo53, edo72,
    bohlenPierce, studieII, stria,
    werckmeister1..4, kirnberger2/3,
    meantoneQC, pythagorean, zeta12,
    JI_5limit_major, JI_7limit, harmonicSeries8_16,
    maqamRast, maqamBayati, maqamHijaz,
    slendro_approx, pelog_approx, AstridsBontempi

Scale masks (all 12-note systems):
    Church modes: ionian dorian phrygian lydian mixolydian aeolian locrian
    HM modes: harmonicMinor locrianSharp6 ionianSharp5 dorianSharp4
              phrygianDominant lydianSharp2 ultraLocrian
    MM modes: melodicMinor dorianFlat2 lydianAugmented lydianDominant
              mixolydianFlat6 locrianSharp2 altered
    Messiaen: wholeTone halfWholeDim messiaen3..7
    Pentatonic: majorPentatonic minorPentatonic
    chromatic
--]]


-- ---------------------------------------------------------------------------
-- SPN parser (same accidentals as Pitch.py)
-- ---------------------------------------------------------------------------

local _NOTE_OFFSETS = {c=0,d=2,e=4,f=5,g=7,a=9,b=11}
local _ACC_OFFSETS  = {
    [""]   =  0,
    s      =  1,      f      = -1,
    qs     =  0.5,    qf     = -0.5,
    ss     =  1/3,    sf     = -1/3,
    ts     =  1/6,    tf     = -1/6,
    sqs    =  1.5,    sqf    =  0.5,
    fqs    = -0.5,    fqf    = -1.5,
    sss    =  1+1/3,  ssf    =  1-1/3,
    fss    = -1+1/3,  fsf    = -1-1/3,
    sts    =  1+1/6,  stf    =  1-1/6,
    fts    = -1+1/6,  ftf    = -1-1/6,
}

local function spnToMidi(s)
    s = string.lower(tostring(s))
    local letter, acc, octStr = string.match(s, "^([a-g])([qsft]*)(-?%d+)$")
    if not letter then return nil end
    local base   = _NOTE_OFFSETS[letter] or 0
    local offset = _ACC_OFFSETS[acc]     or 0
    local octave = tonumber(octStr)
    return 12.0 * (octave + 1) + base + offset
end

local function midiToHz(midi, refA)
    refA = refA or 440.0
    return refA * (2.0 ^ ((midi - 69.0) / 12.0))
end

local function hzToMidi(hz, refA)
    refA = refA or 440.0
    return 69.0 + 12.0 * math.log(hz / refA) / math.log(2)
end

-- Convert any pitch input to MIDI float
-- pitchUnit: 'midi' | 'hz' | 'spn'
local function toMidi(val, refA, pitchUnit)
    refA      = refA     or 440.0
    pitchUnit = pitchUnit or "midi"
    if pitchUnit == "spn" then
        return spnToMidi(tostring(val)) or 69.0
    elseif pitchUnit == "hz" then
        return hzToMidi(tonumber(val) or 440.0, refA)
    else  -- midi (default) — also accept SPN strings
        if type(val) == "string" then
            return spnToMidi(val) or tonumber(val) or 69.0
        end
        return tonumber(val) or 69.0
    end
end


-- ---------------------------------------------------------------------------
-- TuningSystem — MIDI float pitch classes
-- ---------------------------------------------------------------------------

-- pitchClasses: list of semitone offsets from 0 (system unison = C)
-- repeatIntervalSemitones: 12.0=octave, 19.02=tritave, nil=non-repeating

local function makeTuningSystem(pitchClasses, repeatIntervalSemitones)
    table.sort(pitchClasses)
    return {
        pitchClasses            = pitchClasses,
        repeatIntervalSemitones = repeatIntervalSemitones,
        masks                   = {},
    }
end

-- Equal division of octave (n steps)
local function fromEDO(n)
    local step = 12.0 / n
    local pc   = {}
    for i = 0, n-1 do pc[i+1] = i * step end
    return makeTuningSystem(pc, 12.0)
end

-- Equal division from step ratio
local function fromRatio(stepRatio, stepsPerGroup, groupRatio, nonRepeating)
    if groupRatio == nil then groupRatio = stepRatio ^ stepsPerGroup end
    local intervalSemitones = 12.0 * math.log(groupRatio) / math.log(2)
    local pc = {}
    for i = 0, stepsPerGroup-1 do
        pc[i+1] = 12.0 * math.log(stepRatio ^ i) / math.log(2)
    end
    return makeTuningSystem(pc, nonRepeating and nil or intervalSemitones)
end

-- From explicit semitone offsets (historical temperaments, JI)
-- If the list has 12 entries and max < 12, repeat interval defaults to 12.0
local function fromSemitones(semitones, repeatInterval)
    local pc = {}
    for _, s in ipairs(semitones) do pc[#pc+1] = s end
    table.sort(pc)
    if pc[1] ~= 0.0 then table.insert(pc, 1, 0.0) end
    if repeatInterval == nil then
        if #pc == 12 and pc[#pc] < 12.0 then
            repeatInterval = 12.0
        elseif pc[#pc] >= 12.0 then
            repeatInterval = pc[#pc]
            -- remove the boundary from pitch classes
            local filtered = {}
            for _, v in ipairs(pc) do
                if v < repeatInterval then filtered[#filtered+1] = v end
            end
            pc = filtered
        else
            repeatInterval = pc[#pc]
        end
    end
    return makeTuningSystem(pc, repeatInterval)
end

-- From Hz values (gamelan etc.)
local function fromHz(frequencies, referenceHz)
    table.sort(frequencies)
    referenceHz = referenceHz or frequencies[1]
    local pc = {}
    for _, f in ipairs(frequencies) do
        pc[#pc+1] = 12.0 * math.log(f / referenceHz) / math.log(2)
    end
    return makeTuningSystem(pc, nil)
end

-- From ratio list (JI)
local function fromRatioList(ratios)
    table.sort(ratios)
    if ratios[1] ~= 1.0 then table.insert(ratios, 1, 1.0) end
    local semitones = {}
    for _, r in ipairs(ratios) do
        semitones[#semitones+1] = 12.0 * math.log(r) / math.log(2)
    end
    return fromSemitones(semitones)
end


-- ---------------------------------------------------------------------------
-- Pitch generation — sieve algorithm (matches Python generatePitches)
-- ---------------------------------------------------------------------------

local function generatePitches(ts, low, high, tsRoot, scaleRoot, maskIndices)
    local _EPS    = 1e-6
    local interval = ts.repeatIntervalSemitones or 12.0
    local pc       = ts.pitchClasses
    local nSteps   = #pc

    -- step 1: anchor
    local anchor = tsRoot or 0.0

    -- step 2: generate full chromatic list with pcIndex tracking
    local chromatic = {}  -- {midi, pcIdx}
    local gMin = math.floor((low  - anchor) / interval) - 1
    local gMax = math.ceil( (high - anchor) / interval) + 1
    for g = gMin, gMax do
        for i, p in ipairs(pc) do
            local midi = anchor + g * interval + p
            if midi >= low - _EPS and midi <= high + _EPS then
                chromatic[#chromatic+1] = {round(midi, 8), i}
            end
        end
    end
    table.sort(chromatic, function(a, b) return a[1] < b[1] end)

    if #chromatic == 0 then return {} end

    -- step 3: find scaleRoot pcIndex
    local srPCIdx = chromatic[1][2]
    if scaleRoot ~= nil then
        local bestDist = math.huge
        for _, entry in ipairs(chromatic) do
            local d = math.abs(entry[1] - scaleRoot)
            if d < bestDist then
                bestDist = d
                srPCIdx  = entry[2]
            end
        end
    end

    -- step 4: sieve
    if maskIndices == nil then
        local result = {}
        for _, entry in ipairs(chromatic) do result[#result+1] = entry[1] end
        return result
    end

    local maskSet = {}
    for _, idx in ipairs(maskIndices) do maskSet[idx] = true end

    local result = {}
    for _, entry in ipairs(chromatic) do
        local midi   = entry[1]
        local pcIdx  = entry[2]
        local relPos = (pcIdx - srPCIdx) % nSteps
        if maskSet[relPos] then
            result[#result+1] = midi
        end
    end
    return result
end

-- helper used inside generatePitches
function round(x, n)
    local m = 10^(n or 0)
    return math.floor(x * m + 0.5) / m
end


-- ---------------------------------------------------------------------------
-- Quantise: nearest value in sorted list
-- ---------------------------------------------------------------------------

local function quantise(grid, value)
    if #grid == 0 then return value end
    local best, bestD = grid[1], math.abs(value - grid[1])
    for i = 2, #grid do
        local d = math.abs(value - grid[i])
        if d < bestD then
            best, bestD = grid[i], d
        elseif d > bestD then
            break
        end
    end
    return best
end


-- ---------------------------------------------------------------------------
-- Predefined tuning systems (MIDI semitone offsets)
-- ---------------------------------------------------------------------------

local TUNING_SYSTEMS = {}

-- EDO
TUNING_SYSTEMS["edo12"] = fromEDO(12)
TUNING_SYSTEMS["edo24"] = fromEDO(24)
TUNING_SYSTEMS["edo31"] = fromEDO(31)
TUNING_SYSTEMS["edo53"] = fromEDO(53)
TUNING_SYSTEMS["edo72"] = fromEDO(72)

-- Non-octave
TUNING_SYSTEMS["bohlenPierce"] = fromRatio(3^(1/13), 13)
TUNING_SYSTEMS["studieII"]     = fromRatio(5^(1/5),  5, 5^(1/5), true)
local phi = (1 + math.sqrt(5)) / 2
TUNING_SYSTEMS["stria"]        = fromRatio(phi, 1, phi, true)

-- Historical temperaments (cents/100 = semitones)
TUNING_SYSTEMS["werckmeister1"] = fromSemitones({0,0.90,1.92,2.94,3.90,4.98,5.88,6.96,7.92,8.88,9.96,10.92})
TUNING_SYSTEMS["werckmeister2"] = fromSemitones({0,0.82,1.96,2.94,3.92,4.98,5.88,6.94,7.84,8.90,10.04,10.86})
TUNING_SYSTEMS["werckmeister3"] = fromSemitones({0,0.96,2.04,3.00,3.96,5.04,6.00,7.02,7.92,9.00,10.02,10.98})
TUNING_SYSTEMS["werckmeister4"] = fromSemitones({0,0.90,1.87,2.98,3.95,4.98,5.95,6.98,7.92,8.93,10.00,10.97})
TUNING_SYSTEMS["kirnberger2"]   = fromSemitones({0,0.90,2.04,2.94,3.86,4.98,5.92,7.02,7.92,8.95,9.96,10.88})
TUNING_SYSTEMS["kirnberger3"]   = fromSemitones({0,0.90,1.95,2.94,3.86,4.98,5.90,6.97,7.92,8.92,9.96,10.88})
TUNING_SYSTEMS["meantoneQC"]    = fromSemitones({0,0.76,1.93,3.10,3.86,5.03,5.79,6.97,8.14,8.90,10.07,10.83})
TUNING_SYSTEMS["pythagorean"]   = fromSemitones({0,1.14,2.04,2.94,4.08,4.98,6.12,7.02,8.16,9.06,9.96,11.10})
TUNING_SYSTEMS["zeta12"]        = fromSemitones({0,1.39,2.04,2.67,3.47,4.98,6.37,7.02,7.65,8.41,9.69,10.49})

-- JI
local function jiS(r) return 12.0 * math.log(r) / math.log(2) end
TUNING_SYSTEMS["JI_5limit_major"]  = fromSemitones({jiS(1),jiS(9/8),jiS(5/4),jiS(4/3),jiS(3/2),jiS(5/3),jiS(15/8)}, 12.0)
TUNING_SYSTEMS["JI_7limit"]        = fromSemitones({jiS(1),jiS(9/8),jiS(7/6),jiS(9/7),jiS(3/2),jiS(7/4),jiS(15/8)}, 12.0)
TUNING_SYSTEMS["harmonicSeries8_16"] = fromSemitones({jiS(8/8),jiS(9/8),jiS(10/8),jiS(11/8),jiS(12/8),jiS(13/8),jiS(14/8),jiS(15/8)}, jiS(2))

-- Maqam (24-EDO)
local function e24(i) return 2^(i/24) end
TUNING_SYSTEMS["maqamRast"]   = fromRatioList({e24(0),e24(4),e24(7),e24(10),e24(14),e24(18),e24(21),e24(24)})
TUNING_SYSTEMS["maqamBayati"] = fromRatioList({e24(0),e24(3),e24(6),e24(10),e24(14),e24(18),e24(21),e24(24)})
TUNING_SYSTEMS["maqamHijaz"]  = fromRatioList({e24(0),e24(2),e24(8),e24(10),e24(14),e24(16),e24(20),e24(24)})

-- Empirical
TUNING_SYSTEMS["slendro_approx"] = fromHz({260.4,295.2,325.0,390.5,433.2}, 260.4)
TUNING_SYSTEMS["pelog_approx"]   = fromHz({260.4,277.2,309.4,347.6,390.5,416.2,463.5}, 260.4)
TUNING_SYSTEMS["AstridsBontempi"] = fromSemitones({
    0,0.19,0.21,1.14,1.19,2.08,2.10,3.18,3.22,3.97,4.15,
    5.08,5.14,6.21,6.21,7.02,7.18,8.19,8.20,9.28,9.35,
    10.29,10.35,11.24,11.29
})


-- ---------------------------------------------------------------------------
-- Scale masks (0-based indices matching Python)
-- ---------------------------------------------------------------------------

local _ALL_MASKS = {
    -- Church modes
    ionian          = {0,2,4,5,7,9,11},
    dorian          = {0,2,3,5,7,9,10},
    phrygian        = {0,1,3,5,7,8,10},
    lydian          = {0,2,4,6,7,9,11},
    mixolydian      = {0,2,4,5,7,9,10},
    aeolian         = {0,2,3,5,7,8,10},
    locrian         = {0,1,3,5,6,8,10},
    -- Harmonic minor modes
    harmonicMinor   = {0,2,3,5,7,8,11},
    locrianSharp6   = {0,1,3,5,6,9,10},
    ionianSharp5    = {0,2,4,5,8,9,11},
    dorianSharp4    = {0,2,3,6,7,9,10},
    phrygianDominant= {0,1,4,5,7,8,10},
    lydianSharp2    = {0,3,4,6,7,9,11},
    ultraLocrian    = {0,1,3,4,6,8,9},
    -- Melodic minor modes
    melodicMinor    = {0,2,3,5,7,9,11},
    dorianFlat2     = {0,1,3,5,7,9,10},
    lydianAugmented = {0,2,4,6,8,9,11},
    lydianDominant  = {0,2,4,6,7,9,10},
    mixolydianFlat6 = {0,2,4,5,7,8,10},
    locrianSharp2   = {0,2,3,5,6,8,10},
    altered         = {0,1,3,4,6,8,10},
    -- Messiaen
    wholeTone       = {0,2,4,6,8,10},
    halfWholeDim    = {0,1,3,4,6,7,9,10},
    messiaen3       = {0,2,3,4,6,7,8,10,11},
    messiaen4       = {0,1,2,5,6,7,8,11},
    messiaen5       = {0,1,5,6,7,11},
    messiaen6       = {0,2,4,5,6,8,10,11},
    messiaen7       = {0,1,2,3,5,6,7,8,9,11},
    -- Pentatonic
    majorPentatonic = {0,2,4,7,9},
    minorPentatonic = {0,3,5,7,10},
    -- Chromatic
    chromatic       = {0,1,2,3,4,5,6,7,8,9,10,11},
}

-- Attach all masks to all 12-note systems
local _12noteSystems = {
    "edo12","werckmeister1","werckmeister2","werckmeister3","werckmeister4",
    "kirnberger2","kirnberger3","meantoneQC","pythagorean","zeta12",
    "JI_5limit_major","JI_7limit","AstridsBontempi",
}
for _, name in ipairs(_12noteSystems) do
    if TUNING_SYSTEMS[name] then
        TUNING_SYSTEMS[name].masks = _ALL_MASKS
    end
end

-- Chromatic mask for other EDOs
for _, name in ipairs({"edo24","edo31","edo53","edo72"}) do
    local ts = TUNING_SYSTEMS[name]
    if ts then
        local n = #ts.pitchClasses
        local chrm = {}
        for i = 0, n-1 do chrm[#chrm+1] = i end
        ts.masks = { chromatic = chrm }
    end
end

-- Bohlen-Pierce masks
TUNING_SYSTEMS["bohlenPierce"].masks = {
    lambda   = {0,1,2,4,5,7,8,9,11,12},
    walker   = {0,2,3,5,6,8,9,11,12},
    chromatic= {0,1,2,3,4,5,6,7,8,9,10,11,12},
}


-- ---------------------------------------------------------------------------
-- pd object
-- ---------------------------------------------------------------------------

local PitchGrid = pd.Class:new():register("PitchGrid")

function PitchGrid:initialize(sel, atoms)
    self.inlets  = 2
    self.outlets = 2

    self.systemName  = "edo12"
    self.lowPitch    = 48.0       -- C3
    self.highPitch   = 84.0       -- C6
    self.tsRoot      = nil        -- tuningSystemRoot (MIDI float or nil)
    self.scaleRoot   = nil        -- scaleRoot (MIDI float or nil)
    self.maskName    = nil
    self.pitchUnit   = "midi"
    self.referenceA  = 440.0
    self.grid        = {}

    -- [PitchGrid <system> <low> <high> <tsRoot>]
    if atoms[1] then self.systemName = tostring(atoms[1]) end
    if atoms[2] then self.lowPitch   = toMidi(atoms[2], self.referenceA, self.pitchUnit) end
    if atoms[3] then self.highPitch  = toMidi(atoms[3], self.referenceA, self.pitchUnit) end
    if atoms[4] then self.tsRoot     = toMidi(atoms[4], self.referenceA, self.pitchUnit) end

    self:buildGrid()
    return true
end

function PitchGrid:buildGrid()
    local ts = TUNING_SYSTEMS[self.systemName]
    if not ts then
        pd.post("PitchGrid: unknown system '" .. self.systemName .. "'")
        self.grid = {}
        return
    end

    local maskIndices = nil
    if self.maskName and ts.masks and ts.masks[self.maskName] then
        maskIndices = ts.masks[self.maskName]
    end

    self.grid = generatePitches(
        ts,
        self.lowPitch,
        self.highPitch,
        self.tsRoot,
        self.scaleRoot,
        maskIndices
    )

    pd.post(string.format(
        "PitchGrid: '%s' %d pitches [%.2f-%.2f] tsRoot=%s scaleRoot=%s mask=%s",
        self.systemName, #self.grid,
        self.lowPitch, self.highPitch,
        self.tsRoot    and string.format("%.2f", self.tsRoot)    or "none",
        self.scaleRoot and string.format("%.2f", self.scaleRoot) or "none",
        self.maskName  or "none"
    ))
end

-- Convert a MIDI float to output unit
function PitchGrid:toOutput(midi)
    if self.pitchUnit == "hz" then
        return midiToHz(midi, self.referenceA)
    else
        return midi  -- midi and spn both output as MIDI float
    end
end

-- Convert input to MIDI float
function PitchGrid:fromInput(val)
    return toMidi(val, self.referenceA, self.pitchUnit)
end

-- Inlet 1: float = quantise, bang = output grid
function PitchGrid:in_1_float(f)
    if #self.grid == 0 then return end
    local inputMidi = self:fromInput(f)
    local qMidi     = quantise(self.grid, inputMidi)
    self:outlet(1, "float", {self:toOutput(qMidi)})
end

function PitchGrid:in_1_bang()
    if #self.grid == 0 then return end
    local out = {}
    for _, midi in ipairs(self.grid) do
        out[#out+1] = self:toOutput(midi)
    end
    self:outlet(2, "list", out)
end

-- Inlet 2 control messages
function PitchGrid:in_2_system(atoms)
    local name = tostring(atoms[1] or "")
    if TUNING_SYSTEMS[name] then
        self.systemName = name
        self.maskName   = nil
        self:buildGrid()
    else
        pd.post("PitchGrid: unknown system '" .. name .. "'")
    end
end

function PitchGrid:in_2_tsRoot(atoms)
    local v = atoms[1]
    self.tsRoot = v and toMidi(v, self.referenceA, self.pitchUnit) or nil
    self:buildGrid()
end

function PitchGrid:in_2_scaleRoot(atoms)
    local v = atoms[1]
    self.scaleRoot = v and toMidi(v, self.referenceA, self.pitchUnit) or nil
    self:buildGrid()
end

function PitchGrid:in_2_mask(atoms)
    local name = tostring(atoms[1] or "none")
    self.maskName = (name == "none") and nil or name
    self:buildGrid()
end

function PitchGrid:in_2_low(atoms)
    self.lowPitch = toMidi(atoms[1], self.referenceA, self.pitchUnit)
    self:buildGrid()
end

function PitchGrid:in_2_high(atoms)
    self.highPitch = toMidi(atoms[1], self.referenceA, self.pitchUnit)
    self:buildGrid()
end

function PitchGrid:in_2_range(atoms)
    self.lowPitch  = toMidi(atoms[1], self.referenceA, self.pitchUnit)
    self.highPitch = toMidi(atoms[2], self.referenceA, self.pitchUnit)
    self:buildGrid()
end

function PitchGrid:in_2_pitchUnit(atoms)
    local u = tostring(atoms[1] or "midi")
    if u == "midi" or u == "hz" or u == "spn" then
        self.pitchUnit = u
        pd.post("PitchGrid: pitchUnit -> " .. u)
    else
        pd.post("PitchGrid: unknown pitchUnit '" .. u .. "' (midi / hz / spn)")
    end
end

function PitchGrid:in_2_referenceA(atoms)
    self.referenceA = tonumber(atoms[1]) or 440.0
    self:buildGrid()
    pd.post("PitchGrid: referenceA -> " .. self.referenceA)
end

-- list dispatcher for messages sent as lists
function PitchGrid:in_2_list(atoms)
    local sel = tostring(atoms[1] or "")
    local map = {
        system      = function() self:in_2_system({atoms[2]}) end,
        tsRoot      = function() self:in_2_tsRoot({atoms[2]}) end,
        scaleRoot   = function() self:in_2_scaleRoot({atoms[2]}) end,
        mask        = function() self:in_2_mask({atoms[2]}) end,
        low         = function() self:in_2_low({atoms[2]}) end,
        high        = function() self:in_2_high({atoms[2]}) end,
        range       = function() self:in_2_range({atoms[2], atoms[3]}) end,
        pitchUnit   = function() self:in_2_pitchUnit({atoms[2]}) end,
        referenceA  = function() self:in_2_referenceA({atoms[2]}) end,
    }
    if map[sel] then map[sel]() end
end
