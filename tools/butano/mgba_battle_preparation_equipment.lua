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
	"MGBA_BATTLE_EQUIPMENT_OUTPUT_DIR"
)
local done_marker_path = required_env(
	"MGBA_BATTLE_EQUIPMENT_DONE_MARKER"
)
local campaign_telemetry_address = assert(parse_number(
	required_env(
		"MGBA_BATTLE_EQUIPMENT_CAMPAIGN_TELEMETRY_ADDRESS"
	)
))
local battle_telemetry_address = assert(parse_number(
	required_env(
		"MGBA_BATTLE_EQUIPMENT_BATTLE_TELEMETRY_ADDRESS"
	)
))

local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_ACTION_SELECTION = 6
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local ACTION_KIND_NINJA_TOOL = 1

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
		last_error =
			emu:read32(campaign_telemetry_address + 68),
		owned_tool_1 =
			emu:read32(campaign_telemetry_address + 72),
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
		selected_unit =
			emu:read32(battle_telemetry_address + 20),
		action_count =
			emu:read32(battle_telemetry_address + 76),
		selected_action_id =
			emu:read32(battle_telemetry_address + 84),
		selected_action_kind =
			emu:read32(battle_telemetry_address + 104),
		selected_action_tool_slot =
			emu:read32(battle_telemetry_address + 108),
		script_phase =
			emu:read32(battle_telemetry_address + 148),
	}
end

local frame = 0
local preparation_step = 0
local battle_step = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 30
local last_deployment_signature = ""
local last_progress_signature = ""

local function press(key)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = key
	emu:addKey(assert(keys[key]))
	release_frame = frame + 5
	return true
end

local function drive_deployment(battle)
	if battle.phase ~= PHASE_DEPLOY_UNIT and
			battle.phase ~= PHASE_DEPLOY_START then
		return false
	end
	local signature = string.format(
		"%d:%d", battle.phase, battle.selected_unit
	)
	if signature ~= last_deployment_signature and press("A") then
		last_deployment_signature = signature
	end
	return true
end

local function finish(campaign, battle)
	assert(campaign.save_generation >= 1)
	assert(campaign.save_slot >= 1)
	assert(campaign.save_verified == 1)
	assert(campaign.naruto_tool_0 == 1)
	assert(campaign.owned_tool_1 == 1)
	assert(campaign.owned_tool_67 == 1)
	assert(campaign.last_error == 0)
	assert(battle.battle_id == 41)
	assert(battle.phase == PHASE_ACTION_SELECTION)
	assert(battle.action_count > 0)
	assert(battle.selected_action_id == 1)
	assert(battle.selected_action_kind ==
		ACTION_KIND_NINJA_TOOL)
	assert(battle.selected_action_tool_slot == 0)
	emu:screenshot(
		output_dir .. "/battle-action-catalog-after-equipment.png"
	)
	local audit = string.format(
		'{"capture_frame":%d,"battle_id":%d,"battle_phase":%d,"action_count":%d,"selected_action_id":%d,"selected_action_kind":%d,"selected_action_tool_slot":%d,"save_generation":%d,"save_slot":%d,"save_verified":%d,"naruto_tool_0":%d,"owned_tool_1":%d,"owned_tool_67":%d,"last_error":%d,"status":"preparation-equipment-complete"}',
		frame,
		battle.battle_id,
		battle.phase,
		battle.action_count,
		battle.selected_action_id,
		battle.selected_action_kind,
		battle.selected_action_tool_slot,
		campaign.save_generation,
		campaign.save_slot,
		campaign.save_verified,
		campaign.naruto_tool_0,
		campaign.owned_tool_1,
		campaign.owned_tool_67,
		campaign.last_error
	)
	write_file(output_dir .. "/audit.json", audit)
	write_file(done_marker_path, audit)
	complete = true
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame > 2400 then
		emu:screenshot(output_dir .. "/stalled.png")
		assert(false, "equipment route timed out")
	end
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
	local progress_signature = string.format(
		"%d:%d:%s:%s:%s",
		preparation_step,
		battle_step,
		battle and tostring(battle.phase) or "none",
		battle and tostring(battle.selected_action_id) or
			"none",
		battle and tostring(battle.script_phase) or "none"
	)
	if progress_signature ~= last_progress_signature then
		last_progress_signature = progress_signature
		write_file(
			output_dir .. "/progress.json",
			string.format(
				'{"frame":%d,"preparation_step":%d,"battle_step":%d,"battle_phase":%d,"selected_action_id":%d,"script_phase":%d}',
				frame,
				preparation_step,
				battle_step,
				battle and battle.phase or 0,
				battle and battle.selected_action_id or 0,
				battle and battle.script_phase or 0
			)
		)
	end
	if not battle or battle.battle_id ~= 41 then
		if preparation_step == 0 and press("Down") then
			preparation_step = 1
		elseif preparation_step == 1 and press("Down") then
			preparation_step = 2
		elseif preparation_step == 2 and press("A") then
			preparation_step = 3
		elseif preparation_step == 3 and press("A") then
			preparation_step = 4
		elseif preparation_step == 4 and not active_key and
				frame >= next_press_frame then
			emu:screenshot(
				output_dir .. "/unequip-complete.png"
			)
			if press("A") then
				preparation_step = 5
			end
		elseif preparation_step == 5 and press("B") then
			preparation_step = 6
		elseif preparation_step == 6 and press("Up") then
			preparation_step = 7
		elseif preparation_step == 7 and press("A") then
			preparation_step = 8
		elseif preparation_step == 8 and press("A") then
			preparation_step = 9
		elseif preparation_step == 9 and not active_key and
				frame >= next_press_frame then
			emu:screenshot(
				output_dir .. "/equip-complete.png"
			)
			if press("A") then
				preparation_step = 10
			end
		elseif preparation_step == 10 and press("B") then
			preparation_step = 11
		elseif preparation_step == 11 and press("Up") then
			preparation_step = 12
		elseif preparation_step == 12 and press("A") then
			preparation_step = 13
		end
		return
	end

	if drive_deployment(battle) then
		return
	end
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if active_key then
		return
	end
	if battle_step == 0 and
			battle.phase == PHASE_UNIT_SELECTION then
		if press("A") then
			battle_step = 1
		end
	elseif battle_step == 1 and
			battle.phase == PHASE_MOVE_SELECTION then
		if press("A") then
			battle_step = 2
		end
	elseif battle_step == 2 and
			battle.phase == PHASE_COMMAND_SELECTION then
		if press("A") then
			battle_step = 3
		end
	elseif battle_step == 3 and
			battle.phase == PHASE_ACTION_SELECTION then
		if battle.selected_action_id == 1 and
			battle.selected_action_kind ==
				ACTION_KIND_NINJA_TOOL and
			battle.selected_action_tool_slot == 0 then
			finish(campaign, battle)
		else
			press("Down")
		end
	end
end)
