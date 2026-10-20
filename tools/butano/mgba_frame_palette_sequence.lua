-- Capture a short sequence of frames, each with its own palette RAM dump.
--
-- The original's move-range screen is the reason this probe exists: a
-- rendered PNG says what a frame looks like, a palette dump says which
-- entries exist, and neither says which entries produced the pixels -- the
-- two archives we had were captured at different moments, which is how a
-- whole overlay mechanism stayed unexplained for several rounds.
--
-- This probe therefore captures N consecutive frames and, for each of them,
-- both the palette RAM and a screenshot.  A consumer can then pair the
-- palette dump with the screenshot that is actually consistent with it
-- (every colour in the PNG must be a palette entry), instead of assuming an
-- offset between the two.
--
-- The probe is fail-closed: it writes every dump plus a manifest, and the
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

local input_state = required_env("MGBA_FRAME_INPUT_STATE")
local output_dir = required_env("MGBA_FRAME_OUTPUT_DIR")
local done_marker = required_env("MGBA_FRAME_DONE_MARKER")
local settle_frames = tonumber(required_env("MGBA_FRAME_SETTLE_FRAMES"))
local frame_count = tonumber(required_env("MGBA_FRAME_COUNT"))

assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local captured = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < settle_frames then
		return
	end
	if captured >= frame_count then
		return
	end

	local ok, failure = pcall(function()
		local palette = emu.memory["palette"]
		assert(palette, "memory domain not exposed: palette")
		local pram = palette:readRange(0, 1024)
		assert(#pram == 1024,
			string.format("palette returned %d bytes, expected 1024", #pram))
		write_bytes(
			output_dir .. string.format("/pram-%02d.bin", captured),
			pram)

		local io_domain = emu.memory["io"]
		assert(io_domain, "memory domain not exposed: io")
		write_bytes(
			output_dir .. string.format("/io-%02d.bin", captured),
			io_domain:readRange(0, 0x60))

		local oam = emu.memory["oam"]
		assert(oam, "memory domain not exposed: oam")
		local sprites = oam:readRange(0, 1024)
		assert(#sprites == 1024,
			string.format("oam returned %d bytes, expected 1024", #sprites))
		write_bytes(
			output_dir .. string.format("/oam-%02d.bin", captured),
			sprites)

		local vram = emu.memory["vram"]
		assert(vram, "memory domain not exposed: vram")
		local graphics = vram:readRange(0, 96 * 1024)
		assert(#graphics == 96 * 1024,
			string.format("vram returned %d bytes, expected %d",
				#graphics, 96 * 1024))
		write_bytes(
			output_dir .. string.format("/vram-%02d.bin", captured),
			graphics)

		emu:screenshot(
			output_dir .. string.format("/frame-%02d.png", captured))
	end)
	if not ok then
		local log = assert(io.open(output_dir .. "/log.txt", "a"))
		log:write("frame " .. frame .. " failed: " .. tostring(failure) .. "\n")
		log:close()
		write_text(done_marker, "failed\n")
		complete = true
		return
	end
	captured = captured + 1
	if captured >= frame_count then
		write_text(output_dir .. "/manifest.json", string.format(
			'{\n  "schema": "konoha.mgba-frame-palette-sequence.v1",\n' ..
			'  "input_state": "%s",\n' ..
			'  "settle_frames": %d,\n' ..
			'  "captured_frames": %d,\n' ..
			'  "pram_bytes": 1024,\n' ..
			'  "vram_bytes": 98304,\n' ..
			'  "io_bytes": 96\n}\n',
			input_state, settle_frames, captured))
		write_text(done_marker, "ok\n")
		complete = true
	end
end)
