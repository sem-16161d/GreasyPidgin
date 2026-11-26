--[[
multitoggle.lua — pdlua GUI object

A matrix of toggle buttons. Click any cell to flip it between 0 and 1.

Creation arguments:
    [multitoggle <cols> <rows> <cellSize>]
    e.g. [multitoggle 8 4 24]
    Defaults: cols=8, rows=4, cellSize=24

Inlet 1:
    bang            — output the full matrix as rows of lists
    list <r> <c> <v> — set cell at row r, col c to value v (0 or 1)
    set <r> <c> <v>  — same as list but no output
    clear            — set all cells to 0, output
    fill             — set all cells to 1, output
    row <r>          — output row r as a list of 0s and 1s
    col <c>          — output col c as a list of 0s and 1s

Outlet 1: on click → list <row> <col> <value>  (the changed cell)
Outlet 2: on bang  → full matrix as a flat list (row by row)

--]]

local multitoggle = pd.Class:new():register("multitoggle")

-- ---------------------------------------------------------------------------
-- Colours (pd colour format: -integer)
-- ---------------------------------------------------------------------------
local COL_BG      = -1           -- white background
local COL_ON      = -16777216    -- black cell (on)
local COL_OFF     = -262144*0    -- light grey cell (off) — pd uses 0 for default grey
local COL_GRID    = -4144960     -- dark grey grid lines
local COL_BORDER  = -1118482     -- border

-- ---------------------------------------------------------------------------
-- Initialise
-- ---------------------------------------------------------------------------

function multitoggle:initialize(sel, atoms)
    self.inlets  = 1
    self.outlets = 2

    self.cols     = math.max(1, math.floor(tonumber(atoms[1]) or 8))
    self.rows     = math.max(1, math.floor(tonumber(atoms[2]) or 4))
    self.cellSize = math.max(8,  math.floor(tonumber(atoms[3]) or 24))

    self.width  = self.cols * self.cellSize
    self.height = self.rows * self.cellSize

    -- state matrix: grid[row][col] = 0 or 1
    self.grid = {}
    for r = 1, self.rows do
        self.grid[r] = {}
        for c = 1, self.cols do
            self.grid[r][c] = 0
        end
    end

    self:set_size(self.width, self.height)
    return true
end

-- ---------------------------------------------------------------------------
-- Drawing
-- ---------------------------------------------------------------------------

function multitoggle:paint(g)
    local cs = self.cellSize

    -- background
    g:set_color(240, 240, 240)
    g:fill_rect(0, 0, self.width, self.height)

    -- cells
    for r = 1, self.rows do
        for c = 1, self.cols do
            local x = (c - 1) * cs
            local y = (r - 1) * cs
            if self.grid[r][c] == 1 then
                g:set_color(30, 30, 30)      -- on: dark
            else
                g:set_color(200, 200, 200)   -- off: light grey
            end
            g:fill_rect(x + 1, y + 1, cs - 2, cs - 2)
        end
    end

    -- grid lines
    g:set_color(120, 120, 120)
    for c = 0, self.cols do
        g:draw_line(c * cs, 0, c * cs, self.height, 1)
    end
    for r = 0, self.rows do
        g:draw_line(0, r * cs, self.width, r * cs, 1)
    end
end

function multitoggle:get_size()
    return self.width, self.height
end

-- ---------------------------------------------------------------------------
-- Mouse interaction
-- ---------------------------------------------------------------------------

function multitoggle:mouse_down(x, y)
    local cs  = self.cellSize
    local col = math.floor(x / cs) + 1
    local row = math.floor(y / cs) + 1
    if col < 1 or col > self.cols or row < 1 or row > self.rows then return end

    -- flip
    self.grid[row][col] = 1 - self.grid[row][col]
    self:repaint()

    -- outlet 1: which cell changed and its new value
    self:outlet(1, "list", {row, col, self.grid[row][col]})
end

-- ---------------------------------------------------------------------------
-- Output helpers
-- ---------------------------------------------------------------------------

function multitoggle:outputFlat()
    local flat = {}
    for r = 1, self.rows do
        for c = 1, self.cols do
            flat[#flat + 1] = self.grid[r][c]
        end
    end
    self:outlet(2, "list", flat)
end

function multitoggle:outputRow(r)
    if r < 1 or r > self.rows then
        pd.post("multitoggle: row " .. r .. " out of range")
        return
    end
    local out = {}
    for c = 1, self.cols do
        out[#out + 1] = self.grid[r][c]
    end
    self:outlet(2, "list", out)
end

function multitoggle:outputCol(c)
    if c < 1 or c > self.cols then
        pd.post("multitoggle: col " .. c .. " out of range")
        return
    end
    local out = {}
    for r = 1, self.rows do
        out[#out + 1] = self.grid[r][c]
    end
    self:outlet(2, "list", out)
end

-- ---------------------------------------------------------------------------
-- Inlet messages
-- ---------------------------------------------------------------------------

function multitoggle:in_1_bang()
    self:outputFlat()
end

function multitoggle:in_1_row(atoms)
    self:outputRow(math.floor(tonumber(atoms[1]) or 1))
end

function multitoggle:in_1_col(atoms)
    self:outputCol(math.floor(tonumber(atoms[1]) or 1))
end

function multitoggle:in_1_clear()
    for r = 1, self.rows do
        for c = 1, self.cols do
            self.grid[r][c] = 0
        end
    end
    self:repaint()
    self:outputFlat()
end

function multitoggle:in_1_fill()
    for r = 1, self.rows do
        for c = 1, self.cols do
            self.grid[r][c] = 1
        end
    end
    self:repaint()
    self:outputFlat()
end

-- list <row> <col> <value> — set a cell and output
function multitoggle:in_1_list(atoms)
    -- check if it's a named message routed as list
    local first = tostring(atoms[1] or "")
    if     first == "set"   then self:in_1_set({atoms[2], atoms[3], atoms[4]})
    elseif first == "row"   then self:in_1_row({atoms[2]})
    elseif first == "col"   then self:in_1_col({atoms[2]})
    elseif first == "clear" then self:in_1_clear()
    elseif first == "fill"  then self:in_1_fill()
    elseif first == "bin"   then
        local vals = {}
        for i = 2, #atoms do vals[#vals+1] = atoms[i] end
        self:in_1_bin(vals)
    else
        -- treat as: row col value
        local r = math.floor(tonumber(atoms[1]) or 1)
        local c = math.floor(tonumber(atoms[2]) or 1)
        local v = math.floor(tonumber(atoms[3]) or 0)
        if r >= 1 and r <= self.rows and c >= 1 and c <= self.cols then
            self.grid[r][c] = (v ~= 0) and 1 or 0
            self:repaint()
            self:outlet(1, "list", {r, c, self.grid[r][c]})
        end
    end
end

function multitoggle:in_1_bin(atoms)
    -- fill grid row by row from a flat binary list
    -- values beyond cols*rows are ignored
    local idx = 1
    for r = 1, self.rows do
        for c = 1, self.cols do
            if atoms[idx] ~= nil then
                self.grid[r][c] = (math.floor(tonumber(atoms[idx]) or 0) ~= 0) and 1 or 0
                idx = idx + 1
            end
        end
    end
    self:repaint()
end


-- set <row> <col> <value> — set a cell silently (no output)
function multitoggle:in_1_set(atoms)
    local r = math.floor(tonumber(atoms[1]) or 1)
    local c = math.floor(tonumber(atoms[2]) or 1)
    local v = math.floor(tonumber(atoms[3]) or 0)
    if r >= 1 and r <= self.rows and c >= 1 and c <= self.cols then
        self.grid[r][c] = (v ~= 0) and 1 or 0
        self:repaint()
    end
end