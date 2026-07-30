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

local input_state = required_env("MGBA_EXPANSION_RESTORE_STATE")
local output_dir = required_env("MGBA_EXPANSION_RESTORE_OUTPUT_DIR")
local run_id = required_env("MGBA_EXPANSION_RESTORE_RUN_ID")
local rom_sha256 = required_env("MGBA_EXPANSION_RESTORE_ROM_SHA256")
local done_marker = required_env("MGBA_EXPANSION_RESTORE_DONE_MARKER")
local expected_marker = 0x4258474D
local completed = false

assert(emu:loadStateFile(input_state), "failed to restore expansion probe state")
local restored_frame = emu:currentFrame()

callbacks:add("frame", function()
	if completed then
		return
	end
	local delta = emu:currentFrame() - restored_frame
	local rom_marker = emu:read32(0x08600100) % 0x100000000
	local scratch_marker = emu:read32(0x0203FFF0) % 0x100000000
	assert(rom_marker == expected_marker, "restored expanded ROM marker mismatch")
	assert(
		scratch_marker == expected_marker,
		"restored expansion scratch marker mismatch"
	)
	if delta >= 30 then
		local screenshot = output_dir .. "/restore-frame-30.png"
		emu:screenshot(screenshot)
		local payload = table.concat({
			'{"schema":"rom-expansion-snapshot-restore-v1"',
			',"run_id":', quoted(run_id),
			',"success":true',
			',"rom_sha256":', quoted(rom_sha256),
			',"input_state":', quoted(input_state),
			',"restored_frame":', tostring(restored_frame),
			',"capture_delta":', tostring(delta),
			',"rom_marker":"0x', string.format("%08X", rom_marker), '"',
			',"scratch_marker":"0x', string.format("%08X", scratch_marker), '"',
			',"pc":"0x', string.format("%08X", emu:readRegister("pc")), '"',
			',"screenshot":', quoted(screenshot),
			'}'
		})
		write_file(output_dir .. "/restore-evidence.json", payload)
		write_file(done_marker, payload)
		completed = true
	end
end)
