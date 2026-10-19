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

local function append_file(path, payload)
	local output = assert(io.open(path, "a"))
	output:write(payload)
	output:close()
end

local output_dir =
	required_env("MGBA_B32_DEPLOY_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_B32_DEPLOY_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_B32_DEPLOY_TELEMETRY_ADDRESS")
))
local samples_path = output_dir .. "/register-samples.jsonl"
local inputs_path = output_dir .. "/input-events.jsonl"
write_file(samples_path, "")
write_file(inputs_path, "")

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local COMMAND_END_ACTION = 5

local keys = {
	A = C.GBA_KEY.A,
	Down = C.GBA_KEY.DOWN,
	Select = C.GBA_KEY.SELECT,
}

local expected_deployment = { 1, 2, 3, 12, 35, 1 }
local observed_deployment = {}
local observed_ai_substitution = false

local function read_telemetry()
	if emu:read32(telemetry_address) ~= TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id = emu:read32(telemetry_address + 4),
		phase = emu:read32(telemetry_address + 8),
		round = emu:read32(telemetry_address + 12),
		side = emu:read32(telemetry_address + 16),
		selected_unit = emu:read32(telemetry_address + 20),
		active_units = emu:read32(telemetry_address + 24),
		unit_count = emu:read32(telemetry_address + 28),
		selected_command = emu:read32(telemetry_address + 32),
		player_completed = emu:read32(telemetry_address + 36),
		enemy_completed = emu:read32(telemetry_address + 40),
		scene_frame = emu:read32(telemetry_address + 44),
		cursor_x = emu:read32(telemetry_address + 48),
		cursor_y = emu:read32(telemetry_address + 52),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		render_stage = emu:read32(telemetry_address + 64),
		presentation_busy = emu:read32(telemetry_address + 68),
		selected_character_id =
			emu:read32(telemetry_address + 72),
		background_chunk_index =
			emu:read32(telemetry_address + 96),
		background_chunk_count =
			emu:read32(telemetry_address + 100),
		script_phase = emu:read32(telemetry_address + 148),
		script_command_index = emu:read32(telemetry_address + 156),
		ai_secondary_planned = emu:read32(telemetry_address + 228),
		ai_defense_kind =
			emu:read32(telemetry_address + 232),
		ai_defense_action_id = emu:read32(telemetry_address + 236),
		ai_defense_tool_slot =
			emu:read32(telemetry_address + 240),
		ai_defense_score =
			emu:read32(telemetry_address + 244),
	}
end

local function signature(telemetry)
	if not telemetry then
		return "none"
	end
	return string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.round,
		telemetry.selected_unit,
		telemetry.selected_character_id,
		telemetry.selected_command,
		telemetry.player_completed,
		telemetry.enemy_completed,
		telemetry.presentation_busy,
		telemetry.script_phase,
		telemetry.script_command_index,
		telemetry.ai_secondary_planned,
		telemetry.ai_defense_action_id
	)
end

local function append_sample(frame, telemetry)
	append_file(
		samples_path,
		string.format(
			'{"frame":%d,"battle_id":%d,"phase":%d,"round":%d,"side":%d,"selected_unit":%d,"selected_character_id":%d,"active_units":%d,"unit_count":%d,"selected_command":%d,"player_completed":%d,"enemy_completed":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"last_control_error":%d,"last_player_error":%d,"render_stage":%d,"presentation_busy":%d,"background_chunk_index":%d,"background_chunk_count":%d,"ai_secondary_planned":%d,"ai_defense_kind":%d,"ai_defense_action_id":%d,"ai_defense_tool_slot":%d,"ai_defense_score":%d,"ie":"0x%04X","if":"0x%04X","ime":"0x%08X","irq_flags":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","keys":"0x%04X","cycles":%d}\n',
			frame,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.round,
			telemetry.side,
			telemetry.selected_unit,
			telemetry.selected_character_id,
			telemetry.active_units,
			telemetry.unit_count,
			telemetry.selected_command,
			telemetry.player_completed,
			telemetry.enemy_completed,
			telemetry.scene_frame,
			telemetry.cursor_x,
			telemetry.cursor_y,
			telemetry.last_control_error,
			telemetry.last_player_error,
			telemetry.render_stage,
			telemetry.presentation_busy,
			telemetry.background_chunk_index,
			telemetry.background_chunk_count,
			telemetry.ai_secondary_planned,
			telemetry.ai_defense_kind,
			telemetry.ai_defense_action_id,
			telemetry.ai_defense_tool_slot,
			telemetry.ai_defense_score,
			emu:read16(0x04000200),
			emu:read16(0x04000202),
			emu:read32(0x04000208),
			emu:read32(0x03007FF8),
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp"),
			emu:read16(0x04000130),
			emu:currentCycle()
		)
	)
end

local frame = 0
local active_key = nil
local active_key_name = nil
local release_frame = 0
local last_release_frame = -100
local last_issued_signature = "none"
local next_bootstrap_select_frame = 30
local last_sample_signature = "none"
local screenshots = {}
local screenshot_queue = {}
local completion_frame = nil
local complete = false

local function queue_screenshot(key, name)
	if screenshots[key] then
		return
	end
	screenshots[key] = true
	table.insert(
		screenshot_queue,
		{ due = frame + 3, name = name }
	)
end

local function flush_screenshots()
	for index = #screenshot_queue, 1, -1 do
		local entry = screenshot_queue[index]
		if frame >= entry.due then
			emu:screenshot(output_dir .. "/" .. entry.name)
			table.remove(screenshot_queue, index)
		end
	end
end

local function issue_key(name, telemetry, force_repeat)
	if active_key or frame - last_release_frame < 3 then
		return false
	end
	local current_signature = signature(telemetry)
	if current_signature == last_issued_signature and not force_repeat then
		return false
	end
	active_key = assert(keys[name])
	active_key_name = name
	emu:addKey(active_key)
	release_frame = frame + 6
	last_issued_signature = current_signature
	append_file(
		inputs_path,
		string.format(
			'{"frame":%d,"event":"press","key":"%s","battle_id":%d,"phase":%d,"round":%d,"selected_unit":%d,"selected_character_id":%d,"selected_command":%d}\n',
			frame,
			name,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.round,
			telemetry.selected_unit,
			telemetry.selected_character_id,
			telemetry.selected_command
		)
	)
	return true
end

local function record_dynamic_deployment(telemetry)
	if telemetry.battle_id ~= 32 or
			telemetry.phase ~= PHASE_DEPLOY_UNIT then
		return
	end
	local index = telemetry.selected_unit
	assert(index >= 1 and index <= #expected_deployment)
	assert(
		telemetry.selected_character_id ==
			expected_deployment[index],
		"dynamic placeholder resolved to wrong character"
	)
	observed_deployment[index] =
		telemetry.selected_character_id
	queue_screenshot(
		"deployment-" .. tostring(index),
		"deployment-unit-" .. tostring(index) .. ".png"
	)
end

local function drive_route(telemetry)
	if telemetry.ai_secondary_planned == 1 and
			telemetry.ai_defense_kind == 1 and
			telemetry.ai_defense_action_id == 3 then
		observed_ai_substitution = true
	end
	record_dynamic_deployment(telemetry)
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			issue_key("A", telemetry, true)
		end
		return
	end
	if telemetry.phase == PHASE_DEPLOY_UNIT or
			telemetry.phase == PHASE_DEPLOY_START then
		issue_key("A", telemetry)
		return
	end

	if telemetry.battle_id == 41 or
			telemetry.battle_id == 43 or
			telemetry.battle_id == 9 or
			telemetry.battle_id == 11 then
		if telemetry.phase == PHASE_UNIT_SELECTION then
			issue_key("Select", telemetry)
		end
		return
	end
	if telemetry.battle_id ~= 32 then
		return
	end

	assert(telemetry.active_units == 6)
	assert(telemetry.last_control_error == 0)
	assert(telemetry.last_player_error == 0)
	if telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot("round-2", "round-2-player.png")
		if not completion_frame then
			completion_frame = frame + 8
		end
		return
	end
	if telemetry.presentation_busy == 1 then
		return
	end

	if telemetry.phase == PHASE_UNIT_SELECTION then
		queue_screenshot("formation", "formation-3v3.png")
		issue_key("A", telemetry)
	elseif telemetry.phase == PHASE_MOVE_SELECTION then
		issue_key("A", telemetry)
	elseif telemetry.phase == PHASE_COMMAND_SELECTION then
		if telemetry.selected_command == COMMAND_END_ACTION then
			issue_key("A", telemetry)
		else
			issue_key("Down", telemetry)
		end
	elseif telemetry.phase == PHASE_FACING_SELECTION or
			telemetry.phase == PHASE_DEFENSE_DECISION then
		issue_key("A", telemetry)
	end
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1

	if active_key and frame >= release_frame then
		emu:clearKey(active_key)
		append_file(
			inputs_path,
			string.format(
				'{"frame":%d,"event":"release","key":"%s"}\n',
				frame,
				active_key_name
			)
		)
		active_key = nil
		active_key_name = nil
		last_release_frame = frame
	end

	local telemetry = read_telemetry()
	local current_signature = signature(telemetry)
	if telemetry and
			(current_signature ~= last_sample_signature or
				frame % 60 == 0) then
		append_sample(frame, telemetry)
		last_sample_signature = current_signature
	end

	if not telemetry and
			frame >= next_bootstrap_select_frame and
			not active_key then
		active_key = keys.Select
		active_key_name = "Select"
		emu:addKey(active_key)
		release_frame = frame + 6
		last_issued_signature =
			"bootstrap-select-" .. tostring(frame)
		next_bootstrap_select_frame = frame + 60
	elseif telemetry and not active_key then
		drive_route(telemetry)
	end

	flush_screenshots()
	if completion_frame and frame >= completion_frame and
			#screenshot_queue == 0 then
		for index = 1, #expected_deployment do
			assert(
				observed_deployment[index] ==
					expected_deployment[index]
			)
		end
		assert(telemetry and telemetry.battle_id == 32)
		assert(telemetry.active_units == 6)
		assert(telemetry.round >= 2)
		assert(telemetry.phase == PHASE_UNIT_SELECTION)
		assert(telemetry.last_control_error == 0)
		assert(telemetry.last_player_error == 0)
		assert(observed_ai_substitution)
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"battle_id":32,"deployment":[1,2,3,12,35,1],"actual_active_units":%d,"actual_round":%d,"actual_phase":%d,"ai_substitution":true,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","cycles":%d,"status":"capture-complete"}',
				frame,
				telemetry.active_units,
				telemetry.round,
				telemetry.phase,
				emu:readRegister("pc"),
				emu:readRegister("lr"),
				emu:readRegister("sp"),
				emu:currentCycle()
			)
		)
		write_file(
			done_marker_path,
			string.format(
				'{"capture_frame":%d,"status":"capture-complete"}',
				frame
			)
		)
		complete = true
	end
end)
