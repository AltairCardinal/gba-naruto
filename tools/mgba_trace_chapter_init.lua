-- mgba_trace_chapter_init.lua
--
-- Trace the chapter/battle initialization sequence.
-- Goal: find which ROM code reads the chapter config and sets up the battle.
--
-- Strategy:
--   1. Press A every ~210 frames to advance through all opening dialogue.
--   2. Set watchpoints on known battle WRAM areas (written during battle init).
--   3. Capture PC, LR, r0-r3 on every hit.
--   4. Long timeout (15000 frames) to handle the full opening sequence.
--
-- Known battle WRAM (from notes/battle-config-format.md):
--   0x0201BE2A - unit/team count (written early during chapter init)
--   0x020240C0 - main battle data block (0x17C4 bytes)
--   0x02024294 - unit array base
--
-- Run with:
--   MGBA_BIN=... tools/run_headless_mgba.sh \
--     tools/mgba_trace_chapter_init.lua \
--     build/naruto-sequel-dev.gba

local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0
local hit_count = 0
local watch_ids = {}

local KEY_A     = 1 << 0
local KEY_START = 1 << 3

-- Watchpoint ranges to monitor.
-- "unit_count_area" covers the unit count and nearby header fields.
-- "battle_data_head" covers the first 0x100 bytes of the main battle block.
local WATCH_RANGES = {
    { name = "unit_count_area",  start_addr = 0x0201BE00, end_addr = 0x0201C000 },
    { name = "battle_data_head", start_addr = 0x020240C0, end_addr = 0x020241C0 },
}

local WATCH_START_FRAME = 1200  -- after title screen settles
local MAX_HITS          = 64
local TIMEOUT_FRAME     = 15000
local SCREENSHOT_EVERY  = 600   -- capture visual progress

local log_path     = OUT_DIR .. "/chapter-init-trace.log"
local summary_path = OUT_DIR .. "/chapter-init-trace-summary.txt"
local done_path    = OUT_DIR .. "/chapter-init-trace.done"

local pc_counts   = {}
local addr_counts = {}
local first_hit_taken = false

local function append(path, line, mode)
    local f = io.open(path, mode or "a")
    if f then
        f:write(line .. "\n")
        f:close()
    end
end

local function log(line)
    append(log_path, line, frame == 0 and "w" or "a")
end

local function hex8(v)
    return string.format("%08X", v or 0)
end

local function read_reg(name)
    local ok, value = pcall(function()
        return emu:readRegister(name)
    end)
    return (ok and value) or 0
end

local function write_summary(status)
    local pcs = {}
    for pc, count in pairs(pc_counts) do
        table.insert(pcs, { pc = pc, count = count })
    end
    table.sort(pcs, function(a, b)
        return a.count ~= b.count and a.count > b.count or a.pc < b.pc
    end)

    local addrs = {}
    for addr, count in pairs(addr_counts) do
        table.insert(addrs, { addr = addr, count = count })
    end
    table.sort(addrs, function(a, b)
        return a.count ~= b.count and a.count > b.count or a.addr < b.addr
    end)

    local f = io.open(summary_path, "w")
    if not f then return end
    f:write("status=" .. status .. "\n")
    f:write("hits=" .. hit_count .. "\n")
    f:write("timeout_frame=" .. TIMEOUT_FRAME .. "\n")
    f:write("pcs:\n")
    for _, item in ipairs(pcs) do
        f:write(string.format("  %08X  hits=%d\n", item.pc, item.count))
    end
    f:write("addrs:\n")
    for _, item in ipairs(addrs) do
        f:write(string.format("  %08X  hits=%d\n", item.addr, item.count))
    end
    f:close()
end

local function finish(status)
    for _, id in ipairs(watch_ids) do
        pcall(function() emu:clearBreakpoint(id) end)
    end
    watch_ids = {}
    write_summary(status)
    append(done_path, status, "w")
    log("DONE status=" .. status .. " total_hits=" .. hit_count)
    os.exit(0)
end

local function on_watch(info)
    hit_count = hit_count + 1
    local pc   = read_reg("pc")
    local lr   = read_reg("lr")
    local r0   = read_reg("r0")
    local r1   = read_reg("r1")
    local r2   = read_reg("r2")
    local r3   = read_reg("r3")
    local addr = info.address or 0

    pc_counts[pc]     = (pc_counts[pc]   or 0) + 1
    addr_counts[addr] = (addr_counts[addr] or 0) + 1

    log(string.format(
        "hit=%d frame=%d pc=%s lr=%s r0=%s r1=%s r2=%s r3=%s addr=%s old=%d new=%d",
        hit_count, frame,
        hex8(pc), hex8(lr),
        hex8(r0), hex8(r1), hex8(r2), hex8(r3),
        hex8(addr),
        info.oldValue or -1, info.newValue or -1
    ))

    if not first_hit_taken then
        first_hit_taken = true
        pcall(function()
            emu:screenshot(OUT_DIR .. "/chapter-init-first-hit.png")
        end)
        log("first_hit_screenshot=" .. OUT_DIR .. "/chapter-init-first-hit.png")
    end

    if hit_count >= MAX_HITS then
        finish("max_hits")
    end
end

callbacks:add("start", function()
    frame = 0
    log(string.format("start timeout=%d watch_start=%d", TIMEOUT_FRAME, WATCH_START_FRAME))
    for _, r in ipairs(WATCH_RANGES) do
        log(string.format("watch_range name=%s %08X-%08X", r.name, r.start_addr, r.end_addr))
    end
end)

callbacks:add("frame", function()
    frame = frame + 1

    -- === Key press sequence ===
    -- Mirror the proven newgame_walk presses for the first ~2700 frames,
    -- then continue pressing A every 210 frames to clear remaining dialogue.
    local function pulse(keys, start_f, duration)
        return (frame >= start_f and frame < start_f + duration) and keys or 0
    end

    local keys = 0

    -- Phase 1: proven title→dialogue navigation (matches mgba_newgame_walk.lua)
    keys = keys | pulse(KEY_A,     330,  8)
    keys = keys | pulse(KEY_A,     540,  8)
    keys = keys | pulse(KEY_A,     750,  8)
    keys = keys | pulse(KEY_START, 960,  8)
    keys = keys | pulse(KEY_A,    1140,  8)
    keys = keys | pulse(KEY_A,    1590,  8)
    keys = keys | pulse(KEY_A,    1830,  8)
    keys = keys | pulse(KEY_A,    2070,  8)
    keys = keys | pulse(KEY_A,    2310,  8)
    keys = keys | pulse(KEY_A,    2550,  8)

    -- Phase 2: continue pressing A every 210 frames from 2760 onward
    if frame >= 2760 and (frame - 2760) % 210 < 8 then
        keys = keys | KEY_A
    end

    emu:setKeys(keys)

    if keys ~= 0 and hit_count == 0 then
        -- only log key presses before first watchpoint hit to keep log compact
        log(string.format("frame=%d keys=0x%X", frame, keys))
    end

    -- === Periodic screenshots ===
    if frame % SCREENSHOT_EVERY == 0 then
        pcall(function()
            emu:screenshot(string.format("%s/chapter-init-%05d.png", OUT_DIR, frame))
        end)
    end

    -- === Arm watchpoints once ===
    if frame == WATCH_START_FRAME and #watch_ids == 0 then
        for _, r in ipairs(WATCH_RANGES) do
            local id = emu:setRangeWatchpoint(
                on_watch,
                r.start_addr,
                r.end_addr,
                C.WATCHPOINT_TYPE.WRITE_CHANGE
            )
            table.insert(watch_ids, id)
            log(string.format("watch_set name=%s range=%08X-%08X id=%s",
                r.name, r.start_addr, r.end_addr, tostring(id)))
        end
    end

    -- === Timeout ===
    if frame == TIMEOUT_FRAME then
        finish(hit_count > 0 and "timeout_with_hits" or "timeout_no_hits")
    end
end)
