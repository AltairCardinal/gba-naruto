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

local output_dir = required_env(
	"MGBA_BATTLE_PREPARATION_OUTPUT_DIR"
)
local done_marker_path = required_env(
	"MGBA_BATTLE_PREPARATION_DONE_MARKER"
)
local campaign_telemetry_address = assert(parse_number(
	required_env(
		"MGBA_BATTLE_PREPARATION_CAMPAIGN_TELEMETRY_ADDRESS"
	)
))
local battle_telemetry_address = assert(parse_number(
	required_env(
		"MGBA_BATTLE_PREPARATION_BATTLE_TELEMETRY_ADDRESS"
	)
))

local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local keys = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Down = C.GBA_KEY.DOWN,
	Up = C.GBA_KEY.UP,
}

local function read_campaign()
	if emu:read32(campaign_telemetry_address) ~=
			CAMPAIGN_TELEMETRY_MAGIC then
		return nil
	end
	return {
		save_generation =
			emu:read32(campaign_telemetry_address + 16),
		save_slot =
			emu:read32(campaign_telemetry_address + 20),
		save_verified =
			emu:read32(campaign_telemetry_address + 24),
		naruto_tool_0 =
			emu:read32(campaign_telemetry_address + 44),
		owned_tool_67 =
			emu:read32(campaign_telemetry_address + 56),
		owned_tool_68 =
			emu:read32(campaign_telemetry_address + 60),
		material_6 =
			emu:read32(campaign_telemetry_address + 64),
		last_error =
			emu:read32(campaign_telemetry_address + 68),
	}
end

local function read_battle()
	if emu:read32(battle_telemetry_address) ~=
			BATTLE_TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id =
			emu:read32(battle_telemetry_address + 4),
		phase =
			emu:read32(battle_telemetry_address + 8),
	}
end

local frame = 0
local step = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 30
local battle_ready_frame = nil

local function press(key)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = key
	emu:addKey(assert(keys[key]))
	release_frame = frame + 5
	return true
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if active_key and frame >= release_frame then
		emu:clearKey(assert(keys[active_key]))
		active_key = nil
		next_press_frame = frame + 12
	end

	local campaign = read_campaign()
	if not campaign then
		return
	end
	local battle = read_battle()

	if step == 0 and press("Up") then
		step = 1
	elseif step == 1 and press("A") then
		step = 2
	elseif step == 2 and not active_key and
			frame >= next_press_frame then
		emu:screenshot(
			output_dir .. "/upgrade-first-recipe.png"
		)
		if press("Down") then
			step = 3
		end
	elseif step == 3 and press("Down") then
		step = 4
	elseif step == 4 and not active_key and
			frame >= next_press_frame then
		emu:screenshot(
			output_dir .. "/upgrade-recipe.png"
		)
		if press("A") then
			step = 5
		end
	elseif step == 5 and not active_key and
			frame >= next_press_frame then
		emu:screenshot(
			output_dir .. "/upgrade-complete.png"
		)
		if press("A") then
			step = 6
		end
	elseif step == 6 and press("B") then
		step = 7
	elseif step == 7 and press("Down") then
		step = 8
	elseif step == 8 and press("A") then
		step = 9
	elseif step == 9 and campaign.save_generation >= 1 and
			campaign.save_verified == 1 and
			battle and battle.battle_id == 41 and
			battle.phase == PHASE_DEPLOY_UNIT then
		battle_ready_frame = frame + 15
		step = 10
	elseif step == 10 and battle_ready_frame and
			frame >= battle_ready_frame and battle and
			battle.battle_id == 41 and
			battle.phase == PHASE_DEPLOY_UNIT then
		assert(campaign.save_slot >= 1)
		assert(campaign.naruto_tool_0 == 68)
		assert(campaign.owned_tool_67 == 0)
		assert(campaign.owned_tool_68 == 1)
		assert(campaign.material_6 == 0)
		assert(campaign.last_error == 0)
		emu:screenshot(
			output_dir .. "/battle-start-after-upgrade.png"
		)
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"battle_id":%d,"battle_phase":%d,"save_generation":%d,"save_slot":%d,"save_verified":%d,"naruto_tool_0":%d,"owned_tool_67":%d,"owned_tool_68":%d,"material_6":%d,"last_error":%d,"status":"preparation-upgrade-complete"}',
				frame,
				battle.battle_id,
				battle.phase,
				campaign.save_generation,
				campaign.save_slot,
				campaign.save_verified,
				campaign.naruto_tool_0,
				campaign.owned_tool_67,
				campaign.owned_tool_68,
				campaign.material_6,
				campaign.last_error
			)
		)
		write_file(
			done_marker_path,
			string.format(
				'{"capture_frame":%d,"status":"preparation-upgrade-complete"}',
				frame
			)
		)
		complete = true
	end
end)
