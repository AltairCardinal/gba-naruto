local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or tonumber(value:gsub("^0[xX]", ""), 16)
end

local function optional_number(name, fallback)
	local value = os.getenv(name)
	if not value or value == "" then
		return fallback
	end
	return assert(parse_number(value))
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir =
	required_env("MGBA_BATTLE_CAMPAIGN_ROUTE_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_BATTLE_CAMPAIGN_ROUTE_DONE_MARKER")
local battle_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_BATTLE_TELEMETRY_ADDRESS"
)))
local campaign_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_CAMPAIGN_TELEMETRY_ADDRESS"
)))
local complete_stage =
	os.getenv("MGBA_BATTLE_CAMPAIGN_ROUTE_COMPLETE_STAGE") == "1"
capture_ui =
	os.getenv("MGBA_BATTLE_CAMPAIGN_ROUTE_CAPTURE_UI") == "1"
capture_entry_sequence =
	os.getenv(
		"MGBA_BATTLE_CAMPAIGN_ROUTE_CAPTURE_ENTRY_SEQUENCE"
	) == "1"
local scenario_46_rule_probe =
	os.getenv(
		"MGBA_BATTLE_CAMPAIGN_ROUTE_SCENARIO_46_RULE_PROBE"
	) == "1"
scenario_49_sasuke_taijutsu_probe =
	os.getenv(
		"MGBA_BATTLE_CAMPAIGN_ROUTE_SASUKE_TAIJUTSU_PROBE"
	) == "1"
scenario_49_homologous_enemy_duel_probe =
	os.getenv(
		"MGBA_BATTLE_CAMPAIGN_ROUTE_HOMOLOGOUS_ENEMY_DUEL_PROBE"
	) == "1"
local expected_scenario = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_SCENARIO", 42
)
local expected_battle = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_BATTLE", 42
)
local expected_next_scenario = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NEXT_SCENARIO",
	expected_scenario + 1
)
local scenario_43_completion = expected_battle == 43
local scenario_44_completion = expected_battle == 44
local scenario_45_completion = expected_battle == 45
local scenario_46_completion =
	complete_stage and expected_scenario == 46 and
		expected_battle == 9
local scenario_47_completion =
	complete_stage and expected_scenario == 47 and
		expected_battle == 13
local scenario_49_completion =
	complete_stage and expected_scenario == 49 and
		expected_battle == 14
local expected_mission_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_MISSION_EXPERIENCE",
	scenario_45_completion and 150 or
		((scenario_43_completion or scenario_44_completion or
			scenario_46_completion or scenario_47_completion or
			scenario_49_completion) and
			125 or 100)
)
local expected_battle_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_BATTLE_EXPERIENCE",
	scenario_43_completion and 30 or
		(scenario_46_completion and 60 or
		(scenario_47_completion and 75 or
		(scenario_49_completion and 100 or
		((scenario_44_completion or scenario_45_completion) and
			0 or 10))))
)
local expected_round_bonus_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_ROUND_BONUS_EXPERIENCE",
	0
)
local expected_total_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_TOTAL_EXPERIENCE",
	scenario_43_completion and 155 or
		(scenario_44_completion and 125 or
			(scenario_45_completion and 150 or
				(scenario_46_completion and 185 or
					(scenario_47_completion and 200 or
						(scenario_49_completion and 225 or 110)))))
)
local expected_naruto_level = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_LEVEL",
	(scenario_43_completion or scenario_44_completion or
		scenario_45_completion) and 3 or
		(scenario_46_completion and 4 or
			(scenario_47_completion and 5 or
				(scenario_49_completion and 6 or 2)))
)
local expected_naruto_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_EXPERIENCE",
	scenario_43_completion and 0 or
		(scenario_44_completion and 125 or
			(scenario_45_completion and 275 or
				(scenario_46_completion and 180 or
					(scenario_47_completion and 85 or
						(scenario_49_completion and 0 or 110)))))
)
local expected_naruto_training_points = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_TRAINING_POINTS",
	(scenario_43_completion or scenario_44_completion or
		scenario_45_completion) and 2 or
		(scenario_46_completion and 3 or
			(scenario_47_completion and 4 or
				(scenario_49_completion and 5 or 1)))
)
local expected_result_participant_count =
	(scenario_44_completion or scenario_45_completion or
		scenario_46_completion or scenario_47_completion or
		scenario_49_completion) and
		3 or 1
local completion_round_limit =
	scenario_45_completion and 5 or
		(scenario_43_completion and 5 or
			(scenario_44_completion and 4 or 3))

local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_CHAKRA_SELECTION = 4
local PHASE_REST_CONFIRMATION = 5
local PHASE_ACTION_SELECTION = 6
local PHASE_COMBINATION_DECISION = 7
local PHASE_TARGET_SELECTION = 8
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
PHASE_DEFENSE_SELECTION = 11
local PHASE_OUTCOME = 13
local PHASE_RESULT = 14
local PHASE_LEVEL_UP = 15
local PHASE_COMPLETE = 16
local PHASE_SCRIPT_BLOCKED = 18
local PHASE_TRAINING = 19
PHASE_TARGET_CONFIRMATION = 20
PHASE_END_CONFIRMATION = 21
PHASE_TARGET_PREVIEW = 22
local SCRIPT_WAIT_FOR_INPUT = 1
local COMMAND_ABILITY = 1
local COMMAND_DIRECT_ATTACK = 2
local COMMAND_REPLENISH_CHAKRA = 3
local COMMAND_REST = 4
local COMMAND_END_ACTION = 5
local PLAYER_ERROR_ACTION_REJECTED = 7
local ACTION_KIND_ACTIVE = 0
local ACTION_KIND_NINJA_TOOL = 1
local ACTION_CROSS_SHURIKEN = 1
local ACTION_TAIJUTSU = 5
local ACTION_SHADOW_CLONE = 7
local ACTION_SASUKE_FIRE = 16
local EFFECT_DAMAGE = 1
local TARGET_OPPONENT_UNIT = 2
local SIDE_PLAYER = 0
SIDE_ENEMY = 1
local CONTROL_PLAYER = 0
local CONDITION_WIN = 1
local PLAYER_MOVEMENT_BUDGET = 3
local PREPARATION_SETTLE_FRAME = 120
local NO_COORDINATE = 0xFFFFFFFF
local OBJECTIVE_INTERACTION_X = 4
local OBJECTIVE_INTERACTION_Y = 3
local SCENARIO_46_MAP = {
	"################",
	"################",
	"################",
	"#..............#",
	"#..............#",
	"#..............#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#.#####..#####.#",
	"#..............#",
	"#..............#",
	"#..............#",
	"##..########..##",
	"##..########..##",
	"#..............#",
	"#..............#",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"#####......#####",
	"################",
	"################",
	"################",
}
local SCENARIO_47_MAP = {
	"#############",
	"#############",
	"#############",
	"##.........##",
	"#...........#",
	"#...........#",
	"#...#...#...#",
	"#.#.#.#.#.#.#",
	"#.#...#...#.#",
	"#...........#",
	"#..#.#.#.#..#",
	"#...........#",
	"#.#...#...#.#",
	"#.#.#.#.#.#.#",
	"#...#...#...#",
	"#...........#",
	"#...........#",
	"##.........##",
	"#############",
	"#############",
	"#############",
}
local SCENARIO_49_MAP = {
	"###############",
	"###############",
	"###############",
	"##......#....##",
	"#.......#.....#",
	"#.............#",
	"#...#.........#",
	"#...........#.#",
	"#.....#..#....#",
	"#.....#..#....#",
	"###.###.###.###",
	"#.............#",
	"#.............#",
	"#..#..#.......#",
	"#.....#.......#",
	"##...........##",
	"###############",
	"###############",
	"###############",
}
local SCENARIO_49_NARUTO_GUARD = { x = 11, y = 3 }
local SCENARIO_49_SASUKE_GUARD = { x = 12, y = 4 }
SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_1 = { x = 8, y = 6 }
SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_2 = { x = 7, y = 4 }

local keys = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Up = C.GBA_KEY.UP,
}

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local preparation_step = 0
local last_deployment_signature = ""
local last_battle = nil
local result_verified = false
local shadow_clone_verified = false
local objective_verified = false
local cross_shuriken_verified = false
local sasuke_fire_verified = false
local sakura_finisher_verified = false
local scenario_45_equipment_verified = false
local combination_standalone_staged = false
local objective_facing_staged = false
local last_progress_signature = ""
local move_round = -1
local move_unit = -1
local move_enemy_x = -1
local move_enemy_y = -1
local move_candidates = {}
local move_candidate_index = 1
local move_attempt_pending = false
local move_target_distance = -1
local entry_ready_frame = nil
postbattle_task_menu_ready_frame = nil
postbattle_task_menu_capture_step = 0
prebattle_task_menu_root_captured = false
prebattle_task_confirmation_ready_frame = nil
prebattle_task_confirmation_captured = false
local direct_attack_rejected = false
local shadow_clone_transformed = false
local scenario_46_presented_captures = 0
local scenario_46_captures_by_character = { 0, 0, 0 }
local scenario_46_previous_active_units = nil
local scenario_46_capture_character = 0
local scenario_46_move_x = NO_COORDINATE
local scenario_46_move_y = NO_COORDINATE
local scenario_46_target_x = NO_COORDINATE
local scenario_46_target_y = NO_COORDINATE
local scenario_46_replenishing = false
local scenario_46_combination_standalone_staged = false
local scenario_47_move_x = NO_COORDINATE
local scenario_47_move_y = NO_COORDINATE
local scenario_47_target_x = NO_COORDINATE
local scenario_47_target_y = NO_COORDINATE
local scenario_47_clone_x = NO_COORDINATE
local scenario_47_clone_y = NO_COORDINATE
local scenario_47_rest_requested = false
local scenario_47_rest_pending = false
local scenario_47_rest_hp_before = 0
local scenario_47_rest_unit = 0
local scenario_47_rest_verified = false
local scenario_47_shadow_clone_requested = false
local scenario_47_shadow_clone_verified = false
local scenario_47_combination_standalone_staged = false
local scenario_47_previous_enemy_count = nil
local scenario_47_defeated_enemies = 0
local scenario_49_move_x = NO_COORDINATE
local scenario_49_move_y = NO_COORDINATE
local scenario_49_target_x = NO_COORDINATE
local scenario_49_target_y = NO_COORDINATE
local scenario_49_action_id = ACTION_TAIJUTSU
local scenario_49_replenishing = false
local scenario_49_skip_replenish_under_pressure = false
local scenario_49_replenished_sasuke = false
local scenario_49_used_fireball = false
local scenario_49_creating_shadow_clone = false
local scenario_49_shadow_clone_created = false
local scenario_49_combination_followup = false
scenario_49_move_confirmed = false
local scenario_49_combination_standalone_staged = false
local scenario_49_previous_enemy_count = nil
local scenario_49_defeated_enemies = 0
local scenario_49_allied_ai_damaged = false
local scenario_49_allied_ai_survived = false
local scenario_49_transition_index = 0
local scenario_49_last_transition_signature = ""
local scenario_49_training_summary_page = 0
scenario_49_sasuke_taijutsu_target_confirmed = false
scenario_49_sasuke_taijutsu_presentation_started = false
scenario_49_sasuke_taijutsu_presentation_frames = 0
scenario_49_sasuke_taijutsu_max_stage = -1
scenario_49_sasuke_taijutsu_last_captured_stage = -1
scenario_49_sasuke_taijutsu_settle_frame = nil
scenario_49_defense_no_staged = false
captured_sasuke_focus = false
sasuke_focus_ready_frame = nil
captured_enemy_initiated_duel = false
enemy_initiated_duel_ready_frame = nil
scenario_49_homologous_enemy_duel_started = false
scenario_49_homologous_enemy_duel_last_stage = -1
scenario_49_homologous_enemy_duel_stage_count = 0
captured_command_after_move = false
command_after_move_ready_frame = nil
captured_homologous_target_status = false
homologous_target_status_ready_frame = nil
facing_direction_probe_staged = false
captured_ui_phases = {}
ui_phase_ready_frame = {}
captured_scenario_49_training_pages = {}
scenario_49_training_page_ready_frame = {}
scenario_49_move_menu_probe = 0
entry_sequence_ready_frame = nil
entry_sequence_capture_index = 0
assert_address = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_ASSERT_ADDRESS", 0
)

function on_butano_assert()
	if complete then
		return
	end
	local stack_pointer = emu:readRegister("sp")
	local stack_words = {}
	for index = 0, 255 do
		stack_words[#stack_words + 1] = string.format(
			'"0x%08X"',
			emu:read32(stack_pointer + index * 4)
		)
	end
	local payload = string.format(
		'{"observer_frame":%d,"emulator_frame":%d,"assert_address":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","r0":"0x%08X","r1":"0x%08X","r2":"0x%08X","r3":"0x%08X","stack_words":[%s],"status":"assert-hit"}',
		frame,
		emu:currentFrame(),
		assert_address,
		emu:readRegister("pc"),
		emu:readRegister("lr"),
		emu:readRegister("sp"),
		emu:readRegister("r0"),
		emu:readRegister("r1"),
		emu:readRegister("r2"),
		emu:readRegister("r3"),
		table.concat(stack_words, ",")
	)
	write_file(output_dir .. "/assert-hit.json", payload)
	emu:screenshot(output_dir .. "/assert-hit.png")
	assert(emu:saveStateFile(output_dir .. "/assert-hit.ss9"))
	write_file(done_marker_path, payload)
	complete = true
end

if assert_address ~= 0 then
	emu:setBreakpoint(on_butano_assert, assert_address)
end

function capture_ui_phase(battle)
	if not capture_ui then
		return false
	end
	if scenario_49_homologous_enemy_duel_probe and
			scenario_49_homologous_enemy_duel_started and
			battle.presentation_busy == 0 then
		local audit = string.format(
			'{"capture_frame":%d,"battle_id":%d,"round":%d,"captured_stages":%d,"last_control_error":%d,"last_player_error":%d,"status":"homologous-enemy-duel-complete"}',
			frame,
			battle.battle_id,
			battle.round,
			scenario_49_homologous_enemy_duel_stage_count,
			battle.last_control_error,
			battle.last_player_error
		)
		write_file(output_dir .. "/homologous-enemy-duel-audit.json", audit)
		write_file(done_marker_path, audit)
		complete = true
		return true
	end
	if battle.presentation_busy ~= 0 then
		if scenario_49_homologous_enemy_duel_probe and
				battle.current_side == SIDE_ENEMY and
				battle.presentation_combat_stage >= 1 and
				battle.presentation_combat_stage <= 7 then
			scenario_49_homologous_enemy_duel_started = true
			if battle.presentation_combat_stage_frame >= 2 and
					battle.presentation_combat_stage ~=
						scenario_49_homologous_enemy_duel_last_stage then
				local stage = battle.presentation_combat_stage
				scenario_49_homologous_enemy_duel_last_stage = stage
				scenario_49_homologous_enemy_duel_stage_count =
					scenario_49_homologous_enemy_duel_stage_count + 1
				emu:screenshot(
					output_dir .. string.format(
						"/homologous-enemy-duel-stage-%d.png",
						stage
					)
				)
				write_file(
					output_dir .. string.format(
						"/homologous-enemy-duel-stage-%d.json",
						stage
					),
					string.format(
						'{"frame":%d,"round":%d,"stage":%d,"stage_frame":%d,"selected_unit":%d,"selected_character_id":%d,"selected_unit_hp":%d,"selected_unit_max_hp":%d}',
						frame,
						battle.round,
						stage,
						battle.presentation_combat_stage_frame,
						battle.selected_unit,
						battle.selected_character_id,
						battle.selected_unit_hp,
						battle.selected_unit_max_hp
					)
				)
			end
			return true
		end
		if not captured_enemy_initiated_duel and
				battle.current_side == SIDE_ENEMY and
				battle.presentation_combat_stage >= 1 and
				battle.presentation_combat_stage <= 3 then
			if not enemy_initiated_duel_ready_frame then
				enemy_initiated_duel_ready_frame = frame + 2
				return true
			end
			if frame < enemy_initiated_duel_ready_frame then
				return true
			end
			emu:screenshot(
				output_dir .. "/ui-enemy-initiated-duel.png"
			)
			captured_enemy_initiated_duel = true
		end
		return false
	end
	local phase = battle.phase
	if scenario_49_completion and
			phase == PHASE_TRAINING and
			battle.training_detail_page < 6 and
			not captured_scenario_49_training_pages[
				battle.training_detail_page
			] then
		local training_page = battle.training_detail_page
		if not scenario_49_training_page_ready_frame[
				training_page
			] then
			scenario_49_training_page_ready_frame[
				training_page
			] = frame + 2
			return true
		end
		if frame < scenario_49_training_page_ready_frame[
				training_page
			] then
			return true
		end
		emu:screenshot(
			output_dir .. string.format(
				"/ui-training-page-%d.png",
				training_page
			)
		)
		captured_scenario_49_training_pages[
			training_page
		] = true
		return true
	end
	if capture_entry_sequence and
			phase == PHASE_UNIT_SELECTION and
			entry_sequence_capture_index < 32 then
		if not entry_sequence_ready_frame then
			entry_sequence_ready_frame = frame + 2
			return true
		end
		if frame < entry_sequence_ready_frame then
			return true
		end
		emu:screenshot(
			output_dir .. string.format(
				"/ui-phase-1-frame-%02d.png",
				entry_sequence_capture_index
			)
		)
		entry_sequence_capture_index =
			entry_sequence_capture_index + 1
		return true
	end
	if not captured_sasuke_focus and
			battle.selected_character_id == 2 and
			(phase == PHASE_MOVE_SELECTION or
				phase == PHASE_COMMAND_SELECTION) then
		if not sasuke_focus_ready_frame then
			sasuke_focus_ready_frame = frame + 2
			return true
		end
		if frame < sasuke_focus_ready_frame then
			return true
		end
		emu:screenshot(output_dir .. "/ui-sasuke-focus.png")
		captured_sasuke_focus = true
	end
	if not captured_command_after_move and
			battle.battle_id == 14 and
			phase == PHASE_COMMAND_SELECTION and
			(battle.move_preview_x ~= battle.selected_unit_x or
				battle.move_preview_y ~= battle.selected_unit_y) then
		if not command_after_move_ready_frame then
			command_after_move_ready_frame = frame + 2
			return true
		end
		if frame < command_after_move_ready_frame then
			return true
		end
		emu:screenshot(
			output_dir .. "/ui-command-after-move.png"
		)
		write_file(
			output_dir .. "/ui-command-after-move.json",
			string.format(
				'{"frame":%d,"round":%d,"phase":%d,"selected_character_id":%d,"selected_command":%d,"selected_unit_x":%d,"selected_unit_y":%d,"move_preview_x":%d,"move_preview_y":%d,"status":"command-after-move"}',
				frame,
				battle.round,
				phase,
				battle.selected_character_id,
				battle.selected_command,
				battle.selected_unit_x,
				battle.selected_unit_y,
				battle.move_preview_x,
				battle.move_preview_y
			)
		)
		captured_command_after_move = true
	end
	if not captured_homologous_target_status and
			battle.phase == PHASE_TARGET_PREVIEW and
			battle.selected_character_id == 1 and
			battle.selected_action_id == ACTION_TAIJUTSU and
			battle.cursor_unit_hp == 25 and
			battle.cursor_unit_attack == 14 and
			battle.cursor_unit_defense == 6 and
			battle.cursor_unit_agility == 24 then
		if not homologous_target_status_ready_frame then
			homologous_target_status_ready_frame = frame + 8
			return true
		end
		if frame < homologous_target_status_ready_frame then
			return true
		end
		emu:screenshot(
			output_dir .. "/ui-target-status-homologous.png"
		)
		write_file(
			output_dir .. "/ui-target-status-homologous.json",
			string.format(
				'{"frame":%d,"round":%d,"phase":%d,"selected_unit":%d,"selected_character_id":%d,"selected_action_id":%d,"cursor_unit_hp":%d,"cursor_unit_attack":%d,"cursor_unit_defense":%d,"cursor_unit_agility":%d,"status":"homologous-target-status"}',
				frame,
				battle.round,
				battle.phase,
				battle.selected_unit,
				battle.selected_character_id,
				battle.selected_action_id,
				battle.cursor_unit_hp,
				battle.cursor_unit_attack,
				battle.cursor_unit_defense,
				battle.cursor_unit_agility
			)
		)
		captured_homologous_target_status = true
	end
	if phase ~= PHASE_UNIT_SELECTION and
			phase ~= PHASE_MOVE_SELECTION and
			phase ~= PHASE_COMMAND_SELECTION and
			phase ~= PHASE_ACTION_SELECTION and
			phase ~= PHASE_TARGET_SELECTION and
			phase ~= PHASE_TARGET_PREVIEW and
			phase ~= PHASE_TARGET_CONFIRMATION and
			phase ~= PHASE_END_CONFIRMATION and
			phase ~= PHASE_FACING_SELECTION and
			phase ~= PHASE_SCRIPT_BLOCKED and
			phase ~= PHASE_RESULT and
			phase ~= PHASE_LEVEL_UP and
			phase ~= PHASE_TRAINING then
		return false
	end
	if phase == PHASE_SCRIPT_BLOCKED and
			(battle.script_phase ~= SCRIPT_WAIT_FOR_INPUT or
				battle.script_message_window_visible ~= 1) then
		return false
	end
	if captured_ui_phases[phase] then
		return false
	end
	if phase == PHASE_MOVE_SELECTION and
			battle.move_preview_x == battle.selected_unit_x and
			battle.move_preview_y == battle.selected_unit_y then
		return false
	end
	if phase == PHASE_TARGET_SELECTION or
			phase == PHASE_TARGET_PREVIEW or
			phase == PHASE_TARGET_CONFIRMATION then
		if battle.selected_action_target_kind ~=
				TARGET_OPPONENT_UNIT then
			return false
		end
		local cursor_enemy = false
		for _, unit in ipairs(battle.units) do
			if unit.active == 1 and
					unit.side == SIDE_ENEMY and
					unit.x == battle.cursor_x and
					unit.y == battle.cursor_y then
				cursor_enemy = true
				break
			end
		end
		if not cursor_enemy then
			return false
		end
	end
	if phase == PHASE_FACING_SELECTION and
			battle.selected_character_id ~= 2 then
		return false
	end
	if phase == PHASE_FACING_SELECTION and
			not facing_direction_probe_staged then
		if press("Down") then
			facing_direction_probe_staged = true
			ui_phase_ready_frame[phase] = frame + 8
		end
		return true
	end
	if not ui_phase_ready_frame[phase] then
		ui_phase_ready_frame[phase] =
			frame + (phase == PHASE_SCRIPT_BLOCKED and 8 or 2)
		return true
	end
	if frame < ui_phase_ready_frame[phase] then
		return true
	end
	emu:screenshot(
		output_dir .. string.format("/ui-phase-%d.png", phase)
	)
	if phase == PHASE_SCRIPT_BLOCKED then
		write_file(
			output_dir .. "/ui-phase-18.json",
			string.format(
				'{"frame":%d,"script_phase":%d,"script_selector":%d,"script_text_address":%d,"script_message_window_visible":%d,"script_portrait_0_visible":%d,"script_portrait_1_visible":%d,"presentation_busy":%d}',
				frame,
				battle.script_phase,
				battle.script_selector,
				battle.script_text_address,
				battle.script_message_window_visible,
				battle.script_portrait_0_visible,
				battle.script_portrait_1_visible,
				battle.presentation_busy
			)
		)
		assert(
			emu:saveStateFile(output_dir .. "/ui-phase-18.ss9"),
			"failed to save dialogue UI state"
		)
	end
	captured_ui_phases[phase] = true
	return false
end

local function read_campaign_telemetry()
	if emu:read32(campaign_telemetry_address) ~=
			CAMPAIGN_TELEMETRY_MAGIC then
		return nil
	end
	return {
		load_generation =
			emu:read32(campaign_telemetry_address + 4),
		load_used_default =
			emu:read32(campaign_telemetry_address + 12),
		save_generation =
			emu:read32(campaign_telemetry_address + 16),
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
		last_error =
			emu:read32(campaign_telemetry_address + 68),
		owned_tool_1 =
			emu:read32(campaign_telemetry_address + 72),
		scenario_id =
			emu:read32(campaign_telemetry_address + 76),
		route_complete =
			emu:read32(campaign_telemetry_address + 80),
	}
end

local function read_battle_units()
	local units = {}
	for index = 0, 11 do
		local unit = {
			id = index + 1,
			character_id = emu:read32(
				battle_telemetry_address + 420 + index * 4
			),
			active = emu:read32(
				battle_telemetry_address + 468 + index * 4
			),
			x = emu:read32(
				battle_telemetry_address + 516 + index * 4
			),
			y = emu:read32(
				battle_telemetry_address + 564 + index * 4
			),
		}
		unit.hp = emu:read32(
			battle_telemetry_address + 620 + index * 4
		)
		unit.chakra = emu:read32(
			battle_telemetry_address + 668 + index * 4
		)
		unit.side = emu:read32(
			battle_telemetry_address + 716 + index * 4
		)
		unit.control = emu:read32(
			battle_telemetry_address + 764 + index * 4
		)
		units[index + 1] = unit
	end
	return units
end

local function read_battle_telemetry()
	if emu:read32(battle_telemetry_address) ~=
			BATTLE_TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id =
			emu:read32(battle_telemetry_address + 4),
		phase =
			emu:read32(battle_telemetry_address + 8),
		round =
			emu:read32(battle_telemetry_address + 12),
		current_side =
			emu:read32(battle_telemetry_address + 16),
		selected_unit =
			emu:read32(battle_telemetry_address + 20),
		active_units =
			emu:read32(battle_telemetry_address + 24),
		selected_command =
			emu:read32(battle_telemetry_address + 32),
		cursor_x =
			emu:read32(battle_telemetry_address + 48),
		cursor_y =
			emu:read32(battle_telemetry_address + 52),
		last_control_error =
			emu:read32(battle_telemetry_address + 56),
		last_player_error =
			emu:read32(battle_telemetry_address + 60),
		presentation_busy =
			emu:read32(battle_telemetry_address + 68),
		presentation_combat_stage =
			emu:read32(battle_telemetry_address + 364),
		presentation_combat_stage_frame =
			emu:read32(battle_telemetry_address + 368),
		selected_character_id =
			emu:read32(battle_telemetry_address + 72),
		action_count =
			emu:read32(battle_telemetry_address + 76),
		selected_action_id =
			emu:read32(battle_telemetry_address + 84),
		last_resolved_action_id =
			emu:read32(battle_telemetry_address + 92),
		selected_action_kind =
			emu:read32(battle_telemetry_address + 104),
		result_participant_count =
			emu:read32(battle_telemetry_address + 112),
		result_mission_experience =
			emu:read32(battle_telemetry_address + 116),
		result_battle_experience =
			emu:read32(battle_telemetry_address + 120),
		result_round_bonus_experience =
			emu:read32(battle_telemetry_address + 124),
		result_total_experience =
			emu:read32(battle_telemetry_address + 128),
		result_level_before =
			emu:read32(battle_telemetry_address + 132),
		result_level_after =
			emu:read32(battle_telemetry_address + 136),
		result_experience_after =
			emu:read32(battle_telemetry_address + 140),
		battlefield_object_count =
			emu:read32(battle_telemetry_address + 284),
		script_phase =
			emu:read32(battle_telemetry_address + 148),
		script_selector =
			emu:read32(battle_telemetry_address + 152),
		script_command_index =
			emu:read32(battle_telemetry_address + 156),
		script_text_address =
			emu:read32(battle_telemetry_address + 160),
		script_message_window_visible =
			emu:read32(battle_telemetry_address + 164),
		script_portrait_0_visible =
			emu:read32(battle_telemetry_address + 168),
		script_portrait_1_visible =
			emu:read32(battle_telemetry_address + 192),
		training_character_id =
			emu:read32(battle_telemetry_address + 336),
		training_points =
			emu:read32(battle_telemetry_address + 348),
		selected_unit_x =
			emu:read32(battle_telemetry_address + 384),
		selected_unit_y =
			emu:read32(battle_telemetry_address + 388),
		first_active_enemy_x =
			emu:read32(battle_telemetry_address + 392),
		first_active_enemy_y =
			emu:read32(battle_telemetry_address + 396),
		selected_action_effect_code =
			emu:read32(battle_telemetry_address + 400),
		selected_action_target_kind =
			emu:read32(battle_telemetry_address + 404),
		selected_unit_chakra =
			emu:read32(battle_telemetry_address + 408),
		move_preview_x =
			emu:read32(battle_telemetry_address + 412),
		move_preview_y =
			emu:read32(battle_telemetry_address + 416),
		selected_unit_hp =
			emu:read32(battle_telemetry_address + 612),
		selected_unit_max_hp =
			emu:read32(battle_telemetry_address + 616),
		cursor_unit_hp =
			emu:read32(battle_telemetry_address + 328),
		cursor_unit_attack =
			emu:read32(battle_telemetry_address + 308),
		cursor_unit_defense =
			emu:read32(battle_telemetry_address + 312),
		cursor_unit_agility =
			emu:read32(battle_telemetry_address + 316),
		resource_preview_amount =
			emu:read32(battle_telemetry_address + 812),
		resource_preview_maximum_amount =
			emu:read32(battle_telemetry_address + 816),
		condition_outcome =
			emu:read32(battle_telemetry_address + 820),
		training_detail_page =
			emu:read32(battle_telemetry_address + 824),
		units = read_battle_units(),
	}
end

function press(key)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = key
	emu:addKey(assert(keys[key]))
	release_frame = frame + 6
	return true
end

local function drive_scenario_45_preparation()
	if frame < PREPARATION_SETTLE_FRAME then
		return
	end
	local key = nil
	if preparation_step == 0 or preparation_step == 1 then
		key = "Down"
	elseif preparation_step >= 2 and preparation_step <= 4 then
		key = "A"
	elseif preparation_step == 5 then
		key = "B"
	elseif preparation_step == 6 then
		key = "Up"
	elseif preparation_step == 7 or preparation_step == 8 or
			preparation_step == 9 then
		key = "A"
	elseif preparation_step == 10 then
		key = "B"
	elseif preparation_step == 11 then
		key = "Up"
	elseif preparation_step == 12 then
		key = "A"
	end
	if key and press(key) then
		preparation_step = preparation_step + 1
	end
end

local function move_cursor_to(battle, target_x, target_y)
	if battle.cursor_x < target_x then
		press("Right")
	elseif battle.cursor_x > target_x then
		press("Left")
	elseif battle.cursor_y < target_y then
		press("Down")
	elseif battle.cursor_y > target_y then
		press("Up")
	else
		return true
	end
	return false
end

local function drive_deployment(battle)
	if battle.phase ~= PHASE_DEPLOY_UNIT and
			battle.phase ~= PHASE_DEPLOY_START then
		return false
	end
	local signature = string.format(
		"%d:%d", battle.phase, battle.selected_unit
	)
	if signature ~= last_deployment_signature and
			press("A") then
		last_deployment_signature = signature
	end
	return true
end

local function write_progress(campaign, battle)
	local signature = string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		campaign.scenario_id,
		battle and battle.battle_id or -1,
		battle and battle.phase or -1,
		battle and battle.round or -1,
		battle and battle.cursor_x or -1,
		battle and battle.cursor_y or -1,
		battle and battle.selected_command or -1,
		battle and battle.selected_action_id or -1,
		battle and battle.presentation_busy or -1,
		result_verified and 1 or 0,
		battle and battle.selected_unit_x or -1,
		battle and battle.selected_unit_y or -1,
		battle and battle.first_active_enemy_x or -1,
		battle and battle.first_active_enemy_y or -1,
		battle and battle.last_control_error or -1,
		battle and battle.last_player_error or -1,
		move_target_distance,
		battle and battle.script_phase or -1,
		battle and battle.selected_unit_hp or -1,
		battle and battle.selected_unit_max_hp or -1,
		scenario_47_rest_pending and 1 or 0
	)
	if signature == last_progress_signature then
		return
	end
	last_progress_signature = signature
	write_file(
			output_dir .. "/progress.json",
			string.format(
				'{"frame":%d,"scenario_id":%d,"battle_id":%d,"phase":%d,"script_phase":%d,"round":%d,"cursor_x":%d,"cursor_y":%d,"selected_command":%d,"selected_action_id":%d,"presentation_busy":%d,"selected_unit":%d,"selected_unit_x":%d,"selected_unit_y":%d,"selected_unit_hp":%d,"selected_unit_max_hp":%d,"first_active_enemy_x":%d,"first_active_enemy_y":%d,"last_control_error":%d,"last_player_error":%d,"move_candidate_index":%d,"move_target_distance":%d,"result_participant_count":%d,"result_mission_experience":%d,"result_battle_experience":%d,"result_round_bonus_experience":%d,"result_total_experience":%d,"result_level_before":%d,"result_level_after":%d,"result_experience_after":%d,"training_points":%d,"result_verified":%d,"scenario_47_rest_pending":%d}',
			frame,
				campaign.scenario_id,
				battle and battle.battle_id or -1,
				battle and battle.phase or -1,
				battle and battle.script_phase or -1,
				battle and battle.round or -1,
			battle and battle.cursor_x or -1,
			battle and battle.cursor_y or -1,
			battle and battle.selected_command or -1,
				battle and battle.selected_action_id or -1,
				battle and battle.presentation_busy or -1,
				battle and battle.selected_unit or -1,
				battle and battle.selected_unit_x or -1,
				battle and battle.selected_unit_y or -1,
				battle and battle.selected_unit_hp or -1,
				battle and battle.selected_unit_max_hp or -1,
			battle and battle.first_active_enemy_x or -1,
			battle and battle.first_active_enemy_y or -1,
			battle and battle.last_control_error or -1,
			battle and battle.last_player_error or -1,
			move_candidate_index,
			move_target_distance,
			battle and battle.result_participant_count or -1,
			battle and battle.result_mission_experience or -1,
			battle and battle.result_battle_experience or -1,
				battle and battle.result_round_bonus_experience or -1,
				battle and battle.result_total_experience or -1,
				battle and battle.result_level_before or -1,
				battle and battle.result_level_after or -1,
				battle and battle.result_experience_after or -1,
				battle and battle.training_points or -1,
				result_verified and 1 or 0,
				scenario_47_rest_pending and 1 or 0
		)
	)
	collectgarbage("step", 64)
end

local function finish_entry(campaign, battle)
	assert(campaign.scenario_id == expected_scenario)
	assert(campaign.route_complete == 0)
	assert(campaign.last_error == 0)
	assert(campaign.load_generation >= 1)
	assert(campaign.load_used_default == 0)
	assert(battle.battle_id == expected_battle)
	assert(battle.phase == PHASE_UNIT_SELECTION)
	assert(battle.last_control_error == 0)
	assert(battle.last_player_error == 0)
	emu:screenshot(output_dir .. "/battle-entry.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scenario_id":%d,"battle_id":%d,"phase":%d,"round":%d,"active_units":%d,"selected_character_id":%d,"load_generation":%d,"load_used_default":%d,"save_generation":%d,"save_verified":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"campaign-route-battle-entry"}',
			frame,
			campaign.scenario_id,
			battle.battle_id,
			battle.phase,
			battle.round,
			battle.active_units,
			battle.selected_character_id,
			campaign.load_generation,
			campaign.load_used_default,
			campaign.save_generation,
			campaign.save_verified,
			battle.last_control_error,
			battle.last_player_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
	)
	write_file(
		done_marker_path,
		string.format(
			'{"capture_frame":%d,"scenario_id":%d,"battle_id":%d,"status":"campaign-route-battle-entry"}',
			frame,
			campaign.scenario_id,
			battle.battle_id
		)
	)
	complete = true
end

local function finish_scenario_46_rule_probe(campaign, battle)
	assert(expected_scenario == 46)
	assert(expected_battle == 9)
	assert(campaign.scenario_id == 46)
	assert(campaign.route_complete == 0)
	assert(campaign.last_error == 0)
	assert(campaign.load_generation >= 1)
	assert(campaign.load_used_default == 0)
	assert(battle.battle_id == 9)
	assert(battle.round == 1)
	assert(battle.active_units == 8)
	assert(battle.selected_character_id == 1)
	assert(battle.phase == PHASE_ACTION_SELECTION)
	assert(battle.selected_action_kind == ACTION_KIND_ACTIVE)
	assert(battle.selected_action_id == ACTION_SHADOW_CLONE)
	assert(
		battle.selected_action_effect_code == EFFECT_DAMAGE
	)
	assert(
		battle.selected_action_target_kind ==
			TARGET_OPPONENT_UNIT
	)
	assert(direct_attack_rejected)
	assert(shadow_clone_transformed)
	assert(battle.last_control_error == 0)
	assert(battle.last_player_error == 0)
	emu:screenshot(
		output_dir .. "/shadow-clone-capture-action.png"
	)
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scenario_id":%d,"battle_id":%d,"phase":%d,"round":%d,"active_units":%d,"selected_character_id":%d,"selected_command":%d,"selected_action_id":%d,"selected_action_kind":%d,"selected_action_effect_code":%d,"selected_action_target_kind":%d,"direct_attack_rejected":%d,"shadow_clone_transformed":%d,"load_generation":%d,"load_used_default":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"scenario-46-rule-probe"}',
			frame,
			campaign.scenario_id,
			battle.battle_id,
			battle.phase,
			battle.round,
			battle.active_units,
			battle.selected_character_id,
			battle.selected_command,
			battle.selected_action_id,
			battle.selected_action_kind,
			battle.selected_action_effect_code,
			battle.selected_action_target_kind,
			direct_attack_rejected and 1 or 0,
			shadow_clone_transformed and 1 or 0,
			campaign.load_generation,
			campaign.load_used_default,
			battle.last_control_error,
			battle.last_player_error,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
	)
	write_file(
		done_marker_path,
		string.format(
			'{"capture_frame":%d,"scenario_id":46,"battle_id":9,"status":"scenario-46-rule-probe"}',
			frame
		)
	)
	complete = true
end

local function drive_scenario_46_rule_probe(campaign, battle)
	assert(expected_scenario == 46)
	assert(expected_battle == 9)
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if battle.presentation_busy == 1 then
		return
	end
	if battle.phase == PHASE_UNIT_SELECTION then
		assert(battle.selected_character_id == 1)
		press("A")
	elseif battle.phase == PHASE_MOVE_SELECTION then
		press("A")
	elseif battle.phase == PHASE_COMMAND_SELECTION then
		if not direct_attack_rejected then
			if battle.selected_command ~=
					COMMAND_DIRECT_ATTACK then
				press("Down")
			elseif battle.last_player_error ==
					PLAYER_ERROR_ACTION_REJECTED then
				direct_attack_rejected = true
				emu:screenshot(
					output_dir ..
						"/direct-attack-rejected.png"
				)
			else
				press("A")
			end
		elseif battle.selected_command ~= COMMAND_ABILITY then
			press("Up")
		else
			press("A")
		end
	elseif battle.phase == PHASE_CHAKRA_SELECTION then
		press("A")
	elseif battle.phase == PHASE_ACTION_SELECTION then
		if battle.selected_action_id ~= ACTION_SHADOW_CLONE or
				battle.selected_action_kind ~=
					ACTION_KIND_ACTIVE then
			press("Down")
		elseif battle.selected_action_effect_code ==
					EFFECT_DAMAGE and
				battle.selected_action_target_kind ==
					TARGET_OPPONENT_UNIT then
			shadow_clone_transformed = true
			finish_scenario_46_rule_probe(
				campaign, battle
			)
		else
			assert(
				false,
				"scenario 46 did not transform shadow clone"
			)
		end
	else
		assert(false, "unexpected scenario 46 probe phase")
	end
end

local function scenario_46_distance(
	left_x, left_y, right_x, right_y
)
	return math.abs(left_x - right_x) +
		math.abs(left_y - right_y)
end

local function scenario_46_capture_count()
	return scenario_46_presented_captures
end

local function scenario_46_designated_character()
	local capture_count = scenario_46_capture_count()
	if capture_count < 2 then
		return 2
	elseif capture_count < 4 then
		return 1
	end
	return 3
end

local function scenario_46_active_unit(
	battle, character_id
)
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and
				unit.character_id == character_id then
			return unit
		end
	end
	return nil
end

local function scenario_46_closest_cat(
	battle, origin_x, origin_y
)
	local result = nil
	local best_distance = 16 * 32
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.character_id == 41 then
			local distance = scenario_46_distance(
				origin_x, origin_y, unit.x, unit.y
			)
			if not result or distance < best_distance then
				result = unit
				best_distance = distance
			end
		end
	end
	return result
end

local function scenario_46_player_can_enter(x, y)
	if x < 0 or x >= 16 or y < 0 or y >= 32 then
		return false
	end
	return SCENARIO_46_MAP[y + 1]:sub(x + 1, x + 1) == "."
end

local function scenario_46_occupied(
	battle, x, y, actor_character
)
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.x == x and unit.y == y and
				unit.character_id ~= actor_character then
			return true
		end
	end
	return false
end

local function scenario_46_planned_destination(
	battle,
	actor_character,
	origin_x,
	origin_y,
	target_x,
	target_y,
	target_distance
)
	local function point_index(x, y)
		return y * 16 + x
	end
	local function index_point(index)
		return index % 16, math.floor(index / 16)
	end

	local parents = {}
	local costs = {}
	local queue = {}
	local start = point_index(origin_x, origin_y)
	parents[start] = -1
	costs[start] = 0
	queue[1] = start
	local queue_begin = 1
	local found = nil
	local directions = {
		{ -1, 0 },
		{ 0, -1 },
		{ 1, 0 },
		{ 0, 1 },
	}
	while queue_begin <= #queue do
		local current = queue[queue_begin]
		queue_begin = queue_begin + 1
		local x, y = index_point(current)
		if scenario_46_distance(
				x, y, target_x, target_y
			) == target_distance then
			found = current
			break
		end
		for _, direction in ipairs(directions) do
			local next_x = x + direction[1]
			local next_y = y + direction[2]
			local next_index = point_index(next_x, next_y)
			if scenario_46_player_can_enter(
					next_x, next_y
				) and
					not scenario_46_occupied(
						battle,
						next_x,
						next_y,
						actor_character
					) and
					parents[next_index] == nil then
				parents[next_index] = current
				costs[next_index] = costs[current] + 1
				queue[#queue + 1] = next_index
			end
		end
	end
	if not found then
		return origin_x, origin_y
	end
	local selected = found
	while costs[selected] > PLAYER_MOVEMENT_BUDGET do
		selected = parents[selected]
	end
	return index_point(selected)
end

local function scenario_46_prepare_plan(battle)
	local designated_character =
		scenario_46_designated_character()
	local actor_character = battle.selected_character_id
	local capture_chakra_cost =
		designated_character == 2 and 2 or
			(designated_character == 1 and 3 or 0)
	scenario_46_replenishing =
		actor_character == designated_character and
			battle.selected_unit_chakra < capture_chakra_cost
	if scenario_46_replenishing then
		scenario_46_move_x = battle.selected_unit_x
		scenario_46_move_y = battle.selected_unit_y
		scenario_46_target_x = NO_COORDINATE
		scenario_46_target_y = NO_COORDINATE
		return
	end

	local designated_unit = assert(
		scenario_46_active_unit(
			battle, designated_character
		)
	)
	local target = assert(
		scenario_46_closest_cat(
			battle, designated_unit.x, designated_unit.y
		)
	)
	scenario_46_target_x = target.x
	scenario_46_target_y = target.y
	local movement_target_x = target.x
	local movement_target_y = target.y
	local target_distance = 1
	local capture_count = scenario_46_capture_count()
	if capture_count >= 3 and target.y >= 22 then
		if actor_character == designated_character and
				(battle.selected_unit_x ~= 8 or
					battle.selected_unit_y ~= 27) then
			movement_target_x = 8
			movement_target_y = 27
			target_distance = 0
		elseif actor_character ~= designated_character then
			local first_blocker =
				designated_character == 1 and
					actor_character == 2 or
				designated_character ~= 1 and
					actor_character == 1
			movement_target_x = 10
			movement_target_y =
				first_blocker and 27 or 26
			target_distance = 0
		end
	elseif capture_count >= 4 and target.y <= 13 then
		if actor_character == 1 then
			movement_target_x = 14
			movement_target_y =
				target.y < 13 and target.y + 1 or 14
			target_distance = 0
		elseif actor_character == 2 then
			movement_target_x = 13
			movement_target_y = 4
			target_distance = 0
		end
	end
	scenario_46_move_x, scenario_46_move_y =
		scenario_46_planned_destination(
			battle,
			actor_character,
			battle.selected_unit_x,
			battle.selected_unit_y,
			movement_target_x,
			movement_target_y,
			target_distance
		)
end

local function scenario_46_drive_completion(battle)
	if battle.phase ~= PHASE_COMBINATION_DECISION then
		scenario_46_combination_standalone_staged = false
	end
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if battle.presentation_busy == 1 then
		return
	end
	if battle.phase == PHASE_UNIT_SELECTION then
		scenario_46_prepare_plan(battle)
		press("A")
	elseif battle.phase == PHASE_MOVE_SELECTION then
		if move_cursor_to(
				battle,
				scenario_46_move_x,
				scenario_46_move_y
			) then
			press("A")
		end
	elseif battle.phase == PHASE_COMMAND_SELECTION then
		local designated_character =
			scenario_46_designated_character()
		local adjacent_target =
			scenario_46_target_x ~= NO_COORDINATE and
			scenario_46_distance(
				battle.move_preview_x,
				battle.move_preview_y,
				scenario_46_target_x,
				scenario_46_target_y
			) == 1
		local expected_command = COMMAND_END_ACTION
		if scenario_46_replenishing then
			expected_command = COMMAND_REPLENISH_CHAKRA
		elseif battle.selected_character_id ==
					designated_character and
				adjacent_target then
			expected_command = COMMAND_ABILITY
		end
		if battle.selected_command ~= expected_command then
			press("Down")
		else
			if expected_command == COMMAND_ABILITY then
				scenario_46_capture_character =
					battle.selected_character_id
			end
			press("A")
		end
	elseif battle.phase == PHASE_CHAKRA_SELECTION then
		press("A")
	elseif battle.phase == PHASE_ACTION_SELECTION then
		local expected_action =
			battle.selected_character_id == 2 and
				ACTION_SASUKE_FIRE or
			(battle.selected_character_id == 1 and
				ACTION_SHADOW_CLONE or ACTION_TAIJUTSU)
		if battle.selected_action_id ~= expected_action or
				battle.selected_action_kind ~=
					ACTION_KIND_ACTIVE then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_COMBINATION_DECISION then
		assert(battle.selected_character_id == 2)
		if not scenario_46_combination_standalone_staged then
			if press("Down") then
				scenario_46_combination_standalone_staged =
					true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_SELECTION then
		assert(scenario_46_target_x ~= NO_COORDINATE)
		if move_cursor_to(
				battle,
				scenario_46_target_x,
				scenario_46_target_y
		) then
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_PREVIEW then
		press("A")
	elseif battle.phase == PHASE_FACING_SELECTION or
			battle.phase == PHASE_DEFENSE_DECISION then
		press("A")
	elseif battle.phase == PHASE_OUTCOME then
		assert(scenario_46_presented_captures == 5)
		press("A")
	elseif battle.phase == PHASE_RESULT then
		assert(battle.result_participant_count == 3)
		assert(
			battle.result_mission_experience ==
				expected_mission_experience
		)
		assert(
			battle.result_battle_experience ==
				expected_battle_experience
		)
		assert(
			battle.result_round_bonus_experience ==
				expected_round_bonus_experience
		)
		assert(
			battle.result_total_experience ==
				expected_total_experience
		)
		result_verified = true
		press("A")
	elseif battle.phase == PHASE_LEVEL_UP then
		press("A")
	elseif battle.phase == PHASE_TRAINING then
		assert(battle.training_character_id == 1)
		assert(
			battle.training_points ==
				expected_naruto_training_points
		)
		press("B")
	elseif battle.phase == PHASE_COMPLETE then
		assert(result_verified)
		press("A")
	end
end

local function scenario_47_distance(
	left_x, left_y, right_x, right_y
)
	return math.abs(left_x - right_x) +
		math.abs(left_y - right_y)
end

local function scenario_47_active_enemy_count(battle)
	local count = 0
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.character_id == 33 then
			count = count + 1
		end
	end
	return count
end

local function scenario_47_closest_enemy(
	battle, origin_x, origin_y
)
	local result = nil
	local best_distance = 13 * 21
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.character_id == 33 then
			local distance = scenario_47_distance(
				origin_x, origin_y, unit.x, unit.y
			)
			if not result or distance < best_distance then
				result = unit
				best_distance = distance
			end
		end
	end
	return result
end

local function scenario_47_player_can_enter(x, y)
	if x < 0 or x >= 13 or y < 0 or y >= 21 then
		return false
	end
	return SCENARIO_47_MAP[y + 1]:sub(x + 1, x + 1) == "."
end

local function scenario_47_occupied(
	battle, x, y, actor_id
)
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.id ~= actor_id and
				unit.x == x and unit.y == y then
			return true
		end
	end
	return false
end

local function scenario_47_planned_destination(
	battle,
	actor_id,
	origin_x,
	origin_y,
	target_x,
	target_y,
	target_distance
)
	local function point_index(x, y)
		return y * 13 + x
	end
	local function index_point(index)
		return index % 13, math.floor(index / 13)
	end

	local parents = {}
	local costs = {}
	local queue = {}
	local start = point_index(origin_x, origin_y)
	parents[start] = -1
	costs[start] = 0
	queue[1] = start
	local queue_begin = 1
	local found = nil
	local directions = {
		{ -1, 0 },
		{ 0, -1 },
		{ 1, 0 },
		{ 0, 1 },
	}
	while queue_begin <= #queue do
		local current = queue[queue_begin]
		queue_begin = queue_begin + 1
		local x, y = index_point(current)
		if scenario_47_distance(
				x, y, target_x, target_y
			) == target_distance then
			found = current
			break
		end
		for _, direction in ipairs(directions) do
			local next_x = x + direction[1]
			local next_y = y + direction[2]
			local next_index = point_index(next_x, next_y)
			if scenario_47_player_can_enter(
					next_x, next_y
				) and
					not scenario_47_occupied(
						battle,
						next_x,
						next_y,
						actor_id
					) and
					parents[next_index] == nil then
				parents[next_index] = current
				costs[next_index] = costs[current] + 1
				queue[#queue + 1] = next_index
			end
		end
	end
	if not found then
		return origin_x, origin_y
	end
	local selected = found
	while costs[selected] > PLAYER_MOVEMENT_BUDGET do
		selected = parents[selected]
	end
	return index_point(selected)
end

local function scenario_47_prepare_plan(battle)
	local actor = assert(battle.units[battle.selected_unit])
	assert(actor.active == 1)
	assert(actor.character_id == battle.selected_character_id)
	local target = assert(
		scenario_47_closest_enemy(
			battle, actor.x, actor.y
		)
	)
	scenario_47_target_x = target.x
	scenario_47_target_y = target.y
	scenario_47_rest_requested =
		not scenario_47_rest_verified and battle.round >= 4 and
			battle.selected_unit_hp <
				battle.selected_unit_max_hp
	if scenario_47_rest_requested then
		scenario_47_move_x = actor.x
		scenario_47_move_y = actor.y
		return
	end
	scenario_47_move_x, scenario_47_move_y =
		scenario_47_planned_destination(
			battle,
			actor.id,
			actor.x,
			actor.y,
			target.x,
			target.y,
			1
		)
end

local function scenario_47_prepare_clone_target(battle)
	local directions = {
		{ -1, 0 },
		{ 0, -1 },
		{ 1, 0 },
		{ 0, 1 },
	}
	for _, direction in ipairs(directions) do
		local x = battle.move_preview_x + direction[1]
		local y = battle.move_preview_y + direction[2]
		if scenario_47_player_can_enter(x, y) and
				not scenario_47_occupied(
					battle, x, y, battle.selected_unit
				) then
			scenario_47_clone_x = x
			scenario_47_clone_y = y
			return
		end
	end
	assert(false, "no legal scenario 47 clone target")
end

local function scenario_47_drive_completion(battle)
	if battle.phase ~= PHASE_COMBINATION_DECISION then
		scenario_47_combination_standalone_staged = false
	end
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if battle.presentation_busy == 1 then
		return
	end
	if battle.phase == PHASE_UNIT_SELECTION then
		scenario_47_prepare_plan(battle)
		press("A")
	elseif battle.phase == PHASE_MOVE_SELECTION then
		if move_cursor_to(
				battle,
				scenario_47_move_x,
				scenario_47_move_y
			) then
			press("A")
		end
	elseif battle.phase == PHASE_COMMAND_SELECTION then
		scenario_47_shadow_clone_requested =
			not scenario_47_shadow_clone_verified and
				battle.round >= 6 and
				battle.selected_character_id == 1 and
				battle.selected_unit_chakra >= 3
		local adjacent_target =
			scenario_47_distance(
				battle.move_preview_x,
				battle.move_preview_y,
				scenario_47_target_x,
				scenario_47_target_y
			) == 1
		local expected_command = COMMAND_END_ACTION
		if scenario_47_rest_requested then
			expected_command = COMMAND_REST
		elseif scenario_47_shadow_clone_requested or
				adjacent_target then
			expected_command = COMMAND_ABILITY
		end
		if battle.selected_command ~= expected_command then
			press("Down")
		else
			if scenario_47_shadow_clone_requested then
				scenario_47_prepare_clone_target(battle)
			end
			press("A")
		end
	elseif battle.phase == PHASE_REST_CONFIRMATION then
		assert(scenario_47_rest_requested)
		scenario_47_rest_pending = true
		scenario_47_rest_hp_before = battle.selected_unit_hp
		scenario_47_rest_unit = battle.selected_unit
		press("A")
	elseif battle.phase == PHASE_ACTION_SELECTION then
		local expected_action =
			scenario_47_shadow_clone_requested and
				ACTION_SHADOW_CLONE or ACTION_TAIJUTSU
		if battle.selected_action_id ~= expected_action or
				battle.selected_action_kind ~=
					ACTION_KIND_ACTIVE then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_COMBINATION_DECISION then
		if not scenario_47_combination_standalone_staged then
			if press("Down") then
				scenario_47_combination_standalone_staged =
					true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_SELECTION then
		local target_x = scenario_47_target_x
		local target_y = scenario_47_target_y
		if scenario_47_shadow_clone_requested then
			target_x = scenario_47_clone_x
			target_y = scenario_47_clone_y
		end
		if move_cursor_to(battle, target_x, target_y) then
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_PREVIEW then
		press("A")
	elseif battle.phase == PHASE_FACING_SELECTION or
			battle.phase == PHASE_DEFENSE_DECISION then
		press("A")
	elseif battle.phase == PHASE_OUTCOME then
		assert(scenario_47_defeated_enemies == 5)
		assert(scenario_47_shadow_clone_verified)
		press("A")
	elseif battle.phase == PHASE_RESULT then
		assert(battle.result_participant_count == 3)
		assert(
			battle.result_mission_experience ==
				expected_mission_experience
		)
		assert(
			battle.result_battle_experience ==
				expected_battle_experience
		)
		assert(
			battle.result_round_bonus_experience ==
				expected_round_bonus_experience
		)
		assert(
			battle.result_total_experience ==
				expected_total_experience
		)
		result_verified = true
		press("A")
	elseif battle.phase == PHASE_LEVEL_UP then
		press("A")
	elseif battle.phase == PHASE_TRAINING then
		assert(battle.training_character_id == 1)
		assert(
			battle.training_points ==
				expected_naruto_training_points
		)
		press("B")
	elseif battle.phase == PHASE_COMPLETE then
		assert(result_verified)
		press("A")
	end
end

local function scenario_49_distance(
	left_x, left_y, right_x, right_y
)
	return math.abs(left_x - right_x) +
		math.abs(left_y - right_y)
end

local function scenario_49_active_enemy_count(battle)
	local count = 0
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.side ~= SIDE_PLAYER then
			count = count + 1
		end
	end
	return count
end

local function scenario_49_weakest_enemy(
	battle, actor, action_range
)
	local result = nil
	local best_hp = 0
	local best_distance = 0
	local best_reachable = false
	for _, candidate in ipairs(battle.units) do
		if candidate.active == 1 and
				candidate.side ~= SIDE_PLAYER then
			local candidate_distance = scenario_49_distance(
				actor.x,
				actor.y,
				candidate.x,
				candidate.y
			)
			local candidate_reachable =
				candidate_distance <=
					PLAYER_MOVEMENT_BUDGET + action_range
			if not result or
					(candidate_reachable and
						not best_reachable) or
					(candidate_reachable == best_reachable and
						((candidate_reachable and
							(candidate.hp < best_hp or
								(candidate.hp == best_hp and
									candidate_distance <
										best_distance))) or
							(not candidate_reachable and
								(candidate_distance <
										best_distance or
									(candidate_distance ==
											best_distance and
										candidate.hp <
											best_hp))))) then
				result = candidate
				best_hp = candidate.hp
				best_distance = candidate_distance
				best_reachable = candidate_reachable
			end
		end
	end
	return result
end

local function scenario_49_priority_enemy(
	battle, actor, action_range
)
	if actor.id >= 10 then
		local flank_target = battle.units[7]
		if flank_target and flank_target.active == 1 and
				flank_target.side ~= SIDE_PLAYER then
			return flank_target
		end
	end
	local mission_threat = battle.units[5]
	if mission_threat and mission_threat.active == 1 and
			mission_threat.side ~= SIDE_PLAYER and
			actor.character_id == 3 and battle.round >= 2 then
		return mission_threat
	end
	return nil
end

local function scenario_49_enemy_in_range(
	battle, origin_x, origin_y, action_range
)
	local result = nil
	local best_hp = 0
	local best_distance = 0
	for _, candidate in ipairs(battle.units) do
		if candidate.active == 1 and
				candidate.side ~= SIDE_PLAYER then
			local distance = scenario_49_distance(
				origin_x,
				origin_y,
				candidate.x,
				candidate.y
			)
			if distance <= action_range and
					(not result or candidate.hp < best_hp or
						(candidate.hp == best_hp and
							distance < best_distance)) then
				result = candidate
				best_hp = candidate.hp
				best_distance = distance
			end
		end
	end
	return result
end

local function scenario_49_player_can_enter(x, y)
	if x < 0 or x >= 15 or y < 0 or y >= 19 then
		return false
	end
	return SCENARIO_49_MAP[y + 1]:sub(x + 1, x + 1) == "."
end

local function scenario_49_occupied(
	battle, x, y, actor_id
)
	for _, unit in ipairs(battle.units) do
		if unit.active == 1 and unit.id ~= actor_id and
				unit.x == x and unit.y == y then
			return true
		end
	end
	return false
end

local function scenario_49_planned_destination(
	battle,
	actor_id,
	origin_x,
	origin_y,
	target_x,
	target_y,
	target_distance
)
	local function point_index(x, y)
		return y * 15 + x
	end
	local function index_point(index)
		return index % 15, math.floor(index / 15)
	end

	local parents = {}
	local costs = {}
	local queue = {}
	local start = point_index(origin_x, origin_y)
	parents[start] = -1
	costs[start] = 0
	queue[1] = start
	local queue_begin = 1
	local found = nil
	local directions = {
		{ -1, 0 },
		{ 0, -1 },
		{ 1, 0 },
		{ 0, 1 },
	}
	while queue_begin <= #queue do
		local current = queue[queue_begin]
		queue_begin = queue_begin + 1
		local x, y = index_point(current)
		if scenario_49_distance(
				x, y, target_x, target_y
			) == target_distance then
			found = current
			break
		end
		for _, direction in ipairs(directions) do
			local next_x = x + direction[1]
			local next_y = y + direction[2]
			local next_index = point_index(next_x, next_y)
			if scenario_49_player_can_enter(
					next_x, next_y
				) and
					not scenario_49_occupied(
						battle,
						next_x,
						next_y,
						actor_id
					) and
					parents[next_index] == nil then
				parents[next_index] = current
				costs[next_index] = costs[current] + 1
				queue[#queue + 1] = next_index
			end
		end
	end
	if not found then
		return origin_x, origin_y
	end
	local selected = found
	while costs[selected] > PLAYER_MOVEMENT_BUDGET do
		selected = parents[selected]
	end
	return index_point(selected)
end

function scenario_49_move_cursor_to(
	battle, target_x, target_y
)
	if battle.cursor_x == target_x and
			battle.cursor_y == target_y then
		return true
	end

	local function point_index(x, y)
		return y * 15 + x
	end
	local function index_point(index)
		return index % 15, math.floor(index / 15)
	end
	local directions = {
		{ -1, 0, "Left" },
		{ 0, -1, "Up" },
		{ 1, 0, "Right" },
		{ 0, 1, "Down" },
	}
	local start = point_index(
		battle.cursor_x, battle.cursor_y
	)
	local target = point_index(target_x, target_y)
	local parents = {}
	local parent_keys = {}
	local queue = { start }
	parents[start] = -1
	local queue_begin = 1
	while queue_begin <= #queue and parents[target] == nil do
		local current = queue[queue_begin]
		queue_begin = queue_begin + 1
		local x, y = index_point(current)
		for _, direction in ipairs(directions) do
			local next_x = x + direction[1]
			local next_y = y + direction[2]
			local next_index = point_index(next_x, next_y)
			if scenario_49_player_can_enter(
					next_x, next_y
				) and
					not scenario_49_occupied(
						battle,
						next_x,
						next_y,
						battle.selected_unit
					) and
					parents[next_index] == nil then
				parents[next_index] = current
				parent_keys[next_index] = direction[3]
				queue[#queue + 1] = next_index
			end
		end
	end
	assert(parents[target] ~= nil, "move cursor target unreachable")
	local step = target
	while parents[step] ~= start do
		step = parents[step]
	end
	press(parent_keys[step])
	return false
end

local function scenario_49_prepare_plan(battle)
	local actor = assert(battle.units[battle.selected_unit])
	assert(actor.active == 1)
	assert(actor.side == SIDE_PLAYER)
	assert(actor.control == CONTROL_PLAYER)
	assert(actor.character_id == battle.selected_character_id)
	if scenario_49_sasuke_taijutsu_probe then
		scenario_49_creating_shadow_clone = false
		scenario_49_replenishing = false
		scenario_49_action_id = ACTION_TAIJUTSU
		if actor.character_id ~= 2 then
			scenario_49_move_x = actor.x
			scenario_49_move_y = actor.y
			scenario_49_target_x = actor.x
			scenario_49_target_y = actor.y
			return
		end
		local target = assert(
			scenario_49_weakest_enemy(battle, actor, 1)
		)
		scenario_49_target_x = target.x
		scenario_49_target_y = target.y
		scenario_49_move_x, scenario_49_move_y =
			scenario_49_planned_destination(
				battle,
				actor.id,
				actor.x,
				actor.y,
				target.x,
				target.y,
				1
			)
		return
	end
	scenario_49_creating_shadow_clone =
		actor.id == 1 and actor.character_id == 1 and
			actor.chakra >= 3 and
			not scenario_49_shadow_clone_created
	scenario_49_skip_replenish_under_pressure =
		actor.character_id == 2 and
			scenario_49_active_enemy_count(battle) <= 3
	scenario_49_replenishing =
		actor.character_id == 2 and actor.chakra < 2 and
			not scenario_49_replenished_sasuke and
			not scenario_49_skip_replenish_under_pressure
	if scenario_49_replenishing then
		scenario_49_move_x = actor.x
		scenario_49_move_y = actor.y
		scenario_49_target_x = actor.x
		scenario_49_target_y = actor.y
		return
	end

	scenario_49_action_id =
		scenario_49_creating_shadow_clone and
			ACTION_SHADOW_CLONE or
			(actor.character_id == 2 and actor.chakra >= 2 and
				ACTION_SASUKE_FIRE or ACTION_TAIJUTSU)
	local action_range =
		scenario_49_action_id == ACTION_SASUKE_FIRE and 2 or 1
	local guard = nil
	if scenario_49_active_enemy_count(battle) > 2 then
		if actor.character_id == 1 then
			guard = SCENARIO_49_NARUTO_GUARD
		elseif actor.character_id == 2 then
			guard = SCENARIO_49_SASUKE_GUARD
		end
	end
	if guard then
		scenario_49_move_x, scenario_49_move_y =
			scenario_49_planned_destination(
				battle,
				actor.id,
				actor.x,
				actor.y,
				guard.x,
				guard.y,
				0
			)
		scenario_49_target_x = guard.x
		scenario_49_target_y = guard.y
		if scenario_49_creating_shadow_clone then
			scenario_49_target_x = 10
			scenario_49_target_y = 3
		end
		return
	end
	local target = scenario_49_priority_enemy(
		battle, actor, action_range
	)
	if not target then
		target = scenario_49_weakest_enemy(
			battle, actor, action_range
		)
	end
	assert(target)
	scenario_49_target_x = target.x
	scenario_49_target_y = target.y
	scenario_49_move_x, scenario_49_move_y =
		scenario_49_planned_destination(
			battle,
			actor.id,
			actor.x,
			actor.y,
			target.x,
			target.y,
			action_range
		)
end

local function scenario_49_write_transition(battle)
	local unit_state = {}
	for _, unit in ipairs(battle.units) do
		unit_state[#unit_state + 1] = string.format(
			"%d:%d:%d:%d:%d:%d:%d:%d",
			unit.id,
			unit.character_id,
			unit.active,
			unit.hp,
			unit.chakra,
			unit.side,
			unit.x,
			unit.y
		)
	end
	local signature = string.format(
		"%d:%d:%d:%d:%d:%d:%s",
		battle.round,
		battle.phase,
		battle.selected_unit,
		battle.selected_command,
		battle.selected_action_id,
		battle.condition_outcome,
		table.concat(unit_state, "|")
	)
	if signature == scenario_49_last_transition_signature then
		return
	end
	scenario_49_last_transition_signature = signature
	scenario_49_transition_index =
		scenario_49_transition_index + 1
	write_file(
		output_dir .. "/" .. string.format(
			"scenario_49-transition-%04d.json",
			scenario_49_transition_index
		),
		string.format(
			'{"frame":%d,"round":%d,"phase":%d,"selected_unit":%d,"selected_character_id":%d,"selected_command":%d,"selected_action_id":%d,"resource_preview_amount":%d,"resource_preview_maximum_amount":%d,"condition_outcome":%d,"units":"%s"}',
			frame,
			battle.round,
			battle.phase,
			battle.selected_unit,
			battle.selected_character_id,
			battle.selected_command,
			battle.selected_action_id,
			battle.resource_preview_amount,
			battle.resource_preview_maximum_amount,
			battle.condition_outcome,
			table.concat(unit_state, "|")
		)
	)
end

local function scenario_49_update_evidence(battle)
	scenario_49_write_transition(battle)
	local enemy_count = scenario_49_active_enemy_count(battle)
	if scenario_49_previous_enemy_count and
			enemy_count < scenario_49_previous_enemy_count then
		local defeated =
			scenario_49_previous_enemy_count - enemy_count
		scenario_49_defeated_enemies =
			scenario_49_defeated_enemies + defeated
		write_file(
			output_dir .. string.format(
				"/scenario_49-defeat-%d.json",
				scenario_49_defeated_enemies
			),
			string.format(
				'{"frame":%d,"round":%d,"defeated":%d,"remaining_enemies":%d}',
				frame,
				battle.round,
				defeated,
				enemy_count
			)
		)
	end
	scenario_49_previous_enemy_count = enemy_count
	local escort = battle.units[4]
	if escort and escort.active == 1 and escort.hp < 40 then
		scenario_49_allied_ai_damaged = true
	end
	if battle.phase == PHASE_OUTCOME then
		scenario_49_allied_ai_survived =
			escort ~= nil and escort.active == 1 and
				escort.hp > 0
	end
	if battle.last_resolved_action_id ==
			ACTION_SHADOW_CLONE then
		for index = 10, 12 do
			local clone = battle.units[index]
			if clone.active == 1 and
					clone.character_id == 1 then
				scenario_49_shadow_clone_created = true
				break
			end
		end
	end
end

function finish_scenario_49_sasuke_taijutsu_probe(battle)
	assert(scenario_49_sasuke_taijutsu_target_confirmed)
	assert(scenario_49_sasuke_taijutsu_presentation_started)
	assert(scenario_49_sasuke_taijutsu_presentation_frames > 0)
	assert(scenario_49_sasuke_taijutsu_max_stage >= 7)
	assert(battle.battle_id == 14)
	assert(battle.selected_character_id == 2)
	assert(battle.last_resolved_action_id == ACTION_TAIJUTSU)
	assert(battle.last_control_error == 0)
	assert(battle.last_player_error == 0)
	emu:screenshot(
		output_dir .. "/scenario-49-sasuke-taijutsu-complete.png"
	)
	local audit = string.format(
		'{"capture_frame":%d,"scenario_id":49,"battle_id":%d,"phase":%d,"round":%d,"selected_character_id":%d,"last_resolved_action_id":%d,"presentation_frames":%d,"max_combat_stage":%d,"last_control_error":%d,"last_player_error":%d,"status":"scenario-49-sasuke-taijutsu-complete"}',
		frame,
		battle.battle_id,
		battle.phase,
		battle.round,
		battle.selected_character_id,
		battle.last_resolved_action_id,
		scenario_49_sasuke_taijutsu_presentation_frames,
		scenario_49_sasuke_taijutsu_max_stage,
		battle.last_control_error,
		battle.last_player_error
	)
	write_file(
		output_dir .. "/scenario-49-sasuke-taijutsu-audit.json",
		audit
	)
	write_file(done_marker_path, audit)
	complete = true
end

local function scenario_49_drive_completion(battle)
	if scenario_49_homologous_enemy_duel_probe then
		if battle.phase ~= PHASE_DEFENSE_DECISION then
			scenario_49_defense_no_staged = false
		end
		if battle.phase == PHASE_SCRIPT_BLOCKED then
			if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
				press("A")
			end
		elseif battle.presentation_busy == 1 then
			return
		elseif battle.phase == PHASE_UNIT_SELECTION or
				battle.phase == PHASE_END_CONFIRMATION or
				battle.phase == PHASE_FACING_SELECTION then
			press("A")
		elseif battle.phase == PHASE_MOVE_SELECTION then
			local destination = nil
			if battle.selected_character_id == 1 then
				destination =
					battle.round == 1 and
						SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_1 or
						SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_2
			end
			if not destination or
					scenario_49_move_cursor_to(
						battle,
						destination.x,
						destination.y
					) then
				press("A")
			end
		elseif battle.phase == PHASE_COMMAND_SELECTION then
			local expected_command = COMMAND_END_ACTION
			if battle.selected_command ~= expected_command then
				press("Down")
			else
				press("A")
			end
		elseif battle.phase == PHASE_DEFENSE_DECISION then
			if not scenario_49_defense_no_staged then
				if press("Down") then
					scenario_49_defense_no_staged = true
				end
			else
				press("A")
			end
		elseif battle.phase == PHASE_DEFENSE_SELECTION then
			press("B")
		end
		return
	end
	if scenario_49_sasuke_taijutsu_target_confirmed then
		if battle.presentation_busy == 1 then
			scenario_49_sasuke_taijutsu_presentation_started = true
			scenario_49_sasuke_taijutsu_presentation_frames =
				scenario_49_sasuke_taijutsu_presentation_frames + 1
			if battle.presentation_combat_stage < 8 then
				scenario_49_sasuke_taijutsu_max_stage =
					math.max(
						scenario_49_sasuke_taijutsu_max_stage,
						battle.presentation_combat_stage
					)
				if battle.presentation_combat_stage ~=
						scenario_49_sasuke_taijutsu_last_captured_stage then
					scenario_49_sasuke_taijutsu_last_captured_stage =
						battle.presentation_combat_stage
					emu:screenshot(
						output_dir .. string.format(
							"/scenario-49-sasuke-taijutsu-stage-%d.png",
							battle.presentation_combat_stage
						)
					)
				end
			end
			return
		elseif scenario_49_sasuke_taijutsu_presentation_started then
			if not scenario_49_sasuke_taijutsu_settle_frame then
				scenario_49_sasuke_taijutsu_settle_frame = frame + 2
			elseif frame >=
					scenario_49_sasuke_taijutsu_settle_frame then
				finish_scenario_49_sasuke_taijutsu_probe(battle)
			end
			return
		end
	end
	if battle.phase ~= PHASE_COMBINATION_DECISION then
		scenario_49_combination_standalone_staged = false
	end
	if battle.phase ~= PHASE_DEFENSE_DECISION then
		scenario_49_defense_no_staged = false
	end
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if battle.presentation_busy == 1 then
		return
	end
	if battle.phase == PHASE_UNIT_SELECTION then
		scenario_49_combination_followup = false
		scenario_49_move_confirmed = false
		scenario_49_prepare_plan(battle)
		press("A")
	elseif battle.phase == PHASE_MOVE_SELECTION then
		if not scenario_49_sasuke_taijutsu_probe and
				scenario_49_move_menu_probe == 0 then
			if press("A") then
				scenario_49_move_menu_probe = 1
				scenario_49_move_confirmed = true
			end
			return
		elseif scenario_49_move_menu_probe == 2 then
			scenario_49_move_menu_probe = 3
			write_file(
				output_dir .. "/scenario_49-move-menu.json",
				string.format(
					'{"frame":%d,"round":%d,"phase":%d,"move_preview_x":%d,"move_preview_y":%d,"status":"move-menu-reopened"}',
					frame,
					battle.round,
					battle.phase,
					battle.move_preview_x,
					battle.move_preview_y
				)
			)
		end
		if scenario_49_move_cursor_to(
				battle,
				scenario_49_move_x,
				scenario_49_move_y
			) then
			if press("A") then scenario_49_move_confirmed = true end
		end
	elseif battle.phase == PHASE_COMMAND_SELECTION then
		if scenario_49_move_menu_probe == 1 then
			if press("B") then
				scenario_49_move_menu_probe = 2
				scenario_49_move_confirmed = false
			end
			return
		elseif scenario_49_move_menu_probe == 2 or
				(not scenario_49_move_confirmed and not scenario_49_replenishing) then
			if battle.selected_command ~= 0 then press("Up") else press("A") end
			return
		end
		local expected_command = COMMAND_END_ACTION
		if scenario_49_sasuke_taijutsu_probe and
				battle.selected_character_id ~= 2 then
			expected_command = COMMAND_END_ACTION
		elseif scenario_49_replenishing then
			expected_command = COMMAND_REPLENISH_CHAKRA
		elseif scenario_49_creating_shadow_clone then
			expected_command = COMMAND_ABILITY
		else
			local target = scenario_49_enemy_in_range(
				battle,
				battle.move_preview_x,
				battle.move_preview_y,
				(scenario_49_action_id ==
					ACTION_SASUKE_FIRE and 2 or 1)
			)
			if target then
				scenario_49_target_x = target.x
				scenario_49_target_y = target.y
				expected_command = COMMAND_ABILITY
			end
		end
		if battle.selected_command ~= expected_command then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_CHAKRA_SELECTION then
		assert(scenario_49_replenishing)
		if battle.resource_preview_amount <
				battle.resource_preview_maximum_amount then
			press("Down")
		else
			scenario_49_replenished_sasuke = true
			press("A")
		end
	elseif battle.phase == PHASE_ACTION_SELECTION then
		local expected_action =
			scenario_49_combination_followup and
				ACTION_TAIJUTSU or scenario_49_action_id
		if battle.selected_action_id ~= expected_action or
				battle.selected_action_kind ~=
					ACTION_KIND_ACTIVE then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_COMBINATION_DECISION then
		local scenario_49_combination_target_adjacent =
			scenario_49_distance(
				battle.move_preview_x,
				battle.move_preview_y,
				scenario_49_target_x,
				scenario_49_target_y
			) == 1
		if scenario_49_action_id == ACTION_SASUKE_FIRE and
				scenario_49_combination_target_adjacent then
			if press("A") then
				scenario_49_combination_followup = true
			end
		elseif not scenario_49_combination_standalone_staged then
			if press("Down") then
				scenario_49_combination_standalone_staged = true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_SELECTION then
		if move_cursor_to(
				battle,
				scenario_49_target_x,
				scenario_49_target_y
			) then
			if scenario_49_action_id ==
					ACTION_SASUKE_FIRE then
				scenario_49_used_fireball = true
			end
			if press("A") then
				scenario_49_combination_followup = false
			end
		end
	elseif battle.phase == PHASE_TARGET_PREVIEW then
		press("A")
	elseif battle.phase == PHASE_TARGET_CONFIRMATION then
		if scenario_49_sasuke_taijutsu_probe then
			assert(battle.selected_character_id == 2)
			assert(
				battle.selected_action_id ==
					ACTION_TAIJUTSU
			)
			scenario_49_sasuke_taijutsu_target_confirmed = true
		end
		press("A")
	elseif battle.phase == PHASE_END_CONFIRMATION or
			battle.phase == PHASE_FACING_SELECTION then
		press("A")
	elseif battle.phase == PHASE_DEFENSE_DECISION then
		if not scenario_49_defense_no_staged then
			if press("Down") then
				scenario_49_defense_no_staged = true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_DEFENSE_SELECTION then
		press("B")
	elseif battle.phase == PHASE_OUTCOME then
		assert(battle.condition_outcome == CONDITION_WIN)
		assert(scenario_49_defeated_enemies == 5)
		assert(scenario_49_used_fireball)
		assert(scenario_49_shadow_clone_created)
		assert(scenario_49_allied_ai_damaged)
		assert(scenario_49_allied_ai_survived)
		assert(battle.round <= 16)
		press("A")
	elseif battle.phase == PHASE_RESULT then
		assert(
			battle.result_participant_count ==
				expected_result_participant_count
		)
		assert(
			battle.result_mission_experience ==
				expected_mission_experience
		)
		assert(
			battle.result_battle_experience ==
				expected_battle_experience
		)
		assert(
			battle.result_round_bonus_experience ==
				expected_round_bonus_experience
		)
		assert(
			battle.result_total_experience ==
				expected_total_experience
		)
		result_verified = true
		press("A")
	elseif battle.phase == PHASE_LEVEL_UP then
		press("A")
	elseif battle.phase == PHASE_TRAINING then
		assert(battle.training_character_id == 1)
		assert(
			battle.training_points ==
				expected_naruto_training_points
		)
		if scenario_49_training_summary_page < 6 then
			if press("A") then
				scenario_49_training_summary_page =
					scenario_49_training_summary_page + 1
			end
		end
	elseif battle.phase == PHASE_COMPLETE then
		assert(result_verified)
		press("A")
	end
end

local function scenario_45_attack_range(battle)
	if not scenario_45_completion then
		return nil
	end
	if not cross_shuriken_verified then
		if battle.selected_character_id == 1 then
			return 3
		end
		return nil
	end
	if not sasuke_fire_verified then
		if battle.selected_character_id == 2 then
			return 2
		end
		return nil
	end
	if battle.round > completion_round_limit and
			battle.selected_character_id == 3 then
		return 1
	end
	return nil
end

local function reset_move_candidates(battle)
	move_candidates = {}
	move_candidate_index = 1
	move_attempt_pending = false
	move_round = battle.round
	move_unit = battle.selected_unit
	move_enemy_x = battle.first_active_enemy_x
	move_enemy_y = battle.first_active_enemy_y
	local objective_phase =
		scenario_44_completion and
			battle.first_active_enemy_x == NO_COORDINATE
	if objective_phase then
		for distance = 0, 9 + 22 - 1 do
			for y = 0, 22 - 1 do
				for x = 0, 9 - 1 do
					local candidate_distance =
						math.abs(x - OBJECTIVE_INTERACTION_X) +
						math.abs(y - OBJECTIVE_INTERACTION_Y)
					local candidate_origin_distance =
						math.abs(x - battle.selected_unit_x) +
						math.abs(y - battle.selected_unit_y)
					if candidate_distance == distance and
							candidate_origin_distance <=
								PLAYER_MOVEMENT_BUDGET then
						table.insert(
							move_candidates,
							{
								x = x,
								y = y,
								distance = distance,
							}
						)
					end
				end
			end
		end
	elseif expected_battle == 42 and battle.round == 1 then
		move_candidates[1] = {
			x = 4,
			y = 7,
			distance =
				math.abs(4 - battle.first_active_enemy_x) +
				math.abs(7 - battle.first_active_enemy_y),
		}
	elseif scenario_45_completion then
		local attack_range = scenario_45_attack_range(battle)
		if not attack_range then
			move_candidates[1] = {
				x = battle.selected_unit_x,
				y = battle.selected_unit_y,
				distance =
					math.abs(
						battle.selected_unit_x -
							battle.first_active_enemy_x
					) +
					math.abs(
						battle.selected_unit_y -
							battle.first_active_enemy_y
					),
			}
		else
			for distance = 1, 9 + 22 - 1 do
				for y = 0, 22 - 1 do
					for x = 0, 9 - 1 do
						local candidate_distance =
							math.abs(
								x -
									battle.first_active_enemy_x
							) +
							math.abs(
								y -
									battle.first_active_enemy_y
							)
						local candidate_origin_distance =
							math.abs(
								x -
									battle.selected_unit_x
							) +
							math.abs(
								y -
									battle.selected_unit_y
							)
						if candidate_distance == distance and
								candidate_origin_distance <=
									PLAYER_MOVEMENT_BUDGET then
							table.insert(
								move_candidates,
								{
									x = x,
									y = y,
									distance = distance,
								}
							)
						end
					end
				end
			end
		end
	elseif battle.round <= completion_round_limit then
		move_candidates[1] = {
			x = battle.selected_unit_x,
			y = battle.selected_unit_y,
			distance =
				math.abs(
					battle.selected_unit_x -
						battle.first_active_enemy_x
				) +
				math.abs(
					battle.selected_unit_y -
						battle.first_active_enemy_y
				),
		}
	else
		for distance = 1, 9 + 22 - 1 do
			for y = 0, 22 - 1 do
				for x = 0, 9 - 1 do
					local candidate_distance =
						math.abs(x - battle.first_active_enemy_x) +
						math.abs(y - battle.first_active_enemy_y)
					local candidate_origin_distance =
						math.abs(x - battle.selected_unit_x) +
						math.abs(y - battle.selected_unit_y)
					if candidate_distance == distance and
							candidate_origin_distance <=
								PLAYER_MOVEMENT_BUDGET then
						table.insert(
							move_candidates,
							{
								x = x,
								y = y,
								distance = distance,
							}
						)
					end
				end
			end
		end
	end
end

local function stage_move_target(battle)
	if move_round ~= battle.round or
			move_unit ~= battle.selected_unit or
			move_enemy_x ~= battle.first_active_enemy_x or
			move_enemy_y ~= battle.first_active_enemy_y then
		reset_move_candidates(battle)
	end
	if move_attempt_pending and not active_key then
		if battle.last_player_error ~= 0 or
				battle.last_control_error ~= 0 then
			move_candidate_index = move_candidate_index + 1
			move_attempt_pending = false
		end
	end
	local candidate = move_candidates[move_candidate_index]
	assert(candidate, "no reachable movement candidate")
	move_target_distance = candidate.distance
	return candidate.x, candidate.y
end

local function confirm_stage_move()
	if press("A") then
		move_attempt_pending = true
	end
end

local function drive_stage_completion(battle)
	if battle.phase ~= PHASE_FACING_SELECTION then
		objective_facing_staged = false
	end
	if battle.phase ~= PHASE_COMBINATION_DECISION then
		combination_standalone_staged = false
	end
	if battle.phase == PHASE_SCRIPT_BLOCKED then
		if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if battle.presentation_busy == 1 then
		return
	end
	if battle.phase == PHASE_UNIT_SELECTION then
		press("A")
	elseif battle.phase == PHASE_MOVE_SELECTION then
		assert(battle.selected_unit_x ~= 0xFFFFFFFF)
		assert(battle.selected_unit_y ~= 0xFFFFFFFF)
		local target_x, target_y = stage_move_target(battle)
		if move_cursor_to(battle, target_x, target_y) then
			confirm_stage_move()
		end
	elseif battle.phase == PHASE_COMMAND_SELECTION then
		local objective_phase =
			scenario_44_completion and
				battle.first_active_enemy_x == NO_COORDINATE
		local shadow_clone_turn =
			scenario_43_completion and
				battle.round == 1 and
				not shadow_clone_verified
		local scenario_45_range =
			scenario_45_attack_range(battle)
		local scenario_45_attack =
			scenario_45_range and
				move_target_distance <= scenario_45_range
		local generic_attack =
			battle.round > completion_round_limit and
				move_target_distance == 1
		local expected_command =
			(not objective_phase and
				(shadow_clone_turn or
				(scenario_45_completion and
					scenario_45_attack) or
				(not scenario_45_completion and
					generic_attack))) and
				COMMAND_ABILITY or
				COMMAND_END_ACTION
		if battle.selected_command ~= expected_command then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_ACTION_SELECTION then
		assert(battle.action_count >= 2)
		local expected_action = ACTION_TAIJUTSU
		local expected_kind = ACTION_KIND_ACTIVE
		if scenario_43_completion and
				battle.round == 1 and
				not shadow_clone_verified then
			expected_action = ACTION_SHADOW_CLONE
		elseif scenario_45_completion and
				not cross_shuriken_verified then
			expected_action = ACTION_CROSS_SHURIKEN
			expected_kind = ACTION_KIND_NINJA_TOOL
		elseif scenario_45_completion and
				not sasuke_fire_verified then
			expected_action = ACTION_SASUKE_FIRE
		end
		if battle.selected_action_id ~= expected_action or
				battle.selected_action_kind ~= expected_kind then
			press("Down")
		else
			press("A")
		end
	elseif battle.phase == PHASE_COMBINATION_DECISION then
		assert(scenario_45_completion)
		assert(not sasuke_fire_verified)
		assert(battle.selected_character_id == 2)
		if not combination_standalone_staged then
			if press("Down") then
				combination_standalone_staged = true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_SELECTION then
		local target_x = battle.first_active_enemy_x
		local target_y = battle.first_active_enemy_y
		if scenario_43_completion and
				battle.round == 1 and
				not shadow_clone_verified then
			target_x = battle.selected_unit_x
			target_y = battle.selected_unit_y - 1
		else
			assert(target_x ~= 0xFFFFFFFF)
			assert(target_y ~= 0xFFFFFFFF)
		end
		if move_cursor_to(battle, target_x, target_y) then
			press("A")
		end
	elseif battle.phase == PHASE_TARGET_PREVIEW or
			battle.phase == PHASE_TARGET_CONFIRMATION or
			battle.phase == PHASE_END_CONFIRMATION then
		press("A")
	elseif battle.phase == PHASE_FACING_SELECTION then
		local objective_phase =
			scenario_44_completion and
				battle.first_active_enemy_x == NO_COORDINATE
		if objective_phase and not objective_facing_staged then
			if press("Down") then
				objective_facing_staged = true
			end
		else
			press("A")
		end
	elseif battle.phase == PHASE_DEFENSE_DECISION then
		press("A")
	elseif battle.phase == PHASE_OUTCOME then
		if scenario_44_completion then
			assert(battle.first_active_enemy_x == NO_COORDINATE)
			assert(battle.battlefield_object_count == 0)
			objective_verified = true
		end
		if scenario_45_completion then
			assert(cross_shuriken_verified)
			assert(sasuke_fire_verified)
			assert(battle.selected_character_id == 3)
			assert(
				battle.last_resolved_action_id ==
					ACTION_TAIJUTSU
			)
			sakura_finisher_verified = true
		end
		press("A")
	elseif battle.phase == PHASE_RESULT then
		assert(
			battle.result_participant_count ==
				expected_result_participant_count
		)
		assert(
			battle.result_mission_experience ==
				expected_mission_experience
		)
		assert(
			battle.result_battle_experience ==
				expected_battle_experience
		)
		assert(
			battle.result_round_bonus_experience ==
				expected_round_bonus_experience
		)
		assert(
			battle.result_total_experience ==
				expected_total_experience
		)
		result_verified = true
		press("A")
	elseif battle.phase == PHASE_LEVEL_UP then
		press("A")
	elseif battle.phase == PHASE_TRAINING then
		assert(battle.training_character_id == 1)
		assert(
			battle.training_points ==
				expected_naruto_training_points
		)
		press("B")
	elseif battle.phase == PHASE_COMPLETE then
		assert(result_verified)
		press("A")
	end
end

local function finish_stage(campaign)
	local battle = assert(last_battle)
	assert(result_verified)
	assert(campaign.scenario_id == expected_next_scenario)
	assert(campaign.route_complete == 0)
	assert(campaign.save_generation >= 1)
	assert(campaign.save_verified == 1)
	assert(campaign.naruto_level == expected_naruto_level)
	assert(
		campaign.naruto_experience ==
			expected_naruto_experience
	)
	assert(
		campaign.naruto_training_points ==
			expected_naruto_training_points
	)
	assert(campaign.naruto_action_8_level == 0)
	assert(campaign.last_error == 0)
	assert(battle.battle_id == expected_battle)
	assert(
		battle.result_mission_experience ==
			expected_mission_experience
	)
	assert(
		battle.result_battle_experience ==
			expected_battle_experience
	)
	assert(
		battle.result_round_bonus_experience ==
			expected_round_bonus_experience
	)
	assert(
		battle.result_total_experience ==
			expected_total_experience
	)
	if scenario_43_completion then
		assert(shadow_clone_verified)
	end
	if scenario_44_completion then
		assert(objective_verified)
		assert(battle.battlefield_object_count == 0)
	end
	if scenario_45_completion then
		assert(scenario_45_equipment_verified)
		assert(cross_shuriken_verified)
		assert(sasuke_fire_verified)
		assert(sakura_finisher_verified)
		assert(campaign.naruto_tool_0 == 0)
		assert(campaign.owned_tool_1 == 0)
	end
	if scenario_46_completion then
		assert(scenario_46_presented_captures == 5)
		assert(scenario_46_captures_by_character[1] == 2)
		assert(scenario_46_captures_by_character[2] == 2)
		assert(scenario_46_captures_by_character[3] == 1)
	end
	if scenario_47_completion then
		assert(scenario_47_defeated_enemies == 5)
		assert(scenario_47_shadow_clone_verified)
	end
	if scenario_49_completion then
		assert(scenario_49_move_menu_probe == 3)
		assert(scenario_49_defeated_enemies == 5)
		assert(scenario_49_used_fireball)
		assert(scenario_49_shadow_clone_created)
		assert(scenario_49_allied_ai_damaged)
		assert(scenario_49_allied_ai_survived)
		assert(battle.condition_outcome == CONDITION_WIN)
		write_file(
			output_dir .. "/scenario_49-audit.json",
			string.format(
				'{"capture_frame":%d,"scenario_id":%d,"battle_id":%d,"round":%d,"condition_outcome":%d,"scenario_49_defeated_enemies":%d,"scenario_49_replenished_sasuke":%d,"scenario_49_shadow_clone_created":%d,"scenario_49_used_fireball":%d,"scenario_49_allied_ai_damaged":%d,"scenario_49_allied_ai_survived":%d,"transition_count":%d}',
				frame,
				campaign.scenario_id,
				battle.battle_id,
				battle.round,
				battle.condition_outcome,
				scenario_49_defeated_enemies,
				scenario_49_replenished_sasuke and 1 or 0,
				scenario_49_shadow_clone_created and 1 or 0,
				scenario_49_used_fireball and 1 or 0,
				scenario_49_allied_ai_damaged and 1 or 0,
				scenario_49_allied_ai_survived and 1 or 0,
				scenario_49_transition_index
			)
		)
	end
	assert(battle.last_resolved_action_id == ACTION_TAIJUTSU)
	assert(battle.last_control_error == 0)
	assert(battle.last_player_error == 0)
	emu:screenshot(output_dir .. "/postbattle-task-menu-root.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scenario_id":%d,"battle_id":%d,"phase":%d,"round":%d,"active_units":%d,"last_resolved_action_id":%d,"shadow_clone_verified":%d,"objective_verified":%d,"cross_shuriken_verified":%d,"sasuke_fire_verified":%d,"sakura_finisher_verified":%d,"battlefield_object_count":%d,"result_mission_experience":%d,"result_battle_experience":%d,"result_round_bonus_experience":%d,"result_total_experience":%d,"save_generation":%d,"save_verified":%d,"naruto_level":%d,"naruto_experience":%d,"naruto_training_points":%d,"naruto_action_8_level":%d,"naruto_tool_0":%d,"owned_tool_1":%d,"last_control_error":%d,"last_player_error":%d,"scenario_46_presented_captures":%d,"scenario_47_defeated_enemies":%d,"scenario_47_rest_verified":%d,"scenario_47_shadow_clone_verified":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"campaign-route-stage-complete"}',
			frame,
			campaign.scenario_id,
			battle.battle_id,
			battle.phase,
			battle.round,
			battle.active_units,
			battle.last_resolved_action_id,
			shadow_clone_verified and 1 or 0,
			objective_verified and 1 or 0,
			cross_shuriken_verified and 1 or 0,
			sasuke_fire_verified and 1 or 0,
			sakura_finisher_verified and 1 or 0,
			battle.battlefield_object_count,
			battle.result_mission_experience,
			battle.result_battle_experience,
			battle.result_round_bonus_experience,
			battle.result_total_experience,
			campaign.save_generation,
			campaign.save_verified,
			campaign.naruto_level,
			campaign.naruto_experience,
			campaign.naruto_training_points,
			campaign.naruto_action_8_level,
			campaign.naruto_tool_0,
			campaign.owned_tool_1,
			battle.last_control_error,
			battle.last_player_error,
			scenario_46_presented_captures,
			scenario_47_defeated_enemies,
			scenario_47_rest_verified and 1 or 0,
			scenario_47_shadow_clone_verified and 1 or 0,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
	)
	write_file(
		done_marker_path,
		string.format(
			'{"capture_frame":%d,"scenario_id":%d,"status":"campaign-route-stage-complete"}',
			frame,
			campaign.scenario_id
		)
	)
	complete = true
end

local function drive_frame()
	if complete then
		return
	end
	frame = frame + 1
	assert(
		frame < ((scenario_46_completion or
			scenario_47_completion or
			scenario_49_completion or
			scenario_49_sasuke_taijutsu_probe) and
				120000 or 20000),
		"campaign route timed out"
	)
	if active_key and frame >= release_frame then
		emu:clearKey(assert(keys[active_key]))
		active_key = nil
		next_press_frame = frame + 3
	end

	local campaign = read_campaign_telemetry()
	if not campaign then
		return
	end
	local battle = read_battle_telemetry()
	if battle and capture_ui_phase(battle) then
		return
	end
	if scenario_46_completion and battle and
			battle.battle_id == 9 and
			battle.active_units >= 3 and
			battle.active_units <= 8 then
		if scenario_46_previous_active_units and
				battle.active_units <
					scenario_46_previous_active_units then
			local captured =
				scenario_46_previous_active_units -
					battle.active_units
			assert(
				scenario_46_capture_character >= 1 and
					scenario_46_capture_character <= 3
			)
			scenario_46_presented_captures =
				scenario_46_presented_captures + captured
			scenario_46_captures_by_character[
				scenario_46_capture_character
			] =
				scenario_46_captures_by_character[
					scenario_46_capture_character
				] + captured
			local capture_file_name = string.format(
				"capture-%d.json",
				scenario_46_presented_captures
			)
			write_file(
				output_dir .. "/" .. capture_file_name,
				string.format(
					'{"frame":%d,"round":%d,"captured":%d,"capturing_character_id":%d,"remaining_active_units":%d}',
					frame,
					battle.round,
					captured,
					scenario_46_capture_character,
					battle.active_units
				)
			)
		end
		scenario_46_previous_active_units =
			battle.active_units
	end
	if scenario_47_completion and battle and
			battle.battle_id == 13 then
		local enemy_count =
			scenario_47_active_enemy_count(battle)
		if scenario_47_previous_enemy_count and
				enemy_count <
					scenario_47_previous_enemy_count then
			local defeated =
				scenario_47_previous_enemy_count -
					enemy_count
			scenario_47_defeated_enemies =
				scenario_47_defeated_enemies + defeated
			write_file(
				output_dir .. string.format(
					"/defeat-%d.json",
					scenario_47_defeated_enemies
				),
				string.format(
					'{"frame":%d,"round":%d,"defeated":%d,"remaining_enemies":%d}',
					frame,
					battle.round,
					defeated,
					enemy_count
				)
			)
		end
		scenario_47_previous_enemy_count = enemy_count
		if scenario_47_rest_pending and
				battle.selected_unit ==
					scenario_47_rest_unit and
				battle.selected_unit_hp >
					scenario_47_rest_hp_before then
			scenario_47_rest_verified = true
			scenario_47_rest_pending = false
		end
		if battle.last_resolved_action_id ==
				ACTION_SHADOW_CLONE then
			for index = 9, 12 do
				local unit = battle.units[index]
				if unit.active == 1 and
						unit.character_id == 1 then
					scenario_47_shadow_clone_verified = true
					break
				end
			end
		end
	end
	if scenario_49_completion and battle and
			battle.battle_id == 14 then
		scenario_49_update_evidence(battle)
	end
	if battle and
			battle.last_resolved_action_id == ACTION_SHADOW_CLONE and
			battle.active_units >= 5 then
		shadow_clone_verified = true
	end
	if scenario_45_completion and battle and
			battle.battle_id == expected_battle then
		if not scenario_45_equipment_verified then
			assert(preparation_step == 13)
			assert(campaign.naruto_tool_0 == 1)
			assert(campaign.owned_tool_1 == 1)
			scenario_45_equipment_verified = true
		end
		if battle.last_resolved_action_id ==
					ACTION_CROSS_SHURIKEN and
				battle.selected_character_id == 1 and
				battle.selected_action_kind ==
					ACTION_KIND_NINJA_TOOL then
			cross_shuriken_verified = true
		end
		if battle.last_resolved_action_id ==
					ACTION_SASUKE_FIRE and
				battle.selected_character_id == 2 and
				battle.selected_action_kind ==
					ACTION_KIND_ACTIVE then
			sasuke_fire_verified = true
		end
	end
	write_progress(campaign, battle)
	if complete_stage and
			campaign.scenario_id == expected_next_scenario and
			campaign.save_verified == 1 then
		if not postbattle_task_menu_ready_frame then
			-- Campaign telemetry is committed in the same frame that main
			-- enters the next preparation scene.  Let the task-menu sprites
			-- reach a stable frame before signing the screenshot.
			postbattle_task_menu_ready_frame = frame + 8
		elseif frame >= postbattle_task_menu_ready_frame then
			if postbattle_task_menu_capture_step == 0 then
				emu:screenshot(
					output_dir .. "/postbattle-task-menu.png"
				)
				if press("A") then
					postbattle_task_menu_capture_step = 1
					postbattle_task_menu_ready_frame = frame + 8
				end
			else
				finish_stage(campaign)
			end
		end
		return
	end
	assert(campaign.scenario_id == expected_scenario)
	if not battle or battle.battle_id ~= expected_battle then
		if scenario_45_completion then
			drive_scenario_45_preparation()
		elseif frame >= PREPARATION_SETTLE_FRAME then
			if capture_ui and expected_scenario == 49 and
					expected_battle == 14 then
				if preparation_step == 0 and
						not prebattle_task_menu_root_captured then
					emu:screenshot(
						output_dir ..
							"/prebattle-task-menu-root.png"
					)
					prebattle_task_menu_root_captured = true
					return
				elseif preparation_step == 3 and
						not active_key and
						not prebattle_task_confirmation_captured then
					if not prebattle_task_confirmation_ready_frame then
						prebattle_task_confirmation_ready_frame =
							frame + 8
						return
					elseif frame <
							prebattle_task_confirmation_ready_frame then
						return
					end
					emu:screenshot(
						output_dir ..
							"/prebattle-task-confirmation.png"
					)
					prebattle_task_confirmation_captured = true
					return
				end
			end
			if preparation_step == 0 and press("Down") then
				preparation_step = 1
			elseif preparation_step == 1 and press("Down") then
				preparation_step = 2
			elseif preparation_step == 2 and press("A") then
				preparation_step = 3
			elseif preparation_step == 3 and not active_key and
					frame >= next_press_frame and press("A") then
				preparation_step = 4
			end
		end
		return
	end
	if drive_deployment(battle) then
		return
	end
	if scenario_46_rule_probe then
		drive_scenario_46_rule_probe(campaign, battle)
		return
	end
	if not complete_stage and
			not scenario_49_sasuke_taijutsu_probe then
		if battle.phase == PHASE_SCRIPT_BLOCKED then
			if battle.script_phase == SCRIPT_WAIT_FOR_INPUT then
				press("A")
			end
			return
		end
		if battle.presentation_busy == 1 then
			return
		end
		if battle.phase == PHASE_UNIT_SELECTION then
			if not entry_ready_frame then
				entry_ready_frame = frame + 2
			elseif frame >= entry_ready_frame then
				finish_entry(campaign, battle)
			end
		end
		return
	end
	last_battle = battle
	if scenario_46_completion then
		scenario_46_drive_completion(battle)
		return
	end
	if scenario_47_completion then
		scenario_47_drive_completion(battle)
		return
	end
	if scenario_49_completion or
			scenario_49_sasuke_taijutsu_probe then
		scenario_49_drive_completion(battle)
		return
	end
	drive_stage_completion(battle)
end

callbacks:add("frame", function()
	local ok, error_message = xpcall(drive_frame, tostring)
	if not ok then
		emu:screenshot(output_dir .. "/failure.png")
		write_file(
			output_dir .. "/failure.txt",
			tostring(error_message)
		)
		complete = true
	end
end)
