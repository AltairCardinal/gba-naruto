-- Dump the second background layer's tilemap (and the display registers) once
-- per frame.
--
-- Why: the pixel diff can only say "these pixels differ".  The original's
-- second background layer has already been exported as a *cell-level* ground
-- truth (1024 cells, each with a family, a palette bank and a tile index).
-- Reading the same layer out of the remake, cell by cell, turns the problem
-- from "where do the pixels differ" into "which tilemap entries differ" --
-- which is directly actionable.
--
-- Environment:
--   DUMP_BG2_OUTPUT_DIR    where to write the per-frame dumps (must exist)
--   DUMP_BG2_KEY           optional key to press, like the recording scripts
--   DUMP_BG2_KEY_SEQUENCE  optional comma separated key sequence
--   DUMP_BG2_HOLD_FRAMES   frames to hold each key (default 4)
--   DUMP_BG2_ZERO_FRAMES   frames to wait before the first key (default 0)
--
-- Outputs, per frame index:
--   frame-NNN.bin    2048 bytes: the BG2 tilemap, 1024 little endian halfwords
--   frame-NNN.json   one line: the registers that describe that frame

local function required_env(name)
    local value = os.getenv(name)
    assert(value and value ~= "", "missing environment variable " .. name)
    return value
end

local function optional_number(name, fallback)
    local value = os.getenv(name)
    if not value or value == "" then
        return fallback
    end
    return assert(tonumber(value), "invalid numeric environment " .. name)
end

local output_dir = required_env("DUMP_BG2_OUTPUT_DIR")
local hold_frames = optional_number("DUMP_BG2_HOLD_FRAMES", 4)
local zero_frames = optional_number("DUMP_BG2_ZERO_FRAMES", 0)
local key = os.getenv("DUMP_BG2_KEY")
local sequence = os.getenv("DUMP_BG2_KEY_SEQUENCE")

local key_codes = {
    A = C.GBA_KEY.A,
    B = C.GBA_KEY.B,
    Up = C.GBA_KEY.UP,
    Down = C.GBA_KEY.DOWN,
    Left = C.GBA_KEY.LEFT,
    Right = C.GBA_KEY.RIGHT,
    L = C.GBA_KEY.L,
    R = C.GBA_KEY.R,
    Start = C.GBA_KEY.START,
    Select = C.GBA_KEY.SELECT,
}

local vram = emu.memory["vram"]
assert(vram, "memory domain not exposed: vram")
local io_domain = emu.memory["io"]
assert(io_domain, "memory domain not exposed: io")

-- The second background layer's screen base lives in BGCNT2 (0x08 in the I/O
-- block); its size lives in bits 14-15.  Read it instead of hard coding, so
-- the dump follows the game rather than our assumption.
-- mGBA's Lua memory API returns a *string* of bytes, not a table.
local function read_u16(domain, offset)
    local bytes = domain:readRange(offset, 2)
    return string.byte(bytes, 1) + string.byte(bytes, 2) * 256
end

local function bg2_cell_count(bgcnt2)
    local size = (bgcnt2 >> 14) & 3
    if size == 0 then return 32 * 32 end
    if size == 1 then return 64 * 32 end
    if size == 2 then return 32 * 64 end
    return 64 * 64
end

local function bg2_screen_base(bgcnt2)
    return ((bgcnt2 >> 8) & 31) * 0x400
end

local frame = 0
local written = 0

local function dump_frame()
    local bgcnt2 = read_u16(io_domain, 0x08)
    local dispcnt = read_u16(io_domain, 0x00)
    local cells = bg2_cell_count(bgcnt2)
    local base = bg2_screen_base(bgcnt2)
    local map = vram:readRange(base, cells * 2)
    local path = string.format("%s/frame-%03d.bin", output_dir, frame)
    local blob = assert(io.open(path, "wb"))
    blob:write(map)
    blob:close()
    local meta = string.format(
        "%s/frame-%03d.json",
        output_dir, frame)
    local text = assert(io.open(meta, "w"))
    text:write(string.format(
        "{\"frame\":%d,\"dispcnt\":%d,\"bgcnt2\":%d,\"screen_base\":%d," ..
        "\"cells\":%d,\"bg2_hoffs\":%d,\"bg2_voffs\":%d}\n",
        frame, dispcnt, bgcnt2, base, cells,
        read_u16(io_domain, 0x26), read_u16(io_domain, 0x28)))
    text:close()
    frame = frame + 1
    written = written + 1
end

callbacks:add("frame", function()
    dump_frame()
end)

-- Drive the same key sequence the recording scripts use, if one was given.
if sequence and sequence ~= "" then
    local tokens = {}
    for token in sequence:gmatch("[^,]+") do
        local normalized = token:gsub("^%s+", ""):gsub("%s+$", "")
        if normalized ~= "" then
            tokens[#tokens + 1] = normalized
        end
    end
    local index = 0
    callbacks:add("frame", function()
        index = index + 1
        if index <= zero_frames then
            return
        end
        local step = index - zero_frames
        local which = math.floor((step - 1) / hold_frames) + 1
        local phase = (step - 1) % hold_frames
        local name = tokens[which]
        if not name then
            return
        end
        if phase == 0 then
            emu:addKey(key_codes[name])
        elseif phase == hold_frames - 1 then
            emu:clearKey(key_codes[name])
        end
    end)
elseif key and key ~= "" then
    local code = assert(key_codes[key], "unsupported key " .. key)
    local counter = 0
    callbacks:add("frame", function()
        counter = counter + 1
        if counter > zero_frames and counter <= zero_frames + hold_frames then
            emu:addKey(code)
        elseif counter == zero_frames + hold_frames + 1 then
            emu:clearKey(code)
        end
    end)
end
