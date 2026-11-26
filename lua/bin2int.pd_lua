--[[
bin2int.lua — pdlua object

Converts a list of binary values (0s and 1s) to an integer.
The list is read MSB first (leftmost = most significant bit).

Creation arguments: none

Inlet 1:
    list    — list of 0s and 1s → outputs integer on outlet 1
    bang    — re-output the last computed integer

Outlet 1: integer value (float)

Example:
    [list 1 0 0 0 0 0 0 0( → 128
    [list 0 0 0 0 0 0 0 1( → 1
    [list 1 1 1 1 0 0 0 0( → 240

    Typical use with [wolfram]:
    [wolfram 30 8 centre]
    |
    [bin2int]
    |
    [print intValue]
--]]

local bin2int = pd.Class:new():register("bin2int")

function bin2int:initialize(sel, atoms)
    self.inlets  = 1
    self.outlets = 1
    self.last    = 0
    return true
end

function bin2int:in_1_list(atoms)
    local val = 0
    local n   = #atoms
    for i = 1, n do
        local bit = math.floor(tonumber(atoms[i]) or 0)
        if bit ~= 0 then bit = 1 end   -- clamp to binary
        val = val + bit * (2 ^ (n - i))
    end
    self.last = math.floor(val)
    self:outlet(1, "float", {self.last})
end

function bin2int:in_1_bang()
    self:outlet(1, "float", {self.last})
end