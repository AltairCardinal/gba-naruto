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

local output_dir =
	required_env("MGBA_BATTLE_CAMPAIGN_DIAGNOSTIC_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_BATTLE_CAMPAIGN_DIAGNOSTIC_DONE_MARKER")
local battle_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_CAMPAIGN_DIAGNOSTIC_BATTLE_TELEMETRY_ADDRESS"
)))
local campaign_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_CAMPAIGN_DIAGNOSTIC_CAMPAIGN_TELEMETRY_ADDRESS"
)))

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < 120 then
		return
	end
	emu:screenshot(output_dir .. "/startup-frame-120.png")
	local payload = string.format(
		'{"capture_frame":%d,"battle_magic":"0x%08X","campaign_magic":"0x%08X","campaign_scenario_id":%d,"campaign_last_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","iwram_mix_guard":"0x%08X","status":"startup-diagnostic"}',
		frame,
		emu:read32(battle_telemetry_address),
		emu:read32(campaign_telemetry_address),
		emu:read32(campaign_telemetry_address + 76),
		emu:read32(campaign_telemetry_address + 68),
		emu:readRegister("pc"),
		emu:readRegister("lr"),
		emu:readRegister("sp"),
		emu:read32(0x03002970)
	)
	write_file(output_dir .. "/diagnostic.json", payload)
	write_file(done_marker_path, payload)
	complete = true
end)
