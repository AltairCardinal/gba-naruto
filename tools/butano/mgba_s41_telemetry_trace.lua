local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or tonumber(value:gsub("^0[xX]", ""), 16)
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir = required_env("MGBA_S41_TRACE_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_S41_TRACE_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_S41_TRACE_TELEMETRY_ADDRESS")
))
local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local frame = 0
local active_key = false
local release_frame = 0
local records = {}

local function record()
	local magic = emu:read32(telemetry_address)
	local battle_id = emu:read32(telemetry_address + 4)
	local phase = emu:read32(telemetry_address + 8)
	local round = emu:read32(telemetry_address + 12)
	local selected_unit = emu:read32(telemetry_address + 20)
	local active_units = emu:read32(telemetry_address + 24)
	records[#records + 1] = string.format(
		'{"frame":%d,"magic":"0x%08X","battle_id":%u,"phase":%u,"round":%u,"selected_unit":%u,"active_units":%u}',
		frame,
		magic,
		battle_id,
		phase,
		round,
		selected_unit,
		active_units
	)
	return magic, phase
end

callbacks:add("frame", function()
	frame = frame + 1
	if active_key and frame >= release_frame then
		emu:clearKey(C.GBA_KEY.A)
		active_key = false
	end

	if frame % 30 == 0 then
		local magic, phase = record()
		if not active_key and magic == TELEMETRY_MAGIC and
			(phase == PHASE_DEPLOY_UNIT or phase == PHASE_DEPLOY_START) then
			emu:addKey(C.GBA_KEY.A)
			active_key = true
			release_frame = frame + 6
		end
	end

	if frame == 900 then
		emu:screenshot(output_dir .. "/frame-900.png")
		local payload = string.format(
			'{"status":"trace-complete","telemetry_address":"0x%08X","records":[%s]}',
			telemetry_address,
			table.concat(records, ",")
		)
		write_file(output_dir .. "/trace.json", payload)
		write_file(done_marker_path, payload)
	end
end)
