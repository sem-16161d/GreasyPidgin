--[[
wolfram.lua — pdlua object
Wolfram elementary cellular automaton (1D, 2-state, 3-cell neighbourhood).

Creation arguments:
    [wolfram <ruleNumber> <size> <startMode>]
    e.g.  [wolfram 30 32 centre]
    Defaults: rule=30, size=32, startMode=centre

    startMode:
        centre  — single active cell in the middle (default)
        random  — random initial state
        <int>   — gen0 from binary representation of that integer

Inlet 1 (left) — control:
    bang            — compute one generation and output it
    float           — compute N generations and output the last
    rule <0-255>    — change the rule number (rebuilds lookup, resets)
    reset           — reset to generation 0
    size <n>        — resize the automaton (resets)
    seed <int>      — set gen0 from integer (resets)
    random          — randomise gen0 (resets)
    centre          — set gen0 to single centre cell (resets)

Outlet 1: current generation as a list of 0s and 1s
Outlet 2: generation index (float)
Outlet 3: integer value of the current generation (binary → int)
--]]


-- ---------------------------------------------------------------------------
-- Build Wolfram lookup table from rule number
-- ---------------------------------------------------------------------------

local function buildLookup(ruleNumber)
    -- 8 possible 3-bit neighbourhoods: 111, 110, ... 000
    -- rule bit i corresponds to neighbourhood with integer value (7-i)
    local lookup = {}
    for i = 0, 7 do
        local neighbourhood = string.format("%03d", tonumber(string.format("%d%d%d",
            math.floor(i / 4) % 2,
            math.floor(i / 2) % 2,
            i % 2)))
        -- bit position in the rule: neighbourhood 111=7 → bit 7, 000=0 → bit 0
        local bit = math.floor(ruleNumber / (2 ^ i)) % 2
        lookup[neighbourhood] = bit
    end
    return lookup
end

-- convert a cell array to its integer value (MSB first)
local function cellsToInt(cells)
    local n   = #cells
    local val = 0
    for i = 1, n do
        val = val + cells[i] * (2 ^ (n - i))
    end
    return val
end


-- ---------------------------------------------------------------------------
-- pd object
-- ---------------------------------------------------------------------------

local wolfram = pd.Class:new():register("wolfram")

function wolfram:initialize(sel, atoms)
    self.inlets  = 1
    self.outlets = 3

    -- defaults
    self.ruleNumber = 30
    self.size       = 32
    self.startMode  = "centre"
    self.genIndex   = 0
    self.gen        = {}
    self.lookup     = {}

    -- parse creation args: [wolfram <rule> <size> <startMode>]
    if atoms[1] then self.ruleNumber = math.max(0, math.min(255, math.floor(tonumber(atoms[1]) or 30))) end
    if atoms[2] then self.size       = math.max(1, math.floor(tonumber(atoms[2]) or 32)) end
    if atoms[3] then self.startMode  = tostring(atoms[3]) end

    self.lookup = buildLookup(self.ruleNumber)
    self:reset()
    return true
end


-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

function wolfram:setGenFromCentre()
    self.gen = {}
    for i = 1, self.size do
        self.gen[i] = 0
    end
    self.gen[math.ceil(self.size / 2)] = 1
end

function wolfram:setGenFromRandom()
    self.gen = {}
    for i = 1, self.size do
        self.gen[i] = math.random(0, 1)
    end
end

function wolfram:setGenFromInt(n)
    -- binary representation of n, padded/truncated to self.size
    local bits = {}
    local tmp  = math.max(0, math.floor(n))
    for i = self.size, 1, -1 do
        bits[i] = tmp % 2
        tmp     = math.floor(tmp / 2)
    end
    self.gen = bits
end

function wolfram:reset()
    self.genIndex = 0
    local mode = self.startMode
    if mode == "centre" then
        self:setGenFromCentre()
    elseif mode == "random" then
        self:setGenFromRandom()
    else
        local n = tonumber(mode)
        if n then
            self:setGenFromInt(n)
        else
            self:setGenFromCentre()
        end
    end
end

function wolfram:step()
    local old = self.gen
    local n   = #old
    local new = {}
    for i = 1, n do
        local pre  = old[((i - 2) % n) + 1]
        local cur  = old[i]
        local post = old[(i % n) + 1]
        local key  = string.format("%d%d%d", pre, cur, post)
        new[i]     = self.lookup[key] or 0
    end
    self.gen      = new
    self.genIndex = self.genIndex + 1
end

function wolfram:output()
    -- outlet 3: integer value
    self:outlet(3, "float", {cellsToInt(self.gen)})
    -- outlet 2: generation index
    self:outlet(2, "float", {self.genIndex})
    -- outlet 1: generation as list
    self:outlet(1, "list", self.gen)
end


-- ---------------------------------------------------------------------------
-- Inlet 1 messages
-- ---------------------------------------------------------------------------

function wolfram:in_1_bang()
    self:step()
    self:output()
end

function wolfram:in_1_float(f)
    -- compute N steps, output only the last
    local n = math.max(1, math.floor(f))
    for _ = 1, n do
        self:step()
    end
    self:output()
end

function wolfram:in_1_rule(atoms)
    local r = math.max(0, math.min(255, math.floor(tonumber(atoms[1]) or 30)))
    self.ruleNumber = r
    self.lookup     = buildLookup(r)
    self:reset()
    pd.post("wolfram: rule -> " .. r)
end

function wolfram:in_1_reset()
    self:reset()
    self:output()
end

function wolfram:in_1_size(atoms)
    local s   = math.max(1, math.floor(tonumber(atoms[1]) or 32))
    self.size = s
    self:reset()
    pd.post("wolfram: size -> " .. s)
end

function wolfram:in_1_seed(atoms)
    local n           = math.floor(tonumber(atoms[1]) or 0)
    self.startMode    = tostring(n)
    self:setGenFromInt(n)
    self.genIndex     = 0
    self:output()
    pd.post("wolfram: seed -> " .. n)
end

function wolfram:in_1_random()
    self.startMode = "random"
    self:setGenFromRandom()
    self.genIndex  = 0
    self:output()
end

function wolfram:in_1_centre()
    self.startMode = "centre"
    self:setGenFromCentre()
    self.genIndex  = 0
    self:output()
end

-- catch list messages e.g. [rule 30( sent as a list
function wolfram:in_1_list(atoms)
    local sel = tostring(atoms[1] or "")
    if     sel == "rule"   then self:in_1_rule({atoms[2]})
    elseif sel == "size"   then self:in_1_size({atoms[2]})
    elseif sel == "seed"   then self:in_1_seed({atoms[2]})
    elseif sel == "reset"  then self:in_1_reset()
    elseif sel == "random" then self:in_1_random()
    elseif sel == "centre" then self:in_1_centre()
    end
end