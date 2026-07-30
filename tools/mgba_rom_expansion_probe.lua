local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local function quoted(value)
	value = value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n")
	return '"' .. value .. '"'
end

local output_dir = required_env("MGBA_EXPANSION_OUTPUT_DIR")
local run_id = required_env("MGBA_EXPANSION_RUN_ID")
local expected_rom_sha256 = required_env("MGBA_EXPANSION_ROM_SHA256")
local done_marker = required_env("MGBA_EXPANSION_DONE_MARKER")
local marker_address = 0x08600100
local scratch_address = 0x0203FFF0
local expected_marker = 0x4258474D
local frame = 0
local completed = false
local first_scratch = nil

callbacks:add("frame", function()
	if completed then
		return
	end
	frame = frame + 1
	local rom_marker = emu:read32(marker_address) % 0x100000000
	local scratch_marker = emu:read32(scratch_address) % 0x100000000
	if frame == 1 then
		first_scratch = scratch_marker
	end
	assert(rom_marker == expected_marker, "expanded ROM marker mismatch")
	assert(scratch_marker == expected_marker, "startup CPU probe did not write marker")

	if frame == 60 then
		local state_path = output_dir .. "/boot-frame-60.ss9"
		local png_path = output_dir .. "/boot-frame-60.png"
		local evidence_path = output_dir .. "/runtime-evidence.json"
		assert(emu:saveStateFile(state_path), "failed to save expansion probe state")
		emu:screenshot(png_path)
		local payload = table.concat({
			'{"schema":"rom-expansion-runtime-evidence-v1"',
			',"run_id":', quoted(run_id),
			',"success":true',
			',"capture_frame":60',
			',"rom_sha256":', quoted(expected_rom_sha256),
			',"marker_address":"0x08600100"',
			',"scratch_address":"0x0203FFF0"',
			',"expected_marker":"0x4258474D"',
			',"rom_marker":"0x', string.format("%08X", rom_marker), '"',
			',"first_frame_scratch":"0x', string.format("%08X", first_scratch), '"',
			',"final_scratch":"0x', string.format("%08X", scratch_marker), '"',
			',"pc":"0x', string.format("%08X", emu:readRegister("pc")), '"',
			',"state":', quoted(state_path),
			',"screenshot":', quoted(png_path),
			'}'
		})
		write_file(evidence_path, payload)
		write_file(done_marker, payload)
		completed = true
	end
end)
