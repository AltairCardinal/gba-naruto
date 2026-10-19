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

local output_dir = required_env("MGBA_EFFECT_FLAG_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_EFFECT_FLAG_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_EFFECT_FLAG_TELEMETRY_ADDRESS")
))

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_ACTION_SELECTION = 6
local PHASE_TARGET_SELECTION = 8
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local ACTION_KIND_NINJA_TOOL = 1

local keys = {
	A = C.GBA_KEY.A,
	Down = C.GBA_KEY.DOWN,
	Up = C.GBA_KEY.UP,
}

local function read_telemetry()
	if emu:read32(telemetry_address) ~= TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id = emu:read32(telemetry_address + 4),
		phase = emu:read32(telemetry_address + 8),
		round = emu:read32(telemetry_address + 12),
		scene_frame = emu:read32(telemetry_address + 44),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		presentation_busy = emu:read32(telemetry_address + 68),
		selected_action_id = emu:read32(telemetry_address + 84),
		last_resolved_action_id = emu:read32(telemetry_address + 92),
		selected_action_kind = emu:read32(telemetry_address + 104),
		script_phase = emu:read32(telemetry_address + 148),
		cursor_unit_id = emu:read32(telemetry_address + 304),
		cursor_unit_attack = emu:read32(telemetry_address + 308),
		cursor_unit_defense = emu:read32(telemetry_address + 312),
		cursor_unit_agility = emu:read32(telemetry_address + 316),
		cursor_unit_status_count = emu:read32(telemetry_address + 320),
		cursor_unit_active = emu:read32(telemetry_address + 324),
		cursor_unit_hp = emu:read32(telemetry_address + 328),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local last_deployment_signature = ""
local step = 0
local route_start_frame = nil
local before_attack = nil
local before_defense = nil
local before_agility = nil

local function press(key)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = key
	emu:addKey(assert(keys[key]))
	release_frame = frame + 6
	return true
end

local function drive_deployment(telemetry)
	if telemetry.phase ~= PHASE_DEPLOY_UNIT and
			telemetry.phase ~= PHASE_DEPLOY_START then
		return false
	end
	local signature = string.format(
		"%d:%d", telemetry.phase,
		emu:read32(telemetry_address + 20)
	)
	if signature ~= last_deployment_signature and press("A") then
		last_deployment_signature = signature
	end
	return true
end

local function finish(telemetry)
	assert(telemetry.cursor_unit_id == 2)
	assert(telemetry.cursor_unit_status_count == 3)
	assert(telemetry.cursor_unit_active == 0)
	assert(telemetry.cursor_unit_hp == 0)
	assert(telemetry.last_resolved_action_id == 11)
	assert(telemetry.presentation_busy == 1)
	assert(telemetry.last_control_error == 0)
	assert(telemetry.last_player_error == 0)
	emu:screenshot(output_dir .. "/poison-resolved.png")
	local audit = string.format(
		'{"capture_frame":%d,"scene_frame":%d,"battle_id":%d,' ..
		'"round":%d,"action_id":%d,"target_unit_id":%d,' ..
		'"target_active":%d,"target_hp":%d,"status_count":%d,' ..
		'"attack_before":%d,"attack_after":%d,' ..
		'"defense_before":%d,"defense_after":%d,' ..
		'"agility_before":%d,"agility_after":%d,' ..
		'"last_control_error":%d,"last_player_error":%d,' ..
		'"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X",' ..
		'"status":"capture-complete"}',
		frame,
		telemetry.scene_frame,
		telemetry.battle_id,
		telemetry.round,
		telemetry.last_resolved_action_id,
		telemetry.cursor_unit_id,
		telemetry.cursor_unit_active,
		telemetry.cursor_unit_hp,
		telemetry.cursor_unit_status_count,
		before_attack,
		telemetry.cursor_unit_attack,
		before_defense,
		telemetry.cursor_unit_defense,
		before_agility,
		telemetry.cursor_unit_agility,
		telemetry.last_control_error,
		telemetry.last_player_error,
		emu:readRegister("pc"),
		emu:readRegister("lr"),
		emu:readRegister("sp")
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
	if active_key and frame >= release_frame then
		emu:clearKey(assert(keys[active_key]))
		active_key = nil
		next_press_frame = frame + 3
	end

	local telemetry = read_telemetry()
	if not telemetry or telemetry.battle_id ~= 41 then
		return
	end
	if route_start_frame and frame - route_start_frame > 1000 then
		emu:screenshot(output_dir .. "/stalled.png")
		write_file(
			output_dir .. "/stalled.json",
			string.format(
				'{"frame":%d,"step":%d,"phase":%d,' ..
				'"last_resolved_action_id":%d,"target_unit_id":%d,' ..
				'"status_count":%d,"last_control_error":%d,' ..
				'"last_player_error":%d}',
				frame,
				step,
				telemetry.phase,
				telemetry.last_resolved_action_id,
				telemetry.cursor_unit_id,
				telemetry.cursor_unit_status_count,
				telemetry.last_control_error,
				telemetry.last_player_error
			)
		)
		assert(false, "effect flag route timed out")
	end
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if telemetry.last_resolved_action_id == 11 and
			telemetry.cursor_unit_id == 2 and
			telemetry.cursor_unit_status_count == 3 and
			telemetry.cursor_unit_active == 0 and
			telemetry.cursor_unit_hp == 0 then
		finish(telemetry)
		return
	end
	if active_key or telemetry.presentation_busy == 1 then
		return
	end

	if step == 0 and telemetry.phase == PHASE_UNIT_SELECTION then
		route_start_frame = frame
		if press("A") then
			step = 1
		end
	elseif step >= 1 and step <= 3 and
			telemetry.phase == PHASE_MOVE_SELECTION then
		if press("Up") then
			step = step + 1
		end
	elseif step == 4 and telemetry.phase == PHASE_MOVE_SELECTION then
		if press("A") then
			step = 5
		end
	elseif step == 5 and telemetry.phase == PHASE_COMMAND_SELECTION then
		if press("A") then
			step = 6
		end
	elseif step == 6 and telemetry.phase == PHASE_ACTION_SELECTION then
		if telemetry.selected_action_id == 11 and
				telemetry.selected_action_kind == ACTION_KIND_NINJA_TOOL then
			if press("A") then
				step = 7
			end
		else
			press("Down")
		end
	elseif step >= 7 and step <= 9 and
			telemetry.phase == PHASE_TARGET_SELECTION then
		if press("Up") then
			step = step + 1
		end
	elseif step == 10 and telemetry.phase == PHASE_TARGET_SELECTION then
		assert(telemetry.cursor_unit_id == 2)
		assert(telemetry.cursor_unit_status_count == 0)
		assert(telemetry.cursor_unit_active == 1)
		assert(telemetry.cursor_unit_hp > 0)
		before_attack = telemetry.cursor_unit_attack
		before_defense = telemetry.cursor_unit_defense
		before_agility = telemetry.cursor_unit_agility
		if press("A") then
			step = 11
		end
	end
end)
