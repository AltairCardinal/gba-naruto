-- Dump the GBA's I/O register block from one savestate.
--
-- The archived `io.bin` dumps in this repository decode to an impossible
-- DISPCNT (bit 15 clear means "LCD off" while the captured frame is clearly
-- rendered), so the register block's offset inside the dumped region is not
-- calibrated yet.  This probe reads the region as the emulator exposes it and
-- writes the raw bytes plus a decoded view, so the layout can be pinned
-- against the frame that is actually on screen.
--
-- The probe is fail-closed: it writes the bytes and a manifest, and the
-- driver refuses a run whose outputs are missing or the wrong size.

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

local input_state = required_env("MGBA_REGS_INPUT_STATE")
local output_dir = required_env("MGBA_REGS_OUTPUT_DIR")
local done_marker = required_env("MGBA_REGS_DONE_MARKER")
local settle_frames = tonumber(required_env("MGBA_REGS_SETTLE_FRAMES"))
local byte_count = tonumber(required_env("MGBA_REGS_BYTES"))

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

	local domain = emu.memory["io"]
	assert(domain, "memory domain not exposed: io")
	local bytes = domain:readRange(0, byte_count)
	assert(#bytes == byte_count,
		string.format("io returned %d bytes, expected %d", #bytes, byte_count))

	write_bytes(output_dir .. "/io.bin", bytes)
	write_text(output_dir .. "/manifest.json", string.format(
		'{\n  "schema": "konoha.mgba-register-dump.v1",\n' ..
		'  "input_state": "%s",\n' ..
		'  "settle_frames": %d,\n' ..
		'  "captured_frame": %d,\n' ..
		'  "bytes": %d\n}\n',
		input_state, settle_frames, frame, byte_count))

	write_text(done_marker, "ok\n")
	complete = true
end)
