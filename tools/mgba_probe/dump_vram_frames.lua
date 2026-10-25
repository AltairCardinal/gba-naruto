-- Dump the raw display registers and VRAM once per frame.
--
-- Why raw blocks instead of parsing in Lua: mGBA's Lua memory API returns
-- bytes, and the register offsets differ from the GBA's flat I/O map, so
-- decoding them in Lua is guesswork.  The Butano line already solved this by
-- dumping the raw I/O block and the raw VRAM and decoding on the Python side
-- (tools/butano/mgba_frame_palette_sequence.lua).  This script does the same,
-- one frame at a time, so the consumer can pick any region it wants after the
-- fact.
--
-- Environment:
--   DUMP_VRAM_OUTPUT_DIR   where to write the per-frame dumps (must exist)
--   DUMP_VRAM_KEY_SEQUENCE optional comma separated key sequence
--   DUMP_VRAM_HOLD_FRAMES  frames to hold each key (default 4)
--   DUMP_VRAM_ZERO_FRAMES  frames to wait before the first key (default 0)
--   DUMP_VRAM_MAX_FRAMES   stop after this many frames (default 0 = no limit)

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

local output_dir = required_env("DUMP_VRAM_OUTPUT_DIR")
local hold_frames = optional_number("DUMP_VRAM_HOLD_FRAMES", 4)
local zero_frames = optional_number("DUMP_VRAM_ZERO_FRAMES", 0)
local max_frames = optional_number("DUMP_VRAM_MAX_FRAMES", 0)
local sequence = os.getenv("DUMP_VRAM_KEY_SEQUENCE")

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

local frame = 0

local function dump_frame()
    local io_bytes = io_domain:readRange(0, 0x60)
    local io_file = assert(io.open(
        string.format("%s/frame-%04d.io", output_dir, frame), "wb"))
    io_file:write(io_bytes)
    io_file:close()

    local graphics = vram:readRange(0, 96 * 1024)
    local vram_file = assert(io.open(
        string.format("%s/frame-%04d.vram", output_dir, frame), "wb"))
    vram_file:write(graphics)
    vram_file:close()

    frame = frame + 1
end

callbacks:add("frame", function()
    if max_frames > 0 and frame >= max_frames then
        return
    end
    dump_frame()
end)

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
end
