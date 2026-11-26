--[[
LSystem.lua — pdlua object

A Lindenmayer System rewriting engine working entirely with integers.
Symbols are non-negative integers. Rules map one integer to a sequence
of integers. Constants (symbols with no explicit rule) are automatically
treated as identity (symbol → symbol).

Creation arguments:
    [LSystem]   — empty, set axiom and rules via messages

Inlet 1:
    axiom <n0> <n1> ...     — set the axiom (list of integers), reset
    rule <pred> <s0> <s1>   — add/replace rule: pred → [s0, s1, ...]
    clearRules              — remove all rules
    step                    — one rewriting step, output result
    iterate <n>             — n rewriting steps, output result
    reset                   — return to axiom, output it
    bang                    — output current generation

Outlet 1: current generation as a list of integers
Outlet 2: generation index (float)
Outlet 3: length of current generation (float)

Example patch:
    [axiom 0 1 0(         → set axiom
    [rule 0 0 1(          → 0 → 0 1
    [rule 1 0(            → 1 → 0
    [iterate 5(           → run 5 steps
    → outlet 1 gives the current generation as a list
--]]

local LSystem = pd.Class:new():register("LSystem")

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local function flatten(lst)
    local result = {}
    for _, item in ipairs(lst) do
        if type(item) == "table" then
            for _, v in ipairs(flatten(item)) do
                result[#result+1] = v
            end
        else
            result[#result+1] = item
        end
    end
    return result
end

-- ---------------------------------------------------------------------------
-- Initialise
-- ---------------------------------------------------------------------------

function LSystem:initialize(sel, atoms)
    self.inlets  = 1
    self.outlets = 3

    self.axiom       = {}   -- list of integers
    self.rules       = {}   -- rules[pred] = {s0, s1, ...}
    self.generations = {}   -- generations[0] = axiom, generations[n] = nth gen
    self.genIndex    = 0

    return true
end

-- ---------------------------------------------------------------------------
-- Core
-- ---------------------------------------------------------------------------

function LSystem:currentGen()
    return self.generations[self.genIndex] or {}
end

function LSystem:applyRules(gen)
    -- constants: symbols with no explicit rule → identity
    local newGen = {}
    for _, symbol in ipairs(gen) do
        local successor = self.rules[symbol]
        if successor then
            for _, s in ipairs(successor) do
                newGen[#newGen+1] = s
            end
        else
            -- identity rule for constants
            newGen[#newGen+1] = symbol
        end
    end
    return newGen
end

function LSystem:doStep()
    local cur    = self:currentGen()
    local newGen = self:applyRules(cur)
    self.genIndex = self.genIndex + 1
    self.generations[self.genIndex] = newGen
    return newGen
end

function LSystem:outputCurrent()
    local gen = self:currentGen()
    self:outlet(3, "float", {#gen})
    self:outlet(2, "float", {self.genIndex})
    if #gen > 0 then
        self:outlet(1, "list", gen)
    else
        self:outlet(1, "bang", {})
    end
end

-- ---------------------------------------------------------------------------
-- Inlet messages
-- ---------------------------------------------------------------------------

function LSystem:in_1_bang()
    self:outputCurrent()
end

function LSystem:in_1_axiom(atoms)
    if #atoms == 0 then
        pd.post("LSystem: axiom message needs at least one integer")
        return
    end
    local ax = {}
    for _, v in ipairs(atoms) do
        ax[#ax+1] = math.floor(tonumber(v) or 0)
    end
    self.axiom       = ax
    self.genIndex    = 0
    self.generations = {[0] = ax}
    pd.post("LSystem: axiom set, " .. #ax .. " symbols")
    self:outputCurrent()
end

function LSystem:in_1_rule(atoms)
    if #atoms < 1 then
        pd.post("LSystem: rule needs at least a predecessor")
        return
    end
    local pred      = math.floor(tonumber(atoms[1]) or 0)
    local successor = {}
    for i = 2, #atoms do
        successor[#successor+1] = math.floor(tonumber(atoms[i]) or 0)
    end
    -- rule with no successor = erase symbol (empty successor)
    self.rules[pred] = (#successor > 0) and successor or {}
    local succStr = (#successor > 0) and table.concat(successor, " ") or "(erase)"
    pd.post("LSystem: rule " .. pred .. " → " .. succStr)
end

function LSystem:in_1_clearRules()
    self.rules = {}
    pd.post("LSystem: all rules cleared")
end

function LSystem:in_1_step()
    if #self.axiom == 0 then
        pd.post("LSystem: no axiom set")
        return
    end
    self:doStep()
    self:outputCurrent()
end

function LSystem:in_1_float(f)
    -- float = iterate N steps
    local n = math.max(1, math.floor(f))
    if #self.axiom == 0 then
        pd.post("LSystem: no axiom set")
        return
    end
    for _ = 1, n do
        self:doStep()
    end
    self:outputCurrent()
end

function LSystem:in_1_iterate(atoms)
    local n = math.max(1, math.floor(tonumber(atoms[1]) or 1))
    if #self.axiom == 0 then
        pd.post("LSystem: no axiom set")
        return
    end
    for _ = 1, n do
        self:doStep()
    end
    self:outputCurrent()
end

function LSystem:in_1_reset()
    self.genIndex    = 0
    self.generations = {[0] = self.axiom}
    pd.post("LSystem: reset to axiom (gen 0)")
    self:outputCurrent()
end

function LSystem:in_1_list(atoms)
    -- dispatch named messages sent as lists
    local sel = tostring(atoms[1] or "")
    if sel == "axiom" then
        local rest = {}
        for i = 2, #atoms do rest[#rest+1] = atoms[i] end
        self:in_1_axiom(rest)
    elseif sel == "rule" then
        local rest = {}
        for i = 2, #atoms do rest[#rest+1] = atoms[i] end
        self:in_1_rule(rest)
    elseif sel == "iterate" then
        self:in_1_iterate({atoms[2]})
    elseif sel == "step"       then self:in_1_step()
    elseif sel == "reset"      then self:in_1_reset()
    elseif sel == "clearRules" then self:in_1_clearRules()
    else
        -- treat a plain list of numbers as a new axiom
        local allNumbers = true
        for _, v in ipairs(atoms) do
            if tonumber(v) == nil then allNumbers = false; break end
        end
        if allNumbers then
            self:in_1_axiom(atoms)
        end
    end
end