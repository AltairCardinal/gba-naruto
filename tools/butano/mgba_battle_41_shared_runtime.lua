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

local output_dir = required_env("MGBA_S41_SHARED_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_S41_SHARED_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_S41_SHARED_TELEMETRY_ADDRESS")
))
local continue_results =
	os.getenv("MGBA_S41_SHARED_CONTINUE_RESULTS") == "1"
local skip_training =
	os.getenv("MGBA_S41_SHARED_SKIP_TRAINING") == "1"
local campaign_telemetry_address_value =
	os.getenv("MGBA_S41_SHARED_CAMPAIGN_TELEMETRY_ADDRESS")
local campaign_telemetry_address = nil
if campaign_telemetry_address_value and
		campaign_telemetry_address_value ~= "" then
	campaign_telemetry_address = assert(parse_number(
		campaign_telemetry_address_value
	))
end

local TELEMETRY_MAGIC = 0x4B42544C
local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_ACTION_SELECTION = 6
local PHASE_TARGET_SELECTION = 8
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
local PHASE_ENEMY_TURN = 12
local PHASE_OUTCOME = 13
local PHASE_RESULT = 14
local PHASE_LEVEL_UP = 15
local PHASE_COMPLETE = 16
local PHASE_SCRIPT_BLOCKED = 18
local PHASE_TRAINING = 19
local PHASE_TARGET_CONFIRMATION = 20
local PHASE_END_CONFIRMATION = 21
local PHASE_TARGET_PREVIEW = 22
local SCRIPT_WAIT_FOR_INPUT = 1
local COMBAT_STAGE_ACTOR_PREP = 2
local COMMAND_MOVE = 0
local COMMAND_ABILITY = 1
local COMMAND_END_ACTION = 5
local ACTION_COMBO = 5
local ACTION_TRAIN = 8
local TRAINING_SECONDARY_PASSIVE = 1
local PREPARATION_SETTLE_FRAME = 120

local keys = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
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
		selected_unit = emu:read32(telemetry_address + 20),
		active_units = emu:read32(telemetry_address + 24),
		selected_command = emu:read32(telemetry_address + 32),
		scene_frame = emu:read32(telemetry_address + 44),
		cursor_x = emu:read32(telemetry_address + 48),
		cursor_y = emu:read32(telemetry_address + 52),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		presentation_busy = emu:read32(telemetry_address + 68),
		action_count = emu:read32(telemetry_address + 76),
		selected_action_id = emu:read32(telemetry_address + 84),
		last_resolved_action_id = emu:read32(telemetry_address + 92),
		result_participant_count = emu:read32(telemetry_address + 112),
		result_mission_experience = emu:read32(telemetry_address + 116),
		result_battle_experience = emu:read32(telemetry_address + 120),
		result_round_bonus_experience = emu:read32(telemetry_address + 124),
		result_total_experience = emu:read32(telemetry_address + 128),
		result_level_before = emu:read32(telemetry_address + 132),
		result_level_after = emu:read32(telemetry_address + 136),
		result_experience_after = emu:read32(telemetry_address + 140),
		result_hp_growth = emu:read32(telemetry_address + 144),
		script_phase = emu:read32(telemetry_address + 148),
		script_selector = emu:read32(telemetry_address + 152),
		script_command_index =
			emu:read32(telemetry_address + 156),
		script_text_address =
			emu:read32(telemetry_address + 160),
		cursor_unit_id = emu:read32(telemetry_address + 304),
		cursor_unit_active = emu:read32(telemetry_address + 324),
		training_character_id = emu:read32(telemetry_address + 336),
		training_action_id = emu:read32(telemetry_address + 340),
		training_action_level = emu:read32(telemetry_address + 344),
		training_points = emu:read32(telemetry_address + 348),
		training_error = emu:read32(telemetry_address + 352),
		training_entry_kind = emu:read32(telemetry_address + 356),
		presentation_combat_stage = emu:read32(telemetry_address + 364),
		presentation_combat_stage_frame = emu:read32(telemetry_address + 368),
		selected_unit_x = emu:read32(telemetry_address + 384),
		selected_unit_y = emu:read32(telemetry_address + 388),
		first_active_enemy_x =
			emu:read32(telemetry_address + 392),
		first_active_enemy_y =
			emu:read32(telemetry_address + 396),
	}
end

local function read_campaign_telemetry()
	if not campaign_telemetry_address or
			emu:read32(campaign_telemetry_address) ~=
				CAMPAIGN_TELEMETRY_MAGIC then
		return nil
	end
	return {
		load_generation =
			emu:read32(campaign_telemetry_address + 4),
		load_slot =
			emu:read32(campaign_telemetry_address + 8),
		load_used_default =
			emu:read32(campaign_telemetry_address + 12),
		save_generation =
			emu:read32(campaign_telemetry_address + 16),
		save_slot =
			emu:read32(campaign_telemetry_address + 20),
		save_verified =
			emu:read32(campaign_telemetry_address + 24),
		naruto_level =
			emu:read32(campaign_telemetry_address + 28),
		naruto_experience =
			emu:read32(campaign_telemetry_address + 32),
		naruto_training_points =
			emu:read32(campaign_telemetry_address + 36),
		naruto_action_8_level =
			emu:read32(campaign_telemetry_address + 40),
		naruto_tool_0 =
			emu:read32(campaign_telemetry_address + 44),
		naruto_tool_1 =
			emu:read32(campaign_telemetry_address + 48),
		naruto_tool_2 =
			emu:read32(campaign_telemetry_address + 52),
		owned_tool_67 =
			emu:read32(campaign_telemetry_address + 56),
		owned_tool_68 =
			emu:read32(campaign_telemetry_address + 60),
		material_6 =
			emu:read32(campaign_telemetry_address + 64),
		last_error =
			emu:read32(campaign_telemetry_address + 68),
		scenario_id =
			emu:read32(campaign_telemetry_address + 76),
		route_complete =
			emu:read32(campaign_telemetry_address + 80),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local last_deployment_signature = ""
local step = 10
local route_round = 1
local round_stage = 0
local presentation_start_frame = nil
local settle_ready_frame = nil
local result_step = 0
local training_action_id = 0
local training_level_before = 0
local training_level_after = 0
local training_points_before = 0
local training_points_after = 0
local captured = {}
local last_progress_signature = ""
local last_battle_telemetry = nil
local preparation_step = 0
local dialogue_ready_scene_frame = nil
local last_dialogue_signature = ""
local presentation_trace_records = {}
local last_presentation_trace_signature = ""

local function press(key)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = key
	emu:addKey(assert(keys[key]))
	release_frame = frame + 6
	return true
end

local function capture_once(key, name)
	if captured[key] then
		return
	end
	emu:screenshot(output_dir .. "/" .. name)
	captured[key] = true
end

local function record_presentation_trace(telemetry)
	if telemetry.presentation_busy ~= 1 then
		return
	end
	local signature = string.format(
		"%d:%d:%d:%d:%d",
		route_round,
		round_stage,
		telemetry.phase,
		telemetry.presentation_combat_stage,
		telemetry.presentation_combat_stage_frame
	)
	if signature == last_presentation_trace_signature then
		return
	end
	last_presentation_trace_signature = signature
	presentation_trace_records[
		#presentation_trace_records + 1
	] = string.format(
		'{"frame":%d,"route_round":%d,"round_stage":%d,"phase":%d,"combat_stage":%d,"combat_stage_frame":%d,"selected_unit_x":%d,"selected_unit_y":%d,"enemy_x":%d,"enemy_y":%d,"selected_action_id":%d,"last_resolved_action_id":%d}',
		frame,
		route_round,
		round_stage,
		telemetry.phase,
		telemetry.presentation_combat_stage,
		telemetry.presentation_combat_stage_frame,
		telemetry.selected_unit_x,
		telemetry.selected_unit_y,
		telemetry.first_active_enemy_x,
		telemetry.first_active_enemy_y,
		telemetry.selected_action_id,
		telemetry.last_resolved_action_id
	)
end

local function write_presentation_trace()
	write_file(
		output_dir .. "/combat-trace.json",
		"[" .. table.concat(
			presentation_trace_records, ","
		) .. "]"
	)
end

local function drive_deployment(telemetry)
	if telemetry.phase ~= PHASE_DEPLOY_UNIT and
			telemetry.phase ~= PHASE_DEPLOY_START then
		return false
	end
	local signature = string.format(
		"%d:%d", telemetry.phase, telemetry.selected_unit
	)
	if signature ~= last_deployment_signature and press("A") then
		last_deployment_signature = signature
	end
	return true
end

local function move_cursor_to(telemetry, target_x, target_y)
	if telemetry.cursor_x < target_x then
		press("Right")
	elseif telemetry.cursor_x > target_x then
		press("Left")
	elseif telemetry.cursor_y < target_y then
		press("Down")
	elseif telemetry.cursor_y > target_y then
		press("Up")
	else
		return true
	end
	return false
end

local function set_round_stage(stage)
	round_stage = stage
	step = route_round * 10 + round_stage
end

local function finish_route_round()
	route_round = route_round + 1
	round_stage = 0
	step = route_round * 10
end

local function drive_round(
		telemetry,
		expected_round,
		target_x,
		target_y,
		attack)
	if route_round ~= expected_round then
		return false
	end
	assert(
		telemetry.round <= expected_round,
		"shared route skipped expected round"
	)
	if telemetry.round < expected_round then
		return true
	end
	if telemetry.phase == PHASE_MOVE_SELECTION then
		capture_once("move-ui", "move-ui.png")
	elseif telemetry.phase == PHASE_TARGET_CONFIRMATION then
		capture_once(
			"attack-confirmation",
			"attack-confirmation.png"
		)
	elseif telemetry.phase == PHASE_END_CONFIRMATION then
		capture_once(
			"end-confirmation",
			"end-confirmation.png"
		)
	elseif telemetry.phase == PHASE_FACING_SELECTION then
		capture_once("facing", "facing.png")
	elseif telemetry.phase == PHASE_DEFENSE_DECISION then
		capture_once(
			"defense-confirmation",
			"defense-confirmation.png"
		)
	end
	if attack and round_stage >= 5 and
			telemetry.phase == PHASE_OUTCOME then
		finish_route_round()
		return true
	end

	-- A phase can change after the script has already advanced its local
	-- stage.  Retry only idempotent navigation/confirmation inputs while the
	-- old phase is still visible; defense yes/no toggles are deliberately
	-- excluded because repeating Down would invert the choice twice.
	if round_stage == 1 and
			telemetry.phase == PHASE_UNIT_SELECTION then
		press("A")
		return true
	elseif round_stage == 2 and
			telemetry.phase == PHASE_COMMAND_SELECTION then
		assert(telemetry.selected_command == COMMAND_MOVE)
		press("A")
		return true
	elseif round_stage == 3 and
			telemetry.phase == PHASE_MOVE_SELECTION then
		if move_cursor_to(telemetry, target_x, target_y) then
			press("A")
		end
		return true
	elseif round_stage == 4 and
			telemetry.phase == PHASE_COMMAND_SELECTION then
		if attack and telemetry.selected_command ~=
				COMMAND_ABILITY then
			press("Up")
		elseif not attack and telemetry.selected_command ~=
				COMMAND_END_ACTION then
			press("Down")
		else
			press("A")
		end
		return true
	elseif attack and round_stage == 5 and
			telemetry.phase == PHASE_ACTION_SELECTION then
		press("A")
		return true
	elseif not attack and round_stage == 5 and
			telemetry.phase == PHASE_END_CONFIRMATION then
		press("A")
		return true
	elseif attack and round_stage == 6 and
			telemetry.phase == PHASE_TARGET_SELECTION then
		if move_cursor_to(
			telemetry,
			telemetry.first_active_enemy_x,
			telemetry.first_active_enemy_y
		) then
			press("A")
		end
		return true
	elseif attack and round_stage == 6 and
			telemetry.phase == PHASE_TARGET_PREVIEW then
		press("A")
		return true
	elseif not attack and round_stage == 6 and
			telemetry.phase == PHASE_FACING_SELECTION then
		if telemetry.presentation_busy == 0 then
			press("A")
		end
		return true
	elseif attack and round_stage == 7 and
			telemetry.phase == PHASE_TARGET_CONFIRMATION then
		press("A")
		return true
	elseif attack and round_stage == 8 and
			telemetry.phase == PHASE_FACING_SELECTION then
		if telemetry.presentation_busy == 0 then
			press("A")
		end
		return true
	end

	if round_stage == 0 and
			telemetry.phase == PHASE_UNIT_SELECTION then
		if expected_round == 1 then
			capture_once("formation", "formation.png")
		end
		if press("A") then
			set_round_stage(1)
		end
	elseif round_stage == 1 and
			telemetry.phase == PHASE_COMMAND_SELECTION then
		capture_once(
			"action-menu-0",
			"action-menu-0.png"
		)
		assert(telemetry.selected_command == COMMAND_MOVE)
		if press("A") then
			set_round_stage(2)
		end
	elseif round_stage == 2 and
			telemetry.phase == PHASE_MOVE_SELECTION then
		assert(telemetry.selected_unit_x ~= 0xFFFFFFFF)
		assert(telemetry.selected_unit_y ~= 0xFFFFFFFF)
		if move_cursor_to(telemetry, target_x, target_y) and
				press("A") then
			set_round_stage(3)
		end
	elseif round_stage == 3 and
		telemetry.phase == PHASE_COMMAND_SELECTION then
		capture_once(
			"action-menu-1",
			"action-menu-1.png"
		)
		if attack then
			if telemetry.selected_command ~=
					COMMAND_ABILITY then
				press("Up")
			elseif press("A") then
				set_round_stage(4)
			end
		elseif telemetry.selected_command ~=
				COMMAND_END_ACTION then
			press("Down")
		elseif press("A") then
			set_round_stage(4)
		end
	elseif attack and round_stage == 4 and
			telemetry.phase == PHASE_ACTION_SELECTION then
		capture_once("actions", "actions.png")
		assert(
			telemetry.action_count == 1,
			"scenario 41 must expose only taijutsu"
		)
		assert(
			telemetry.selected_action_id == ACTION_COMBO,
			"scenario 41 selected a forbidden action"
		)
		if press("A") then
			set_round_stage(5)
		end
	elseif attack and round_stage == 5 and
			telemetry.phase == PHASE_TARGET_SELECTION then
		assert(telemetry.first_active_enemy_x ~= 0xFFFFFFFF)
		assert(telemetry.first_active_enemy_y ~= 0xFFFFFFFF)
		if move_cursor_to(
				telemetry,
				telemetry.first_active_enemy_x,
				telemetry.first_active_enemy_y
			) then
			assert(telemetry.cursor_unit_active == 1)
			assert(
				telemetry.cursor_unit_id ~=
					telemetry.selected_unit
			)
			capture_once("target", "target.png")
			if press("A") then
				set_round_stage(6)
			end
		end
	elseif attack and round_stage == 6 and
			telemetry.phase == PHASE_TARGET_PREVIEW then
		press("A")
	elseif attack and round_stage == 6 and
			telemetry.phase == PHASE_TARGET_CONFIRMATION then
		capture_once(
			"attack-confirmation",
			"attack-confirmation.png"
		)
		if press("A") then
			set_round_stage(7)
		end
	elseif not attack and round_stage == 4 and
			telemetry.phase == PHASE_END_CONFIRMATION then
		if press("A") then
			set_round_stage(5)
		end
	elseif not attack and round_stage == 5 and
			telemetry.phase == PHASE_FACING_SELECTION then
		if telemetry.presentation_busy == 0 and
				press("A") then
			set_round_stage(6)
		end
	elseif not attack and round_stage == 6 and
			telemetry.phase == PHASE_DEFENSE_DECISION then
		if press("Down") then
			set_round_stage(7)
		end
	elseif attack and round_stage == 7 and
			telemetry.phase == PHASE_FACING_SELECTION then
		if telemetry.presentation_busy == 0 and
				press("A") then
			set_round_stage(8)
		end
	elseif attack and round_stage == 8 and
			telemetry.phase == PHASE_DEFENSE_DECISION then
		if press("Down") then
			set_round_stage(9)
		end
	elseif not attack and round_stage == 7 and
			telemetry.phase == PHASE_DEFENSE_DECISION then
		if press("A") then
			set_round_stage(8)
		end
	elseif attack and round_stage == 9 and
			telemetry.phase == PHASE_DEFENSE_DECISION then
		if press("A") then
			set_round_stage(10)
		end
	elseif not attack and round_stage == 8 then
		if telemetry.phase == PHASE_DEFENSE_DECISION then
			press("A")
		else
			finish_route_round()
		end
	elseif attack and round_stage == 10 then
		if telemetry.phase == PHASE_DEFENSE_DECISION then
			press("A")
		else
			finish_route_round()
		end
	end
	return true
end

local function capture_animation(telemetry)
	if telemetry.presentation_busy ~= 1 then
		return
	end
	if not presentation_start_frame then
		presentation_start_frame = frame
	end
	local elapsed = frame - presentation_start_frame
	if elapsed >= 4 then
		capture_once("movement", "movement.png")
	end
	if elapsed >= 20 then
		capture_once("combat-start", "combat-start.png")
	end
	if elapsed >= 48 then
		capture_once("combat-impact", "combat-impact.png")
	end
	if elapsed >= 60 then
		capture_once("combat-return", "combat-return.png")
	end
end

local function finish(telemetry)
	if complete or
			not captured["movement"] or
			not captured["combat-start"] or
			not captured["combat-impact"] or
			not captured["combat-return"] then
		return
	end
	if not settle_ready_frame then
		settle_ready_frame = frame + 2
		return
	end
	if frame < settle_ready_frame then
		return
	end
	capture_once("settled", "settled.png")
	write_presentation_trace()
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"battle_id":%d,"round":%d,"phase":%d,"selected_unit":%d,"active_units":%d,"last_resolved_action_id":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"capture-complete"}',
			frame,
			telemetry.battle_id,
			telemetry.round,
			telemetry.phase,
			telemetry.selected_unit,
			telemetry.active_units,
			telemetry.last_resolved_action_id,
			telemetry.last_control_error,
			telemetry.last_player_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
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

local function finish_results(telemetry)
	if not settle_ready_frame then
		settle_ready_frame = frame + 2
		return
	end
	if frame < settle_ready_frame then
		return
	end
	write_presentation_trace()
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"battle_id":%d,"round":%d,"phase":%d,"result_participant_count":%d,"result_mission_experience":%d,"result_battle_experience":%d,"result_round_bonus_experience":%d,"result_total_experience":%d,"result_level_before":%d,"result_level_after":%d,"result_experience_after":%d,"result_hp_growth":%d,"training_action_id":%d,"training_level_before":%d,"training_level_after":%d,"training_points_before":%d,"training_points_after":%d,"last_resolved_action_id":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"capture-complete"}',
			frame,
			telemetry.battle_id,
			telemetry.round,
			telemetry.phase,
			telemetry.result_participant_count,
			telemetry.result_mission_experience,
			telemetry.result_battle_experience,
			telemetry.result_round_bonus_experience,
			telemetry.result_total_experience,
			telemetry.result_level_before,
			telemetry.result_level_after,
			telemetry.result_experience_after,
			telemetry.result_hp_growth,
			training_action_id,
			training_level_before,
			training_level_after,
			training_points_before,
			training_points_after,
			telemetry.last_resolved_action_id,
			telemetry.last_control_error,
			telemetry.last_player_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
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

local function finish_campaign_save(campaign)
	if complete then
		return
	end
	assert(campaign.save_generation >= 1)
	assert(campaign.save_slot >= 1)
	assert(campaign.save_verified == 1)
	assert(campaign.naruto_level == 2)
	assert(campaign.naruto_experience == 0)
	if skip_training then
		assert(campaign.naruto_training_points == 1)
		assert(campaign.naruto_action_8_level == 0)
	else
		assert(campaign.naruto_training_points == 0)
		assert(campaign.naruto_action_8_level == 1)
	end
	assert(campaign.scenario_id == 42)
	assert(campaign.route_complete == 0)
	assert(campaign.last_error == 0)
	assert(last_battle_telemetry)
	capture_once("campaign-saved", "campaign-saved.png")
	write_presentation_trace()
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"battle_id":%d,"round":%d,"phase":%d,"result_total_experience":%d,"training_action_id":%d,"training_level_before":%d,"training_level_after":%d,"training_points_before":%d,"training_points_after":%d,"campaign_load_generation":%d,"campaign_load_used_default":%d,"campaign_save_generation":%d,"campaign_save_slot":%d,"campaign_save_verified":%d,"campaign_naruto_level":%d,"campaign_naruto_experience":%d,"campaign_naruto_training_points":%d,"campaign_naruto_action_8_level":%d,"campaign_naruto_tool_0":%d,"campaign_naruto_tool_1":%d,"campaign_naruto_tool_2":%d,"campaign_scenario_id":%d,"campaign_route_complete":%d,"campaign_last_error":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"campaign-save-complete"}',
			frame,
			last_battle_telemetry.battle_id,
			last_battle_telemetry.round,
			last_battle_telemetry.phase,
			last_battle_telemetry.result_total_experience,
			training_action_id,
			training_level_before,
			training_level_after,
			training_points_before,
			training_points_after,
			campaign.load_generation,
			campaign.load_used_default,
			campaign.save_generation,
			campaign.save_slot,
			campaign.save_verified,
			campaign.naruto_level,
			campaign.naruto_experience,
			campaign.naruto_training_points,
			campaign.naruto_action_8_level,
			campaign.naruto_tool_0,
			campaign.naruto_tool_1,
			campaign.naruto_tool_2,
			campaign.scenario_id,
			campaign.route_complete,
			campaign.last_error,
			last_battle_telemetry.last_control_error,
			last_battle_telemetry.last_player_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
	)
	write_file(
		done_marker_path,
		string.format(
			'{"capture_frame":%d,"status":"campaign-save-complete"}',
			frame
		)
	)
	complete = true
end

local function drive_results(telemetry)
	if result_step == 0 and telemetry.phase == PHASE_OUTCOME then
		capture_once("outcome", "outcome.png")
		if press("A") then
			result_step = 1
		end
	elseif result_step == 1 and telemetry.phase == PHASE_RESULT then
		assert(telemetry.result_participant_count == 1)
		assert(telemetry.result_mission_experience == 100)
		assert(telemetry.result_battle_experience == 50)
		assert(telemetry.result_round_bonus_experience == 0)
		assert(telemetry.result_total_experience == 150)
		capture_once("result", "result.png")
		if press("A") then
			result_step = 2
		end
	elseif result_step == 2 and telemetry.phase == PHASE_LEVEL_UP then
		assert(telemetry.result_level_before == 1)
		assert(telemetry.result_level_after == 2)
		assert(telemetry.result_experience_after == 0)
		assert(telemetry.result_hp_growth == 14)
		capture_once("level-up", "level-up.png")
		if press("A") then
			result_step = 3
		end
	elseif result_step == 3 and telemetry.phase == PHASE_TRAINING then
		assert(telemetry.training_character_id == 1)
		assert(telemetry.training_points == 1)
		if skip_training then
			capture_once("training-before", "training-before.png")
			if press("B") then
				result_step = 5
			end
		elseif telemetry.training_action_id ~= ACTION_TRAIN then
			press("Down")
		else
			assert(telemetry.training_action_level == 0)
			assert(telemetry.training_error == 0)
			training_action_id = telemetry.training_action_id
			training_level_before = telemetry.training_action_level
			training_points_before = telemetry.training_points
			capture_once("training-before", "training-before.png")
			if press("A") then
				result_step = 4
			end
		end
	elseif result_step == 4 and telemetry.phase == PHASE_TRAINING then
		assert(telemetry.training_points == 0)
		assert(telemetry.training_error == 0)
		if not captured["training-after"] then
			assert(telemetry.training_action_id == ACTION_TRAIN)
			assert(telemetry.training_action_level == 1)
			training_level_after = telemetry.training_action_level
			training_points_after = telemetry.training_points
			capture_once("training-after", "training-after.png")
		end
		if telemetry.training_entry_kind ==
				TRAINING_SECONDARY_PASSIVE then
			assert(telemetry.training_action_id == 1)
			assert(telemetry.training_action_level == 0xFF)
			capture_once(
				"training-passive",
				"training-passive.png"
			)
			if press("B") then
				result_step = 5
			end
		else
			press("Down")
		end
	elseif result_step == 5 and telemetry.phase == PHASE_COMPLETE then
		capture_once("result-complete", "result-complete.png")
		if campaign_telemetry_address then
			if press("A") then
				result_step = 6
			end
		else
			finish_results(telemetry)
		end
	end
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

	local campaign = read_campaign_telemetry()
	if result_step == 6 and campaign and
			campaign.save_generation >= 1 and
			campaign.save_verified == 1 then
		finish_campaign_save(campaign)
		return
	end
	local telemetry = read_telemetry()
	if not telemetry or telemetry.battle_id ~= 41 then
		if campaign and frame >= PREPARATION_SETTLE_FRAME then
			if preparation_step == 0 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-root",
					"preparation-root.png"
				)
				capture_once(
					"preparation-menu-0",
					"preparation-menu-0.png"
				)
				if press("Down") then
					preparation_step = 1
				end
			elseif preparation_step == 1 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-menu-1",
					"preparation-menu-1.png"
				)
				if press("Down") then
					preparation_step = 2
				end
			elseif preparation_step == 2 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-menu-2",
					"preparation-menu-2.png"
				)
				if press("Down") then
					preparation_step = 3
				end
			elseif preparation_step == 3 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-menu-3",
					"preparation-menu-3.png"
				)
				if press("Up") then
					preparation_step = 4
				end
			elseif preparation_step == 4 and not active_key and
					frame >= next_press_frame and press("A") then
				preparation_step = 5
			elseif preparation_step == 5 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-confirmation-yes",
					"preparation-confirmation-yes.png"
				)
				if press("Down") then
					preparation_step = 6
				end
			elseif preparation_step == 6 and not active_key and
					frame >= next_press_frame then
				capture_once(
					"preparation-confirmation-no",
					"preparation-confirmation-no.png"
				)
				if press("Up") then
					preparation_step = 7
				end
			elseif preparation_step == 7 and not active_key and
					frame >= next_press_frame and press("A") then
				preparation_step = 8
			end
		end
		return
	end
	last_battle_telemetry = telemetry
	record_presentation_trace(telemetry)
	if frame % 60 == 0 then
		emu:screenshot(output_dir .. "/heartbeat.png")
		write_file(
			output_dir .. "/heartbeat.json",
			string.format(
				'{"frame":%d,"scene_frame":%d,"step":%d,"phase":%d,"selected_unit":%d,"cursor_unit_id":%d,"cursor_unit_active":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X"}',
				frame,
				telemetry.scene_frame,
				step,
				telemetry.phase,
				telemetry.selected_unit,
				telemetry.cursor_unit_id,
				telemetry.cursor_unit_active,
				telemetry.last_control_error,
				telemetry.last_player_error,
				emu:readRegister("pc")
			)
		)
	end
	local progress_signature = string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		step,
		result_step,
		telemetry.phase,
		telemetry.selected_action_id,
		telemetry.cursor_x,
		telemetry.cursor_y,
		telemetry.presentation_busy,
		telemetry.presentation_combat_stage,
		telemetry.presentation_combat_stage_frame,
		telemetry.training_action_id
	)
	if progress_signature ~= last_progress_signature then
		last_progress_signature = progress_signature
		write_file(
			output_dir .. "/progress.json",
			string.format(
				'{"frame":%d,"step":%d,"result_step":%d,"phase":%d,"selected_action_id":%d,"cursor_x":%d,"cursor_y":%d,"presentation_busy":%d,"presentation_combat_stage":%d,"presentation_combat_stage_frame":%d,"training_action_id":%d,"training_action_level":%d,"training_points":%d,"last_control_error":%d,"last_player_error":%d}',
				frame,
				step,
				result_step,
				telemetry.phase,
				telemetry.selected_action_id,
				telemetry.cursor_x,
				telemetry.cursor_y,
				telemetry.presentation_busy,
				telemetry.presentation_combat_stage,
				telemetry.presentation_combat_stage_frame,
				telemetry.training_action_id,
				telemetry.training_action_level,
				telemetry.training_points,
				telemetry.last_control_error,
				telemetry.last_player_error
			)
		)
	end
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			if telemetry.script_text_address ~= 0 then
				local dialogue_signature = string.format(
					"%d:%d",
					telemetry.script_selector,
					telemetry.script_command_index
				)
				if dialogue_signature ~=
						last_dialogue_signature then
					last_dialogue_signature =
						dialogue_signature
					dialogue_ready_scene_frame = telemetry.scene_frame + 2
					return
				end
				if telemetry.scene_frame < dialogue_ready_scene_frame then
					return
				end
			end
			if telemetry.script_selector == 2 then
				capture_once(
					"turn-1-complete",
					"turn-1-complete.png"
				)
			else
				capture_once("dialogue", "dialogue.png")
			end
			press("A")
		end
		return
	end
	if (route_round < 4 or
			(route_round == 4 and round_stage == 0)) and
			telemetry.presentation_busy == 1 and
			telemetry.presentation_combat_stage ==
				COMBAT_STAGE_ACTOR_PREP then
		capture_once(
			"enemy-initiated-combat",
			"enemy-initiated-combat.png"
		)
	end
	if route_round == 4 and round_stage >= 4 then
		capture_animation(telemetry)
	end
	if active_key or telemetry.presentation_busy == 1 then
		return
	end
	if continue_results and route_round >= 5 and
			(telemetry.phase == PHASE_OUTCOME or
			 telemetry.phase == PHASE_RESULT or
			 telemetry.phase == PHASE_LEVEL_UP or
			 telemetry.phase == PHASE_TRAINING or
			 telemetry.phase == PHASE_COMPLETE) then
		drive_results(telemetry)
		return
	end
	if route_round >= 5 and
			(telemetry.phase == PHASE_ENEMY_TURN or
			 telemetry.phase == PHASE_OUTCOME) then
		finish(telemetry)
		return
	end

	if route_round == 1 then
		drive_round(telemetry, 1, 4, 10, false)
	elseif route_round == 2 then
		drive_round(telemetry, 2, 4, 7, false)
	elseif route_round == 3 then
		drive_round(telemetry, 3, 5, 6, false)
	elseif route_round == 4 then
		drive_round(telemetry, 4, telemetry.first_active_enemy_x, telemetry.first_active_enemy_y + 1, true)
	end
end)
