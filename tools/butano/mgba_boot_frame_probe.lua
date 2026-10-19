local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local output_dir = required_env("MGBA_BOOT_PROBE_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_BOOT_PROBE_DONE_MARKER")
local capture_frame = tonumber(
	os.getenv("MGBA_BOOT_PROBE_CAPTURE_FRAME") or "300"
)
local frame = 0
local complete = false

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < capture_frame then
		return
	end
	emu:screenshot(output_dir .. "/frame.png")
	local audit = string.format(
		'{"capture_frame":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"capture-complete"}',
		frame,
		emu:readRegister("pc"),
		emu:readRegister("lr"),
		emu:readRegister("sp")
	)
	write_file(output_dir .. "/audit.json", audit)
	write_file(done_marker_path, audit)
	complete = true
end)
