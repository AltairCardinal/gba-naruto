-- Dump the original game's battle unit pool from one savestate.
--
-- The remake's S49 roster (who fights, where, at what level and with how much
-- HP) is supposed to be a copy of the original's.  Until now the only original
-- side evidence was a rendered PNG or a prose note, neither of which can be
-- compared field by field against the remake's data tables.  The original keeps
-- its live units in one contiguous pool:
--
--   base   0x020240C0
--   stride 0x1D4 per record, 13 records (slot 0..12)
--   +0x00  character id (0 = empty slot)
--   +0x0C  current HP
--   +0x0E  max HP
--   +0xC4  grid X
--   +0xC5  grid Y
--
-- mGBA exposes the GBA's EWRAM to Lua as emu.memory["wram"] (this build has
-- no "ewram" domain; IWRAM is the separate "iwram" domain) and readRange
-- (offset, length) is relative to the region base, so the pool starts at
-- offset 0x240C0.
--
-- The probe is fail-closed: it writes the raw pool bytes and a manifest, and
-- the driver refuses a run whose outputs are missing or the wrong size.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_bytes(path, payload)
	local output = assert(io.open(path, "wb"))
	output:write(payload)
	output:close()
end

local function write_text(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local input_state = required_env("MGBA_ROSTER_INPUT_STATE")
local output_dir = required_env("MGBA_ROSTER_OUTPUT_DIR")
local done_marker = required_env("MGBA_ROSTER_DONE_MARKER")
local settle_frames = tonumber(required_env("MGBA_ROSTER_SETTLE_FRAMES"))

local POOL_BASE = 0x020240C0
local EWRAM_BASE = 0x02000000
local POOL_SIZE = 0x1D4 * 13

assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < settle_frames then
		return
	end

	local domain = emu.memory["wram"]
	assert(domain, "memory domain not exposed: wram")
	local bytes = domain:readRange(POOL_BASE - EWRAM_BASE, POOL_SIZE)
	assert(#bytes == POOL_SIZE,
		string.format("wram returned %d bytes, expected %d", #bytes, POOL_SIZE))

	write_bytes(output_dir .. "/unit_pool.bin", bytes)
	write_text(output_dir .. "/manifest.json", string.format(
		'{\n  "schema": "konoha.mgba-battle-roster-dump.v1",\n' ..
		'  "input_state": "%s",\n' ..
		'  "settle_frames": %d,\n' ..
		'  "captured_frame": %d,\n' ..
		'  "pool_base": "0x%08X",\n' ..
		'  "pool_size": %d\n}\n',
		input_state, settle_frames, frame, POOL_BASE, POOL_SIZE))

	write_text(done_marker, "ok\n")
	complete = true
end)
