local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or
		tonumber(value:gsub("^0[xX]", ""), 16)
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir =
	required_env("MGBA_CAMPAIGN_LOAD_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_CAMPAIGN_LOAD_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_CAMPAIGN_LOAD_TELEMETRY_ADDRESS")
))
local function expected_or_default(name, default_value)
	local value = os.getenv(name)
	if not value or value == "" then
		return default_value
	end
	return assert(parse_number(value))
end

local expected_level = expected_or_default(
	"MGBA_CAMPAIGN_EXPECTED_LEVEL", 2
)
local expected_experience = expected_or_default(
	"MGBA_CAMPAIGN_EXPECTED_EXPERIENCE", 25
)
local expected_action_8_level = expected_or_default(
	"MGBA_CAMPAIGN_EXPECTED_ACTION_8_LEVEL", 1
)
local expected_tool_0 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_TOOL_0"
)
local expected_tool_2 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_TOOL_2"
)
local expected_owned_tool_67 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_67"
)
local expected_owned_tool_68 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_68"
)
local expected_owned_tool_1 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_1"
)
local expected_material_6 = os.getenv(
	"MGBA_CAMPAIGN_EXPECTED_MATERIAL_6"
)
if expected_tool_0 then
	expected_tool_0 = assert(parse_number(expected_tool_0))
end
if expected_tool_2 then
	expected_tool_2 = assert(parse_number(expected_tool_2))
end
if expected_owned_tool_67 then
	expected_owned_tool_67 =
		assert(parse_number(expected_owned_tool_67))
end
if expected_owned_tool_68 then
	expected_owned_tool_68 =
		assert(parse_number(expected_owned_tool_68))
end
if expected_owned_tool_1 then
	expected_owned_tool_1 =
		assert(parse_number(expected_owned_tool_1))
end
if expected_material_6 then
	expected_material_6 =
		assert(parse_number(expected_material_6))
end

local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local frame = 0
local complete = false

local function read_campaign()
	if emu:read32(telemetry_address) ~=
			CAMPAIGN_TELEMETRY_MAGIC then
		return nil
	end
	return {
		load_generation =
			emu:read32(telemetry_address + 4),
		load_slot =
			emu:read32(telemetry_address + 8),
		load_used_default =
			emu:read32(telemetry_address + 12),
		save_generation =
			emu:read32(telemetry_address + 16),
		save_verified =
			emu:read32(telemetry_address + 24),
		naruto_level =
			emu:read32(telemetry_address + 28),
		naruto_experience =
			emu:read32(telemetry_address + 32),
		naruto_training_points =
			emu:read32(telemetry_address + 36),
		naruto_action_8_level =
			emu:read32(telemetry_address + 40),
		naruto_tool_0 =
			emu:read32(telemetry_address + 44),
		naruto_tool_1 =
			emu:read32(telemetry_address + 48),
		naruto_tool_2 =
			emu:read32(telemetry_address + 52),
		owned_tool_67 =
			emu:read32(telemetry_address + 56),
		owned_tool_68 =
			emu:read32(telemetry_address + 60),
		material_6 =
			emu:read32(telemetry_address + 64),
		last_error =
			emu:read32(telemetry_address + 68),
		owned_tool_1 =
			emu:read32(telemetry_address + 72),
	}
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	local campaign = read_campaign()
	if not campaign then
		return
	end

	assert(campaign.load_generation >= 1)
	assert(campaign.load_slot >= 1)
	assert(campaign.load_used_default == 0)
	assert(campaign.save_generation == 0)
	assert(campaign.save_verified == 0)
	assert(campaign.naruto_level == expected_level)
	assert(campaign.naruto_experience ==
		expected_experience)
	assert(campaign.naruto_training_points == 0)
	assert(campaign.naruto_action_8_level ==
		expected_action_8_level)
	if expected_tool_0 then
		assert(campaign.naruto_tool_0 ==
			expected_tool_0)
	end
	if expected_tool_2 then
		assert(campaign.naruto_tool_2 ==
			expected_tool_2)
	end
	if expected_owned_tool_67 then
		assert(campaign.owned_tool_67 ==
			expected_owned_tool_67)
	end
	if expected_owned_tool_68 then
		assert(campaign.owned_tool_68 ==
			expected_owned_tool_68)
	end
	if expected_owned_tool_1 then
		assert(campaign.owned_tool_1 ==
			expected_owned_tool_1)
	end
	if expected_material_6 then
		assert(campaign.material_6 ==
			expected_material_6)
	end
	assert(campaign.last_error == 0)

	emu:screenshot(output_dir .. "/campaign-loaded.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"load_generation":%d,"load_slot":%d,"load_used_default":%d,"save_generation":%d,"save_verified":%d,"naruto_level":%d,"naruto_experience":%d,"naruto_training_points":%d,"naruto_action_8_level":%d,"naruto_tool_0":%d,"naruto_tool_1":%d,"naruto_tool_2":%d,"owned_tool_67":%d,"owned_tool_68":%d,"owned_tool_1":%d,"material_6":%d,"last_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"campaign-load-complete"}',
			frame,
			campaign.load_generation,
			campaign.load_slot,
			campaign.load_used_default,
			campaign.save_generation,
			campaign.save_verified,
			campaign.naruto_level,
			campaign.naruto_experience,
			campaign.naruto_training_points,
			campaign.naruto_action_8_level,
			campaign.naruto_tool_0,
			campaign.naruto_tool_1,
			campaign.naruto_tool_2,
			campaign.owned_tool_67,
			campaign.owned_tool_68,
			campaign.owned_tool_1,
			campaign.material_6,
			campaign.last_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
	)
	write_file(
		done_marker_path,
		string.format(
			'{"capture_frame":%d,"status":"campaign-load-complete"}',
			frame
		)
	)
	complete = true
end)
