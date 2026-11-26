--[[
midi2score2.lua — pdlua object

Reads a MIDI file and writes a score2-compatible text file.

score2 format:
    tempo <bpm>;
    timesig <num>/<den>;
    <duration> <pitch>;
    ...

Durations are expressed as fractions of a beat (1/4, 1/8, 1/12 etc.).
The fraction denominator is derived by finding the best rational
approximation of the note's beat duration.
Pitch is MIDI note number (integer).

Creation arguments:
    [midi2score2]

Inlet 1:
    read <path>             — read MIDI file, write score2 to <path>.txt
    read <inpath> <outpath> — read from inpath, write to outpath
    track <n>               — set track number to read (default 0)
    maxdenom <n>            — max denominator for fraction search (default 64)

Outlet 1: bang when done
Outlet 2: error message as symbol if something goes wrong
--]]

local midi2score2 = pd.Class:new():register("midi2score2")

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

-- Greatest common divisor
local function gcd(a, b)
    a, b = math.abs(a), math.abs(b)
    while b > 0 do a, b = b, a % b end
    return a
end

-- Find best rational approximation p/q of x within tolerance,
-- q <= maxDenom. Returns p, q.
local function bestFraction(x, maxDenom, tol)
    tol      = tol or 0.01
    maxDenom = maxDenom or 64
    if x <= 0 then return 0, 1 end

    local bestP, bestQ, bestErr = 1, 1, math.huge
    for q = 1, maxDenom do
        local p   = math.floor(x * q + 0.5)
        local err = math.abs(x - p / q)
        if err < bestErr then
            bestErr = err
            bestP   = p
            bestQ   = q
        end
        if err < tol then break end
    end
    local g = gcd(bestP, bestQ)
    return bestP / g, bestQ / g
end

-- Format a beat duration as a fraction string e.g. "1/4", "3/8"
local function beatFraction(beats, maxDenom)
    local p, q = bestFraction(beats, maxDenom)
    if q == 1 then return tostring(p) end
    return p .. "/" .. q
end

-- Read raw MIDI bytes and parse tempo + note events
local function parseMidi(path, trackNumber)
    local f = io.open(path, "rb")
    if not f then return nil, "Cannot open file: " .. path end
    local data = f:read("*a")
    f:close()

    -- helper: read big-endian integer from byte string at pos
    local function readInt(pos, n)
        local val = 0
        for i = 0, n-1 do
            val = val * 256 + string.byte(data, pos + i)
        end
        return val
    end

    -- read variable-length quantity
    local function readVLQ(pos)
        local val = 0
        local b
        repeat
            b   = string.byte(data, pos)
            val = val * 128 + (b % 128)
            pos = pos + 1
        until b < 128
        return val, pos
    end

    -- parse MIDI header (all positions 1-based)
    -- MThd: bytes 1-4 marker, 5-8 length, 9-10 format, 11-12 numTracks, 13-14 ticksPerBeat
    if data:sub(1,4) ~= "MThd" then return nil, "Not a MIDI file" end
    local numTracks    = readInt(11, 2)
    local ticksPerBeat = readInt(13, 2)

    if trackNumber >= numTracks then
        return nil, "Track " .. trackNumber .. " does not exist (file has " .. numTracks .. ")"
    end

    local tempo  = 500000  -- default 120 bpm
    local events = {}

    -- first MTrk starts immediately after MThd chunk: 4+4+6 = 14 bytes → pos 15
    local pos = 15

    for trackIdx = 0, numTracks - 1 do
        if pos + 3 > #data then
            return nil, "Unexpected end of file at track " .. trackIdx
        end
        if data:sub(pos, pos+3) ~= "MTrk" then
            return nil, "Expected MTrk at position " .. pos .. " (got '" .. data:sub(pos, pos+3) .. "')"
        end
        local trackLen = readInt(pos+4, 4)
        local trackEnd = pos + 8 + trackLen
        local cur      = pos + 8  -- first byte of track data
        local tick     = 0

        -- active note_ons: noteOns[pitch] = startTick
        local noteOns = {}
        local lastStatus = 0

        while cur < trackEnd do
            -- delta time
            local delta
            delta, cur = readVLQ(cur)
            tick = tick + delta

            local statusByte = string.byte(data, cur)

            -- running status
            if statusByte < 0x80 then
                statusByte = lastStatus
            else
                lastStatus = statusByte
                cur = cur + 1
            end

            local msgType = math.floor(statusByte / 16) * 16
            local channel = statusByte % 16

            if statusByte == 0xFF then
                -- meta event
                local metaType = string.byte(data, cur); cur = cur + 1
                local metaLen;  metaLen, cur = readVLQ(cur)
                if metaType == 0x51 and metaLen == 3 then
                    -- set_tempo
                    local t = readInt(cur, 3)
                    if trackIdx == 0 or tempo == 500000 then
                        tempo = t
                    end
                end
                cur = cur + metaLen

            elseif msgType == 0x90 then
                -- note_on
                local pitch = string.byte(data, cur);     cur = cur + 1
                local vel   = string.byte(data, cur);     cur = cur + 1
                if vel > 0 then
                    if trackIdx == trackNumber then
                        noteOns[pitch] = tick
                    end
                else
                    -- note_on vel=0 = note_off
                    if trackIdx == trackNumber and noteOns[pitch] then
                        local durTicks = tick - noteOns[pitch]
                        events[#events+1] = {
                            tick     = noteOns[pitch],
                            durTicks = durTicks,
                            pitch    = pitch,
                        }
                        noteOns[pitch] = nil
                    end
                end

            elseif msgType == 0x80 then
                -- note_off
                local pitch = string.byte(data, cur); cur = cur + 1
                local vel   = string.byte(data, cur); cur = cur + 1
                if trackIdx == trackNumber and noteOns[pitch] then
                    local durTicks = tick - noteOns[pitch]
                    events[#events+1] = {
                        tick     = noteOns[pitch],
                        durTicks = durTicks,
                        pitch    = pitch,
                    }
                    noteOns[pitch] = nil
                end

            elseif msgType == 0xA0 or msgType == 0xB0 or msgType == 0xE0 then
                cur = cur + 2
            elseif msgType == 0xC0 or msgType == 0xD0 then
                cur = cur + 1
            elseif msgType == 0xF0 then
                -- sysex
                local sysexLen; sysexLen, cur = readVLQ(cur)
                cur = cur + sysexLen
            else
                cur = cur + 1
            end
        end
        pos = trackEnd
    end

    -- sort events by tick
    table.sort(events, function(a, b) return a.tick < b.tick end)

    return {
        ticksPerBeat = ticksPerBeat,
        tempo        = tempo,
        events       = events,
    }
end


-- ---------------------------------------------------------------------------
-- score2 writer
-- ---------------------------------------------------------------------------

local function writeScore2(parsed, outPath, maxDenom)
    local bpm          = math.floor(60000000 / parsed.tempo + 0.5)
    local ticksPerBeat = parsed.ticksPerBeat
    local events       = parsed.events

    local lines = {}
    lines[#lines+1] = "tempo " .. bpm .. ";"

    -- detect time signature from note spacing (simple heuristic: skip for now)
    -- write a placeholder — user can edit
    lines[#lines+1] = "timesig 4/4;"

    -- convert events: sort by tick, emit rests for gaps, emit notes
    local curTick = 0
    for _, ev in ipairs(events) do
        -- gap before this note = rest
        local gapTicks = ev.tick - curTick
        if gapTicks > 0 then
            local gapBeats  = gapTicks / ticksPerBeat
            local fracStr   = beatFraction(gapBeats, maxDenom)
            lines[#lines+1] = fracStr .. " r;"
        end

        local durBeats = ev.durTicks / ticksPerBeat
        local fracStr  = beatFraction(durBeats, maxDenom)
        lines[#lines+1] = fracStr .. " " .. ev.pitch .. ";"

        curTick = ev.tick + ev.durTicks
    end

    local f, err = io.open(outPath, "w")
    if not f then return false, err end
    f:write(table.concat(lines, "\n") .. "\n")
    f:close()
    return true
end


-- ---------------------------------------------------------------------------
-- pd object
-- ---------------------------------------------------------------------------

function midi2score2:initialize(sel, atoms)
    self.inlets   = 1
    self.outlets  = 2
    self.track    = 0
    self.maxDenom = 64
    return true
end

function midi2score2:in_1_read(atoms)
    local inPath  = tostring(atoms[1] or "")
    local outPath = tostring(atoms[2] or (inPath:gsub("%.mid$", "") .. ".score2.txt"))

    if inPath == "" then
        pd.post("midi2score2: read needs a file path")
        self:outlet(2, "symbol", {"no path given"})
        return
    end

    local parsed, err = parseMidi(inPath, self.track)
    if not parsed then
        pd.post("midi2score2: " .. (err or "parse error"))
        self:outlet(2, "symbol", {err or "parse error"})
        return
    end

    pd.post(string.format(
        "midi2score2: %d events, bpm=%d, ticksPerBeat=%d",
        #parsed.events,
        math.floor(60000000 / parsed.tempo + 0.5),
        parsed.ticksPerBeat
    ))

    local ok, werr = writeScore2(parsed, outPath, self.maxDenom)
    if not ok then
        pd.post("midi2score2: write error: " .. (werr or ""))
        self:outlet(2, "symbol", {werr or "write error"})
        return
    end

    pd.post("midi2score2: written -> " .. outPath)
    self:outlet(1, "bang", {})
end

function midi2score2:in_1_track(atoms)
    self.track = math.max(0, math.floor(tonumber(atoms[1]) or 0))
    pd.post("midi2score2: track -> " .. self.track)
end

function midi2score2:in_1_maxdenom(atoms)
    self.maxDenom = math.max(1, math.floor(tonumber(atoms[1]) or 64))
    pd.post("midi2score2: maxdenom -> " .. self.maxDenom)
end

function midi2score2:in_1_list(atoms)
    local sel = tostring(atoms[1] or "")
    local rest = {}
    for i = 2, #atoms do rest[#rest+1] = atoms[i] end
    if     sel == "read"     then self:in_1_read(rest)
    elseif sel == "track"    then self:in_1_track(rest)
    elseif sel == "maxdenom" then self:in_1_maxdenom(rest)
    else   self:in_1_read(atoms)
    end
end