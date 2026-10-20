-- Capture the original's rendered frame and its palette RAM in the same frame.
--
-- The question this probe answers is "which palette entries produced the
-- pixels of this frame".  Two earlier attempts could not answer it:
--
-- * a rendered PNG alone says what the frame looks like, not which palette
--   bank produced a colour;
-- * a palette dump alone says which entries exist, but nothing about which
--   of them the frame actually used -- and the archives in this repository
--   turned out to be captured at a different moment than the PNG they were
--   compared against, which is how a whole mechanism (the move-range
--   overlay) stayed unexplained for several rounds.
--
-- So the probe does both in one frame callback: it reads palette RAM, reads
-- the I/O registers, and asks mGBA for a screenshot.  The screenshot and the
-- palette therefore describe the same frame, and a consumer can check that
-- every colour in the PNG really is a palette entry.
--
-- The probe is fail-closed: it writes the raw dumps, the screenshot and a
-- manifest, and the driver refuses a run whose outputs are missing or the
-- wrong size.

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

local input_state = required_env("MGBA_FRAME_INPUT_STATE")
local output_dir = required_env("MGBA_FRAME_OUTPUT_DIR")
local done_marker = required_env("MGBA_FRAME_DONE_MARKER")
local settle_frames = tonumber(required_env("MGBA_FRAME_SETTLE_FRAMES"))

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
	local ok, failure = pcall(function()

	local pram = emu.memory["palette"]
	assert(pram, "memory domain not exposed: palette")
	local palette = pram:readRange(0, 1024)
	assert(#palette == 1024,
		string.format("pram returned %d bytes, expected 1024", #palette))
	write_bytes(output_dir .. "/pram.bin", palette)

	local io_domain = emu.memory["io"]
	assert(io_domain, "memory domain not exposed: io")
	local registers = io_domain:readRange(0, 0x60)
	write_bytes(output_dir .. "/io.bin", registers)

	emu:screenshot(output_dir .. "/frame.png")

	write_text(output_dir .. "/manifest.json", string.format(
		'{\n  "schema": "konoha.mgba-frame-palette-dump.v1",\n' ..
		'  "input_state": "%s",\n' ..
		'  "settle_frames": %d,\n' ..
		'  "captured_frame": %d,\n' ..
		'  "pram_bytes": 1024,\n' ..
		'  "io_bytes": 96,\n' ..
		'  "screenshot": "frame.png"\n}\n',
		input_state, settle_frames, frame))

	end)
	if not ok then
		local log = assert(io.open(output_dir .. "/log.txt", "a"))
		log:write("frame " .. frame .. " failed: " .. tostring(failure) .. "\n")
		log:close()
		write_text(done_marker, "failed\n")
		complete = true
		return
	end
	write_text(done_marker, "ok\n")
	complete = true
end)
