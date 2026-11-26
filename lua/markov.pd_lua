--[[
markov.lua — pdlua object

A first/higher-order Markov chain working with numbers.
States are tuples of numbers. Transitions are weighted.

Creation arguments:
    [markov <order>]
    e.g. [markov 2]
    Default: order=1

Inlet 1:
    train <n0> <n1> ...   — set training sequence and learn rules
    next                  — generate one next element from current state
    bang                  — same as next
    float N               — generate N elements, output as list
    seed <n0> <n1> ...    — set current state manually (order values)
    reset                 — return to seed state
    clear                 — clear all rules
    order <n>             — change order (clears rules)

Outlet 1: next generated element (float)
Outlet 2: current state as list
Outlet 3: number of unique states known (float)
--]]

local markov = pd.Class:new():register("markov")

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local function stateKey(state)
    return table.concat(state, "_")
end

local function chooseWeighted(elements, weights)
    local total = 0
    for _, w in ipairs(weights) do total = total + w end
    local r = math.random() * total
    local cum = 0
    for i, w in ipairs(weights) do
        cum = cum + w
        if r <= cum then return elements[i] end
    end
    return elements[#elements]
end

-- ---------------------------------------------------------------------------
-- Initialise
-- ---------------------------------------------------------------------------

function markov:initialize(sel, atoms)
    self.inlets  = 1
    self.outlets = 3

    self.order   = math.max(1, math.floor(tonumber(atoms[1]) or 1))
    self.rules   = {}   -- rules[stateKey] = {state, elements=[], weights=[]}
    self.state   = {}   -- current state (list of self.order numbers)
    self.seed    = {}   -- stored seed state

    math.randomseed(os.time())
    return true
end

-- ---------------------------------------------------------------------------
-- Training
-- ---------------------------------------------------------------------------

function markov:learn(seq)
    self.rules = {}
    local n    = #seq
    local ord  = self.order

    if n < ord + 1 then
        pd.post("markov: sequence too short for order " .. ord)
        return
    end

    -- wrap sequence so every state has a successor
    local wrapped = {}
    for _, v in ipairs(seq) do wrapped[#wrapped+1] = v end
    for i = 1, ord do wrapped[#wrapped+1] = seq[i] end

    -- collect (state → nextElement) pairs
    local pairs_ = {}   -- list of {state, next}
    for i = 1, #wrapped - ord do
        local state = {}
        for j = 0, ord-1 do state[#state+1] = wrapped[i+j] end
        local next  = wrapped[i + ord]
        pairs_[#pairs_+1] = {state=state, next=next}
    end

    -- group by state key
    local grouped = {}  -- key → {state, counts={elem→count}}
    for _, p in ipairs(pairs_) do
        local key = stateKey(p.state)
        if not grouped[key] then
            grouped[key] = {state=p.state, counts={}}
        end
        local c = grouped[key].counts
        c[p.next] = (c[p.next] or 0) + 1
    end

    -- build rules
    for key, entry in pairs(grouped) do
        local elements = {}
        local weights  = {}
        for elem, count in pairs(entry.counts) do
            elements[#elements+1] = elem
            weights[#weights+1]   = count
        end
        self.rules[key] = {
            state    = entry.state,
            elements = elements,
            weights  = weights,
        }
    end

    pd.post("markov: trained — " .. #seq .. " events, " .. self._ruleCount() .. " states")
    self:outputState()
end

function markov:_ruleCount()
    local n = 0
    for _ in pairs(self.rules) do n = n + 1 end
    return n
end

-- ---------------------------------------------------------------------------
-- Generation
-- ---------------------------------------------------------------------------

function markov:_nextElement()
    if #self.state < self.order then
        pd.post("markov: no state set — use [seed <n0> <n1> ...]")
        return nil
    end
    local key  = stateKey(self.state)
    local rule = self.rules[key]
    if not rule then
        -- unknown state: pick a random known state
        local keys = {}
        for k in pairs(self.rules) do keys[#keys+1] = k end
        if #keys == 0 then
            pd.post("markov: no rules")
            return nil
        end
        key  = keys[math.random(#keys)]
        rule = self.rules[key]
        pd.post("markov: unknown state, jumping to random state")
    end
    local next = chooseWeighted(rule.elements, rule.weights)
    -- advance state
    table.remove(self.state, 1)
    self.state[#self.state+1] = next
    return next
end

function markov:outputState()
    self:outlet(3, "float", {self:_ruleCount()})
    self:outlet(2, "list",  self.state)
end

-- ---------------------------------------------------------------------------
-- Inlet messages
-- ---------------------------------------------------------------------------

function markov:in_1_bang()
    local next = self:_nextElement()
    if next ~= nil then
        self:outlet(1, "float", {next})
        self:outlet(2, "list",  self.state)
    end
end

function markov:in_1_float(f)
    local n = math.max(1, math.floor(f))
    local out = {}
    for _ = 1, n do
        local next = self:_nextElement()
        if next == nil then break end
        out[#out+1] = next
    end
    if #out > 0 then
        self:outlet(1, "list",  out)
        self:outlet(2, "list",  self.state)
    end
end

function markov:in_1_next()
    self:in_1_bang()
end

function markov:in_1_train(atoms)
    if #atoms < self.order + 1 then
        pd.post("markov: need at least " .. (self.order+1) .. " values to train")
        return
    end
    local seq = {}
    for _, v in ipairs(atoms) do seq[#seq+1] = tonumber(v) or 0 end
    self:learn(seq)
    -- auto-set seed to first state
    self.seed  = {}
    self.state = {}
    for i = 1, self.order do
        self.seed[i]  = seq[i]
        self.state[i] = seq[i]
    end
    self:outputState()
end

function markov:in_1_seed(atoms)
    if #atoms < self.order then
        pd.post("markov: seed needs " .. self.order .. " value(s)")
        return
    end
    self.seed  = {}
    self.state = {}
    for i = 1, self.order do
        self.seed[i]  = tonumber(atoms[i]) or 0
        self.state[i] = self.seed[i]
    end
    self:outputState()
end

function markov:in_1_reset()
    self.state = {}
    for _, v in ipairs(self.seed) do self.state[#self.state+1] = v end
    self:outputState()
end

function markov:in_1_clear()
    self.rules = {}
    self.state = {}
    self.seed  = {}
    pd.post("markov: cleared")
    self:outlet(3, "float", {0})
end

function markov:in_1_order(atoms)
    local o = math.max(1, math.floor(tonumber(atoms[1]) or 1))
    self.order = o
    self.rules = {}
    self.state = {}
    self.seed  = {}
    pd.post("markov: order -> " .. o .. " (rules cleared)")
    self:outlet(3, "float", {0})
end

function markov:in_1_list(atoms)
    local sel = tostring(atoms[1] or "")
    local rest = {}
    for i = 2, #atoms do rest[#rest+1] = atoms[i] end

    if     sel == "train" then self:in_1_train(rest)
    elseif sel == "seed"  then self:in_1_seed(rest)
    elseif sel == "order" then self:in_1_order(rest)
    elseif sel == "next"  then self:in_1_bang()
    elseif sel == "reset" then self:in_1_reset()
    elseif sel == "clear" then self:in_1_clear()
    else
        -- plain list of numbers → treat as training sequence
        local allNums = true
        for _, v in ipairs(atoms) do
            if tonumber(v) == nil then allNums = false; break end
        end
        if allNums then self:in_1_train(atoms) end
    end
end