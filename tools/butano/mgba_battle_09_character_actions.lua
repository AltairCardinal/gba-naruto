local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or tonumber(value:gsub("^0[xX]", ""), 16)
end

local function signed32(value)
	if value >= 0x80000000 then
		return value - 0x100000000
	end
	return value
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

local output_dir = required_env("MGBA_B09_ACTION_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_B09_ACTION_DONE_MARKER")
local telemetry_address =
	assert(parse_number(required_env("MGBA_B09_ACTION_TELEMETRY_ADDRESS")))
local require_ai_resource =
	os.getenv("MGBA_B09_ACTION_REQUIRE_AI_RESOURCE") == "1"
local require_ai_substitution =
	os.getenv("MGBA_B09_ACTION_REQUIRE_AI_SUBSTITUTION") == "1"
local execute_sasuke_fire =
	os.getenv("MGBA_B09_ACTION_EXECUTE_SASUKE_FIRE") == "1"
local execute_sasuke_action_05 =
	os.getenv("MGBA_B09_ACTION_EXECUTE_SASUKE_ACTION_05") == "1"
local execute_sasuke_bomb =
	os.getenv("MGBA_B09_ACTION_EXECUTE_SASUKE_BOMB") == "1"
local sasuke_action_mode_count =
	(execute_sasuke_fire and 1 or 0) +
	(execute_sasuke_action_05 and 1 or 0) +
	(execute_sasuke_bomb and 1 or 0)
assert(
	sasuke_action_mode_count <= 1,
	"choose only one Sasuke runtime action"
)
local execute_sasuke_combat =
	execute_sasuke_fire or execute_sasuke_action_05 or
	execute_sasuke_bomb
local expected_active_units =
	execute_sasuke_combat and 8 or 9
local expected_completion_round =
	(execute_sasuke_action_05 or execute_sasuke_bomb) and 3 or 2
local trap_address_text = os.getenv("MGBA_B09_ACTION_TRAP_ADDRESS")
local trap_address = trap_address_text and parse_number(trap_address_text)
local trap_after_hits =
	tonumber(os.getenv("MGBA_B09_ACTION_TRAP_AFTER_HITS") or "1")
local trap_start_frame =
	tonumber(os.getenv("MGBA_B09_ACTION_TRAP_START_FRAME") or "1")
local watch_address_text = os.getenv("MGBA_B09_ACTION_WATCH_ADDRESS")
local watch_address =
	watch_address_text and parse_number(watch_address_text)
local watch_start_frame =
	tonumber(os.getenv("MGBA_B09_ACTION_WATCH_START_FRAME") or "1")
local watch_after_hits =
	tonumber(os.getenv("MGBA_B09_ACTION_WATCH_AFTER_HITS") or "1")
local register_samples_path = output_dir .. "/register-samples.jsonl"
local input_events_path = output_dir .. "/input-events.jsonl"
local execution_trap_path = output_dir .. "/execution-trap.jsonl"
local memory_write_trap_path = output_dir .. "/memory-write-trap.jsonl"
write_file(register_samples_path, "")
write_file(input_events_path, "")
write_file(execution_trap_path, "")
write_file(memory_write_trap_path, "")

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local COMBAT_STAGE_DUEL_SETUP = 1
local COMBAT_STAGE_TECHNIQUE_TITLE = 3
local COMBAT_STAGE_ACTION_MOVIE = 4
local COMBAT_STAGE_IMPACT = 5
local COMBAT_STAGE_RESULT = 6
local COMBAT_RESOURCE_ACTION_16_MOVIE = 1
local COMBAT_RESOURCE_ACTION_05_HIT = 3
local COMBAT_RESOURCE_ACTION_05_DUST = 4
local COMBAT_RESOURCE_ACTION_16_HIT = 5
local COMBAT_RESOURCE_ACTION_16_CUTIN = 6
local COMBAT_RESOURCE_NINJA_TOOL_BOMB_PROJECTILE = 7
local COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE = 8
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_ACTION_SELECTION = 6
local PHASE_COMBINATION_DECISION = 7
local PHASE_TARGET_SELECTION = 8
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
local PHASE_ENEMY_TURN = 12
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local COMMAND_END_ACTION = 5
local ACTION_CLONE = 1
local ACTION_TELEPORT = 2
local ACTION_05 = 5
local ACTION_BOMB = 49
local requested_sasuke_action =
	execute_sasuke_action_05 and ACTION_05 or
	execute_sasuke_bomb and ACTION_BOMB or 16
local FIRE_STAGING_X = 7
local FIRE_STAGING_Y = 14
local FIRE_ATTACK_X = 7
local FIRE_ATTACK_Y = 11
local ACTION_05_SECOND_STAGING_X = 7
local ACTION_05_SECOND_STAGING_Y = 11
local ACTION_05_ATTACK_X = 7
local ACTION_05_ATTACK_Y = 10
local ACTION_05_EXECUTION_ROUND = 3
local requested_attack_x =
	(execute_sasuke_action_05 or execute_sasuke_bomb) and
		ACTION_05_ATTACK_X or FIRE_ATTACK_X
local requested_attack_y =
	(execute_sasuke_action_05 or execute_sasuke_bomb) and
		ACTION_05_ATTACK_Y or FIRE_ATTACK_Y
local FIRST_ENEMY_UNIT_ID = 4
local LAST_ENEMY_UNIT_ID = 8

local keys = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Up = C.GBA_KEY.UP,
	R = C.GBA_KEY.R,
	Select = C.GBA_KEY.SELECT,
}
local initial_press = { frame = 30, key = "A" }

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
		selected_character_id = emu:read32(telemetry_address + 72),
		action_count = emu:read32(telemetry_address + 76),
		action_index = emu:read32(telemetry_address + 80),
		selected_action_id = emu:read32(telemetry_address + 84),
		selected_action_error = emu:read32(telemetry_address + 88),
		last_resolved_action_id = emu:read32(telemetry_address + 92),
		selected_action_kind = emu:read32(telemetry_address + 104),
		selected_action_tool_slot = emu:read32(telemetry_address + 108),
		script_phase = emu:read32(telemetry_address + 148),
		presentation_resource_resolved = emu:read32(telemetry_address + 208),
		presentation_resource_type = emu:read32(telemetry_address + 212),
		presentation_resource_amount = emu:read32(telemetry_address + 216),
		presentation_resource_hp_delta = signed32(emu:read32(telemetry_address + 220)),
		presentation_resource_chakra_delta = signed32(emu:read32(telemetry_address + 224)),
		ai_secondary_planned = emu:read32(telemetry_address + 228),
		ai_defense_kind = emu:read32(telemetry_address + 232),
		ai_defense_action_id = emu:read32(telemetry_address + 236),
		ai_defense_tool_slot = emu:read32(telemetry_address + 240),
		ai_defense_score = signed32(emu:read32(telemetry_address + 244)),
		cursor_unit_id = emu:read32(telemetry_address + 304),
		cursor_unit_active = emu:read32(telemetry_address + 324),
		selected_action_level = emu:read32(telemetry_address + 332),
		presentation_combat_stage = emu:read32(telemetry_address + 364),
		presentation_combat_stage_frame = emu:read32(telemetry_address + 368),
		presentation_combat_resource = emu:read32(telemetry_address + 380),
	}
end

local function signature(telemetry)
	if not telemetry then
		return "none"
	end
	return string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.round,
		telemetry.selected_unit,
		telemetry.active_units,
		telemetry.selected_command,
		telemetry.player_completed,
		telemetry.enemy_completed,
		telemetry.cursor_x,
		telemetry.cursor_y,
		telemetry.presentation_busy,
		telemetry.selected_character_id,
		telemetry.action_count,
		telemetry.action_index,
		telemetry.selected_action_id,
		telemetry.selected_action_error,
		telemetry.last_resolved_action_id,
		telemetry.selected_action_kind,
		telemetry.selected_action_tool_slot,
		telemetry.script_phase,
		telemetry.presentation_resource_resolved,
		telemetry.presentation_resource_type,
		telemetry.presentation_resource_amount,
		telemetry.presentation_resource_hp_delta,
		telemetry.presentation_resource_chakra_delta,
		telemetry.ai_secondary_planned,
		telemetry.ai_defense_kind,
		telemetry.ai_defense_action_id,
		telemetry.ai_defense_tool_slot,
		telemetry.ai_defense_score,
		telemetry.selected_action_level
	)
end

local function append_sample(frame, telemetry)
	append_file(
		register_samples_path,
		string.format(
			'{"frame":%d,"battle_id":%d,"phase":%d,"script_phase":%d,"round":%d,"side":%d,"selected_unit":%d,"selected_character_id":%d,"active_units":%d,"unit_count":%d,"selected_command":%d,"action_count":%d,"action_index":%d,"selected_action_id":%d,"selected_action_level":%d,"selected_action_error":%d,"selected_action_kind":%d,"selected_action_tool_slot":%d,"last_resolved_action_id":%d,"player_completed":%d,"enemy_completed":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"last_control_error":%d,"last_player_error":%d,"render_stage":%d,"presentation_busy":%d,"resource_resolved":%d,"resource_type":%d,"resource_amount":%d,"resource_hp_delta":%d,"resource_chakra_delta":%d,"ai_secondary_planned":%d,"ai_defense_kind":%d,"ai_defense_action_id":%d,"ai_defense_tool_slot":%d,"ai_defense_score":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","keys":"0x%04X","ime":"0x%04X","ie":"0x%04X","if":"0x%04X","dispstat":"0x%04X","cycles":%d}\n',
			frame,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.script_phase,
			telemetry.round,
			telemetry.side,
			telemetry.selected_unit,
			telemetry.selected_character_id,
			telemetry.active_units,
			telemetry.unit_count,
			telemetry.selected_command,
			telemetry.action_count,
			telemetry.action_index,
			telemetry.selected_action_id,
			telemetry.selected_action_level,
			telemetry.selected_action_error,
			telemetry.selected_action_kind,
			telemetry.selected_action_tool_slot,
			telemetry.last_resolved_action_id,
			telemetry.player_completed,
			telemetry.enemy_completed,
			telemetry.scene_frame,
			telemetry.cursor_x,
			telemetry.cursor_y,
			telemetry.last_control_error,
			telemetry.last_player_error,
			telemetry.render_stage,
			telemetry.presentation_busy,
			telemetry.presentation_resource_resolved,
			telemetry.presentation_resource_type,
			telemetry.presentation_resource_amount,
			telemetry.presentation_resource_hp_delta,
			telemetry.presentation_resource_chakra_delta,
			telemetry.ai_secondary_planned,
			telemetry.ai_defense_kind,
			telemetry.ai_defense_action_id,
			telemetry.ai_defense_tool_slot,
			telemetry.ai_defense_score,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp"),
			emu:read16(0x04000130),
			emu:read16(0x04000208),
			emu:read16(0x04000200),
			emu:read16(0x04000202),
			emu:read16(0x04000004),
			emu:currentCycle()
		)
	)
end

local frame = 0
local complete = false
local trap_breakpoint = nil
local trap_hit_count = 0
local memory_watchpoint = nil
local memory_watch_hit_count = 0
local active_key = nil
local active_key_name = nil
local active_key_battle_id = nil
local active_key_scene_frame = nil
local release_frame = 0
local last_release_frame = -100
local last_release_battle_id = -1
local last_release_scene_frame = 0
local pending_input = nil
local last_signature = "none"
local queued_screenshots = {}
local captured_screenshots = {}
local screenshot_queue = {}
local sasuke_menu_complete = false
local sasuke_fire_standalone_selected = false
local sasuke_action_05_round_2_staged = false
local action_05_origin_x = -1
local action_05_origin_y = -1
local action_05_target_index = 1
local fire_target_scan_started = false
local fire_target_attempt_x = -1
local fire_target_attempt_y = -1
local observed = {
	naruto_menu = false,
	naruto_tool = false,
	teleport = false,
	sakura_menu = false,
	clone = false,
	sasuke_2 = false,
	sasuke_5 = false,
	sasuke_16 = false,
	ai_resource = false,
	ai_substitution = false,
}
local observed_resource = {
	round = 0,
	resource_type = 0,
	amount = 0,
	hp_delta = 0,
	chakra_delta = 0,
}

local function on_memory_write_trap(info)
	if complete then
		return
	end
	memory_watch_hit_count = memory_watch_hit_count + 1
	append_file(
		memory_write_trap_path,
		string.format(
			'{"frame":%d,"hit":%d,"address":"0x%08X","old_value":"0x%08X","new_value":"0x%08X","width":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","r0":"0x%08X","r1":"0x%08X","r2":"0x%08X","r3":"0x%08X","cycles":%d}\n',
			frame,
			memory_watch_hit_count,
			info.address or watch_address,
			info.oldValue or 0,
			info.newValue or 0,
			info.width or 0,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp"),
			emu:readRegister("r0"),
			emu:readRegister("r1"),
			emu:readRegister("r2"),
			emu:readRegister("r3"),
			emu:currentCycle()
		)
	)
	if memory_watch_hit_count < watch_after_hits then
		return
	end
	complete = true
	assert(emu:saveStateFile(output_dir .. "/memory-write-trap.ss9"))
	write_file(
		done_marker_path,
		string.format(
			'{"frame":%d,"status":"memory-write-trap"}',
			frame
		)
	)
end

local function on_execution_trap(info)
	trap_hit_count = trap_hit_count + 1
	local stack_pointer = emu:readRegister("sp")
	local stack_words = {}
	for offset = 0, 124, 4 do
		table.insert(
			stack_words,
			string.format(
				'"0x%08X"',
				emu:read32(stack_pointer + offset)
			)
		)
	end
	local registers = {}
	for index = 0, 12 do
		table.insert(
			registers,
			string.format(
				'"0x%08X"',
				emu:readRegister("r" .. tostring(index))
			)
		)
	end
	local audio_state_words = {}
	for offset = 0, 80, 4 do
		table.insert(
			audio_state_words,
			string.format(
				'"0x%08X"',
				emu:read32(0x0201F980 + offset)
			)
		)
	end
	local audio_hw_words = {}
	for offset = 0, 36, 4 do
		table.insert(
			audio_hw_words,
			string.format(
				'"0x%08X"',
				emu:read32(0x0300294C + offset)
			)
		)
	end
	-- Keep this explicit read in the contract: r12 is often the scratch
	-- register carrying the corrupted branch target on ARM.
	local r12 = emu:readRegister("r12")
	append_file(
		execution_trap_path,
		string.format(
			'{"frame":%d,"hit":%d,"address":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","r12":"0x%08X","registers":[%s],"stack":[%s],"audio_state":[%s],"audio_hw":[%s],"cycles":%d}\n',
			frame,
			trap_hit_count,
			info.address or trap_address,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			stack_pointer,
			r12,
			table.concat(registers, ","),
			table.concat(stack_words, ","),
			table.concat(audio_state_words, ","),
			table.concat(audio_hw_words, ","),
			emu:currentCycle()
		)
	)
	if trap_hit_count < trap_after_hits then
		return
	end
	assert(emu:saveStateFile(output_dir .. "/execution-trap.ss9"))
	write_file(
		done_marker_path,
		string.format(
			'{"frame":%d,"status":"execution-trap"}',
			frame
		)
	)
	complete = true
	if trap_breakpoint then
		emu:clearBreakpoint(trap_breakpoint)
		trap_breakpoint = nil
	end
end

local function queue_screenshot(key, name)
	if queued_screenshots[key] or captured_screenshots[key] then
		return
	end
	queued_screenshots[key] = true
	table.insert(
		screenshot_queue,
		{ due = frame + 3, key = key, name = name }
	)
end

local function flush_screenshots()
	for index = #screenshot_queue, 1, -1 do
		local entry = screenshot_queue[index]
		if frame >= entry.due then
			emu:screenshot(output_dir .. "/" .. entry.name)
			captured_screenshots[entry.key] = true
			table.remove(screenshot_queue, index)
		end
	end
end

local function issue_key(name, telemetry)
	if active_key or pending_input or
			frame - last_release_frame < 3 then
		return false
	end
	if telemetry and
			telemetry.phase ~= PHASE_SCRIPT_BLOCKED and
			telemetry.battle_id == last_release_battle_id and
			telemetry.scene_frame >=
					last_release_scene_frame and
			telemetry.scene_frame <=
					last_release_scene_frame + 1 then
		return false
	end
	local key = assert(keys[name])
	emu:addKey(key)
	active_key = key
	active_key_name = name
	active_key_battle_id = telemetry.battle_id
	active_key_scene_frame = telemetry.scene_frame
	release_frame = frame + 8
	pending_input = {
		signature = signature(telemetry),
		issued = frame,
	}
	append_file(
		input_events_path,
		string.format(
			'{"frame":%d,"event":"press","key":"%s","battle_id":%d,"phase":%d,"scene_frame":%d,"selected_unit":%d,"selected_action_id":%d,"cursor_x":%d,"cursor_y":%d}\n',
			frame,
			name,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.scene_frame,
			telemetry.selected_unit,
			telemetry.selected_action_id,
			telemetry.cursor_x,
			telemetry.cursor_y
		)
	)
	return true
end

local function capture_progress(telemetry)
	if telemetry.battle_id ~= 9 then
		return
	end
	if telemetry.phase == PHASE_DEPLOY_UNIT and
			telemetry.selected_unit == 1 then
		queue_screenshot(
			"deployment-unit-1",
			"deployment-unit-1.png"
		)
	end
	if telemetry.phase == PHASE_DEPLOY_START then
		queue_screenshot(
			"deployment-start",
			"deployment-start.png"
		)
	end
	if telemetry.round == 1 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.player_completed == 0 and
			telemetry.selected_unit == 1 then
		queue_screenshot("formation", "formation-3v5.png")
		queue_screenshot("naruto-selected", "naruto-selected.png")
	end
	if telemetry.phase == PHASE_ACTION_SELECTION and
			telemetry.action_count == 4 and
			telemetry.selected_unit == 1 and
			telemetry.selected_character_id == 1 and
			telemetry.selected_action_level == 1 and
			telemetry.selected_action_id == ACTION_TELEPORT then
		observed.naruto_menu = true
		queue_screenshot("naruto-actions", "naruto-actions.png")
	end
	if execute_sasuke_fire and
			telemetry.presentation_busy == 1 and
			telemetry.last_resolved_action_id == 16 then
		local captures = {
			{
				key = "sasuke-fire-duel",
				name = "sasuke-fire-duel.png",
				stage = COMBAT_STAGE_DUEL_SETUP,
				due_frame = 4,
			},
			{
				key = "sasuke-fire-cutin-slide",
				name = "sasuke-fire-cutin-slide.png",
				stage = COMBAT_STAGE_TECHNIQUE_TITLE,
				resource = COMBAT_RESOURCE_ACTION_16_CUTIN,
				due_frame = 10,
			},
			{
				key = "sasuke-fire-title",
				name = "sasuke-fire-title.png",
				stage = COMBAT_STAGE_TECHNIQUE_TITLE,
				resource = COMBAT_RESOURCE_ACTION_16_CUTIN,
				due_frame = 60,
			},
			{
				key = "sasuke-fire-cutin-fade",
				name = "sasuke-fire-cutin-fade.png",
				stage = COMBAT_STAGE_TECHNIQUE_TITLE,
				resource = COMBAT_RESOURCE_ACTION_16_CUTIN,
				due_frame = 111,
			},
			{
				key = "sasuke-fire-movie-actor",
				name = "sasuke-fire-movie-actor.png",
				stage = COMBAT_STAGE_ACTION_MOVIE,
				resource = COMBAT_RESOURCE_ACTION_16_MOVIE,
				due_frame = 30,
			},
			{
				key = "sasuke-fire-movie-reference",
				name = "sasuke-fire-movie-reference.png",
				stage = COMBAT_STAGE_ACTION_MOVIE,
				resource = COMBAT_RESOURCE_ACTION_16_MOVIE,
				due_frame = 50,
			},
			{
				key = "sasuke-fire-movie-expanded",
				name = "sasuke-fire-movie-expanded.png",
				stage = COMBAT_STAGE_ACTION_MOVIE,
				resource = COMBAT_RESOURCE_ACTION_16_MOVIE,
				due_frame = 90,
			},
			{
				key = "sasuke-fire-impact-00",
				name = "sasuke-fire-impact-00.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_16_HIT,
				due_frame = 50,
			},
			{
				key = "sasuke-fire-impact-04",
				name = "sasuke-fire-impact-04.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_16_HIT,
				due_frame = 54,
			},
			{
				key = "sasuke-fire-impact-08",
				name = "sasuke-fire-impact-08.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_16_HIT,
				due_frame = 58,
			},
			{
				key = "sasuke-fire-impact-12",
				name = "sasuke-fire-impact-12.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_16_HIT,
				due_frame = 62,
			},
			{
				key = "sasuke-fire-impact-15",
				name = "sasuke-fire-impact-15.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_16_HIT,
				due_frame = 65,
			},
		}
		for _, capture in ipairs(captures) do
			if telemetry.presentation_combat_stage ==
						capture.stage and
					(not capture.resource or
					 telemetry.presentation_combat_resource ==
						capture.resource) and
					telemetry.presentation_combat_stage_frame >=
						capture.due_frame and
					not captured_screenshots[capture.key] then
				emu:screenshot(
					output_dir .. "/" .. capture.name
				)
				if capture.key == "sasuke-fire-title" then
					assert(emu:saveStateFile(
						output_dir .. "/sasuke-fire-cutin.ss9"
					))
				end
				captured_screenshots[capture.key] = true
			end
		end
	end
	if execute_sasuke_fire and
			captured_screenshots["sasuke-fire-impact-15"] and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot(
			"sasuke-fire-map-restored",
			"sasuke-fire-map-restored.png"
		)
	end
	if execute_sasuke_action_05 and
			telemetry.presentation_busy == 1 and
			telemetry.last_resolved_action_id == ACTION_05 and
			telemetry.presentation_combat_stage ==
				COMBAT_STAGE_ACTION_MOVIE and
			telemetry.presentation_combat_resource ==
				COMBAT_RESOURCE_ACTION_05_DUST then
		local captures = {
			{
				key = "sasuke-action-05-dust-01",
				name = "sasuke-action-05-dust-01.png",
				due_frame = 1,
			},
			{
				key = "sasuke-action-05-dust-20",
				name = "sasuke-action-05-dust-20.png",
				due_frame = 20,
			},
			{
				key = "sasuke-action-05-dust-58",
				name = "sasuke-action-05-dust-58.png",
				due_frame = 58,
			},
			-- The frame callback observes telemetry before the newly
			-- rendered frame is presented, so sample step 60 at 61.
			{
				key = "sasuke-action-05-reentry-60",
				name = "sasuke-action-05-reentry-60.png",
				due_frame = 61,
			},
		}
		for _, capture in ipairs(captures) do
			if telemetry.presentation_combat_stage_frame >=
						capture.due_frame and
					not captured_screenshots[capture.key] then
				emu:screenshot(
					output_dir .. "/" .. capture.name
				)
				captured_screenshots[capture.key] = true
			end
		end
	end
	if execute_sasuke_action_05 and
			telemetry.presentation_busy == 1 and
			telemetry.last_resolved_action_id == ACTION_05 and
			telemetry.presentation_combat_stage ==
				COMBAT_STAGE_IMPACT and
			telemetry.presentation_combat_resource ==
				COMBAT_RESOURCE_ACTION_05_HIT then
		local captures = {
			{
				key = "sasuke-action-05-impact-00",
				name = "sasuke-action-05-impact-00.png",
				due_frame = 1,
			},
			{
				key = "sasuke-action-05-impact-04",
				name = "sasuke-action-05-impact-04.png",
				due_frame = 4,
			},
			{
				key = "sasuke-action-05-impact-08",
				name = "sasuke-action-05-impact-08.png",
				due_frame = 8,
			},
			{
				key = "sasuke-action-05-impact-12",
				name = "sasuke-action-05-impact-12.png",
				due_frame = 12,
			},
			{
				key = "sasuke-action-05-impact-15",
				name = "sasuke-action-05-impact-15.png",
				due_frame = 15,
			},
		}
		for _, capture in ipairs(captures) do
			if telemetry.presentation_combat_stage_frame >=
						capture.due_frame and
					not captured_screenshots[capture.key] then
				emu:screenshot(
					output_dir .. "/" .. capture.name
				)
				captured_screenshots[capture.key] = true
			end
		end
	end
	if execute_sasuke_action_05 and
			captured_screenshots[
				"sasuke-action-05-impact-15"] and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot(
			"sasuke-action-05-map-restored",
			"sasuke-action-05-map-restored.png"
		)
	end
	if execute_sasuke_bomb and
			telemetry.presentation_busy == 1 and
			telemetry.last_resolved_action_id == ACTION_BOMB then
		local captures = {
			{
				key = "sasuke-bomb-projectile-01",
				name = "sasuke-bomb-projectile-01.png",
				stage = COMBAT_STAGE_ACTION_MOVIE,
				resource =
					COMBAT_RESOURCE_NINJA_TOOL_BOMB_PROJECTILE,
				due_frame = 1,
			},
			{
				key = "sasuke-bomb-projectile-07",
				name = "sasuke-bomb-projectile-07.png",
				stage = COMBAT_STAGE_ACTION_MOVIE,
				resource =
					COMBAT_RESOURCE_NINJA_TOOL_BOMB_PROJECTILE,
				due_frame = 6,
			},
			{
				key = "sasuke-bomb-impact-08",
				name = "sasuke-bomb-impact-08.png",
				stage = COMBAT_STAGE_IMPACT,
				resource = COMBAT_RESOURCE_ACTION_05_HIT,
				due_frame = 8,
			},
			{
				key = "sasuke-bomb-smoke-01",
				name = "sasuke-bomb-smoke-01.png",
				stage = COMBAT_STAGE_RESULT,
				resource = COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE,
				due_frame = 1,
			},
			{
				key = "sasuke-bomb-smoke-40",
				name = "sasuke-bomb-smoke-40.png",
				stage = COMBAT_STAGE_RESULT,
				resource = COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE,
				due_frame = 40,
			},
			{
				key = "sasuke-bomb-smoke-80",
				name = "sasuke-bomb-smoke-80.png",
				stage = COMBAT_STAGE_RESULT,
				resource = COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE,
				due_frame = 80,
			},
			{
				key = "sasuke-bomb-smoke-110",
				name = "sasuke-bomb-smoke-110.png",
				stage = COMBAT_STAGE_RESULT,
				resource = COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE,
				due_frame = 110,
			},
		}
		for _, capture in ipairs(captures) do
			if telemetry.presentation_combat_stage ==
						capture.stage and
					telemetry.presentation_combat_resource ==
						capture.resource and
					telemetry.presentation_combat_stage_frame >=
						capture.due_frame and
					not captured_screenshots[capture.key] then
				emu:screenshot(
					output_dir .. "/" .. capture.name
				)
				captured_screenshots[capture.key] = true
			end
		end
	end
	if execute_sasuke_bomb and
			captured_screenshots["sasuke-bomb-smoke-110"] and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot(
			"sasuke-bomb-map-restored",
			"sasuke-bomb-map-restored.png"
		)
	end
	if telemetry.phase == PHASE_ACTION_SELECTION and
			telemetry.action_count == 4 and
			telemetry.selected_unit == 1 and
			telemetry.selected_character_id == 1 and
			telemetry.action_index == 3 and
			telemetry.selected_action_kind == 1 and
			telemetry.selected_action_tool_slot == 0 and
			telemetry.selected_action_id == 1 then
		observed.naruto_tool = true
		queue_screenshot("naruto-tool", "naruto-tool.png")
	end
	if telemetry.phase == PHASE_FACING_SELECTION and
			telemetry.presentation_busy == 0 and
			telemetry.last_resolved_action_id == ACTION_TELEPORT and
			telemetry.active_units == 8 then
		observed.teleport = true
		queue_screenshot(
			"naruto-teleport-result",
			"naruto-teleport-result.png"
		)
	end
	if telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.selected_unit == 3 and
			telemetry.player_completed == 1 then
		queue_screenshot("sakura-selected", "sakura-selected.png")
	end
	if telemetry.phase == PHASE_ACTION_SELECTION and
			telemetry.action_count == 3 and
			telemetry.selected_unit == 3 and
			telemetry.selected_character_id == 3 and
			telemetry.selected_action_level == 1 and
			telemetry.selected_action_id == ACTION_CLONE then
		observed.sakura_menu = true
		queue_screenshot("sakura-actions", "sakura-actions.png")
	end
	if telemetry.phase == PHASE_FACING_SELECTION and
			telemetry.presentation_busy == 0 and
			telemetry.last_resolved_action_id == ACTION_CLONE and
			telemetry.active_units == 9 then
		observed.clone = true
		queue_screenshot(
			"sakura-clone-result",
			"sakura-clone-result.png"
		)
	end
	if telemetry.phase == PHASE_ACTION_SELECTION and
			telemetry.action_count >= 3 and
			telemetry.selected_unit == 2 and
			telemetry.selected_character_id == 2 and
			telemetry.selected_action_level == 1 then
		if telemetry.selected_action_id == 2 then
			observed.sasuke_2 = true
			queue_screenshot("sasuke-2", "sasuke-action-2.png")
		elseif telemetry.selected_action_id == 5 then
			observed.sasuke_5 = true
			queue_screenshot("sasuke-5", "sasuke-action-5.png")
		elseif telemetry.selected_action_id == 16 then
			observed.sasuke_16 = true
			queue_screenshot("sasuke-16", "sasuke-action-16.png")
		end
	end
	if telemetry.phase == PHASE_ENEMY_TURN and
			telemetry.active_units == 9 then
		queue_screenshot(
			"enemy-active-9",
			"enemy-phase-active-9.png"
		)
	end
	if telemetry.presentation_resource_resolved == 1 then
		observed.ai_resource = true
		observed_resource.round = telemetry.round
		observed_resource.resource_type =
			telemetry.presentation_resource_type
		observed_resource.amount =
			telemetry.presentation_resource_amount
		observed_resource.hp_delta =
			telemetry.presentation_resource_hp_delta
		observed_resource.chakra_delta =
			telemetry.presentation_resource_chakra_delta
		queue_screenshot(
			"enemy-resource-action",
			"enemy-resource-action.png"
		)
	end
	if telemetry.ai_secondary_planned == 1 and
			telemetry.ai_defense_kind == 1 and
			telemetry.ai_defense_action_id == 3 then
		observed.ai_substitution = true
	end
	if telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 and
			telemetry.active_units == 9 then
		queue_screenshot(
			"round-2-active-9",
			"round-2-active-9.png"
		)
	end
end

local function drive_fire_target_scan(telemetry)
	local cursor_has_enemy =
		telemetry.cursor_unit_active == 1 and
		telemetry.cursor_unit_id >= FIRST_ENEMY_UNIT_ID and
		telemetry.cursor_unit_id <= LAST_ENEMY_UNIT_ID
	if cursor_has_enemy and
			(fire_target_attempt_x ~= telemetry.cursor_x or
			 fire_target_attempt_y ~= telemetry.cursor_y) then
		if issue_key("A", telemetry) then
			fire_target_attempt_x = telemetry.cursor_x
			fire_target_attempt_y = telemetry.cursor_y
		end
		return
	end

	if not fire_target_scan_started then
		if telemetry.cursor_x > 0 then
			issue_key("Left", telemetry)
		elseif telemetry.cursor_y > 0 then
			issue_key("Up", telemetry)
		else
			fire_target_scan_started = true
		end
		return
	end

	if telemetry.cursor_y % 2 == 0 then
		if telemetry.cursor_x < 15 then
			issue_key("Right", telemetry)
		else
			assert(
				telemetry.cursor_y < 31,
				"no active battle-9 enemy accepted the fire action"
			)
			issue_key("Down", telemetry)
		end
	elseif telemetry.cursor_x > 0 then
		issue_key("Left", telemetry)
	else
		assert(
			telemetry.cursor_y < 31,
			"no active battle-9 enemy accepted the fire action"
		)
		issue_key("Down", telemetry)
	end
end

local action_05_adjacent_offsets = {
	{ x = 0, y = -1 },
	{ x = 1, y = 0 },
	{ x = 0, y = 1 },
	{ x = -1, y = 0 },
}

local function drive_action_05_adjacent_target(telemetry)
	assert(action_05_origin_x >= 0 and action_05_origin_y >= 0)
	assert(
		action_05_target_index <= #action_05_adjacent_offsets,
		"no adjacent active battle-9 enemy accepted action 5"
	)
	local offset =
		action_05_adjacent_offsets[action_05_target_index]
	local target_x = action_05_origin_x + offset.x
	local target_y = action_05_origin_y + offset.y
	if telemetry.cursor_x > target_x then
		issue_key("Left", telemetry)
	elseif telemetry.cursor_x < target_x then
		issue_key("Right", telemetry)
	elseif telemetry.cursor_y > target_y then
		issue_key("Up", telemetry)
	elseif telemetry.cursor_y < target_y then
		issue_key("Down", telemetry)
	else
		local cursor_has_enemy =
			telemetry.cursor_unit_active == 1 and
			telemetry.cursor_unit_id >= FIRST_ENEMY_UNIT_ID and
			telemetry.cursor_unit_id <= LAST_ENEMY_UNIT_ID
		if cursor_has_enemy then
			issue_key("A", telemetry)
		else
			action_05_target_index =
				action_05_target_index + 1
		end
	end
end

local function drive_battle(telemetry)
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			issue_key("A", telemetry)
		end
		return
	end
	if telemetry.phase == PHASE_DEPLOY_UNIT or
			telemetry.phase == PHASE_DEPLOY_START then
		issue_key("A", telemetry)
		return
	end
	if telemetry.battle_id == 41 then
		if telemetry.phase == PHASE_UNIT_SELECTION and
				telemetry.scene_frame >= 2 then
			issue_key("Select", telemetry)
		end
		return
	end
	if telemetry.battle_id == 43 then
		if telemetry.scene_frame >= 2 then
			issue_key("Select", telemetry)
		end
		return
	end
	if telemetry.battle_id ~= 9 or
			telemetry.presentation_busy == 1 then
		return
	end

	if telemetry.round >= 2 then
		if (execute_sasuke_action_05 or execute_sasuke_bomb) and
				telemetry.round < ACTION_05_EXECUTION_ROUND then
			if sasuke_action_05_round_2_staged then
				if telemetry.phase == PHASE_UNIT_SELECTION then
					issue_key("A", telemetry)
				elseif telemetry.phase == PHASE_MOVE_SELECTION then
					issue_key("A", telemetry)
				elseif telemetry.phase ==
						PHASE_COMMAND_SELECTION then
					if telemetry.selected_command ==
							COMMAND_END_ACTION then
						issue_key("A", telemetry)
					else
						issue_key("Down", telemetry)
					end
				elseif telemetry.phase ==
						PHASE_FACING_SELECTION or
						telemetry.phase ==
							PHASE_DEFENSE_DECISION then
					issue_key("A", telemetry)
				end
			elseif telemetry.phase == PHASE_UNIT_SELECTION then
				if telemetry.selected_unit == 2 then
					issue_key("A", telemetry)
				else
					issue_key("R", telemetry)
				end
			elseif telemetry.phase == PHASE_MOVE_SELECTION then
				if telemetry.cursor_x >
						ACTION_05_SECOND_STAGING_X then
					issue_key("Left", telemetry)
				elseif telemetry.cursor_x <
						ACTION_05_SECOND_STAGING_X then
					issue_key("Right", telemetry)
				elseif telemetry.cursor_y >
						ACTION_05_SECOND_STAGING_Y then
					issue_key("Up", telemetry)
				elseif telemetry.cursor_y <
						ACTION_05_SECOND_STAGING_Y then
					issue_key("Down", telemetry)
				else
					issue_key("A", telemetry)
				end
			elseif telemetry.phase == PHASE_COMMAND_SELECTION then
				if telemetry.selected_command ==
						COMMAND_END_ACTION then
					if issue_key("A", telemetry) then
						sasuke_action_05_round_2_staged = true
					end
				else
					issue_key("Down", telemetry)
				end
			elseif telemetry.phase == PHASE_FACING_SELECTION or
					telemetry.phase ==
						PHASE_DEFENSE_DECISION then
				issue_key("A", telemetry)
			end
		elseif execute_sasuke_combat then
			if telemetry.phase == PHASE_UNIT_SELECTION then
				if (execute_sasuke_fire and
						captured_screenshots[
							"sasuke-fire-duel"]) or
						(execute_sasuke_action_05 and
							captured_screenshots[
								"sasuke-action-05-impact-15"]) or
						(execute_sasuke_bomb and
							captured_screenshots[
								"sasuke-bomb-smoke-110"]) then
					return
				elseif telemetry.selected_unit == 2 then
					issue_key("A", telemetry)
				else
					issue_key("R", telemetry)
				end
			elseif telemetry.phase == PHASE_MOVE_SELECTION then
				if execute_sasuke_action_05 or execute_sasuke_bomb then
					if telemetry.cursor_x >
							requested_attack_x then
						issue_key("Left", telemetry)
					elseif telemetry.cursor_x <
							requested_attack_x then
						issue_key("Right", telemetry)
					elseif telemetry.cursor_y >
							requested_attack_y then
						issue_key("Up", telemetry)
					elseif telemetry.cursor_y <
							requested_attack_y then
						issue_key("Down", telemetry)
					else
						action_05_origin_x =
							telemetry.cursor_x
						action_05_origin_y =
							telemetry.cursor_y
						issue_key("A", telemetry)
					end
				elseif telemetry.cursor_x > requested_attack_x then
					issue_key("Left", telemetry)
				elseif telemetry.cursor_x < requested_attack_x then
					issue_key("Right", telemetry)
				elseif telemetry.cursor_y > requested_attack_y then
					issue_key("Up", telemetry)
				elseif telemetry.cursor_y < requested_attack_y then
					issue_key("Down", telemetry)
				else
					issue_key("A", telemetry)
				end
			elseif telemetry.phase == PHASE_COMMAND_SELECTION then
				issue_key("A", telemetry)
			elseif telemetry.phase == PHASE_ACTION_SELECTION then
				if telemetry.selected_action_id ==
						requested_sasuke_action then
					issue_key("A", telemetry)
				else
					issue_key("Down", telemetry)
				end
			elseif telemetry.phase ==
					PHASE_COMBINATION_DECISION then
				if not sasuke_fire_standalone_selected then
					if issue_key("Down", telemetry) then
						sasuke_fire_standalone_selected = true
					end
				else
					issue_key("A", telemetry)
				end
			elseif telemetry.phase == PHASE_TARGET_SELECTION then
				if execute_sasuke_action_05 or execute_sasuke_bomb then
					drive_action_05_adjacent_target(telemetry)
				else
					drive_fire_target_scan(telemetry)
				end
			elseif telemetry.phase == PHASE_FACING_SELECTION or
					telemetry.phase ==
						PHASE_DEFENSE_DECISION then
				issue_key("A", telemetry)
			end
		elseif telemetry.phase == PHASE_UNIT_SELECTION then
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
				telemetry.phase ==
					PHASE_DEFENSE_DECISION then
			issue_key("A", telemetry)
		end
		return
	end

	if telemetry.phase == PHASE_UNIT_SELECTION then
		if telemetry.selected_unit == 1 and
				telemetry.player_completed == 0 then
			if captured_screenshots["formation"] and
					captured_screenshots["naruto-selected"] then
				issue_key("A", telemetry)
			end
		elseif telemetry.selected_unit == 2 and
				telemetry.player_completed == 1 then
			issue_key("R", telemetry)
		elseif telemetry.selected_unit == 3 and
				telemetry.player_completed == 1 then
			if captured_screenshots["sakura-selected"] then
				issue_key("A", telemetry)
			end
		elseif telemetry.selected_unit == 2 and
				telemetry.player_completed >= 3 then
			issue_key("A", telemetry)
		end
	elseif telemetry.phase == PHASE_MOVE_SELECTION then
		if execute_sasuke_combat and
				telemetry.selected_unit == 2 and
				telemetry.player_completed >= 3 then
			if telemetry.cursor_x > FIRE_STAGING_X then
				issue_key("Left", telemetry)
			elseif telemetry.cursor_y > FIRE_STAGING_Y then
				issue_key("Up", telemetry)
			else
				issue_key("A", telemetry)
			end
		else
			issue_key("A", telemetry)
		end
	elseif telemetry.phase == PHASE_COMMAND_SELECTION then
		if telemetry.selected_unit == 2 and
				telemetry.player_completed >= 3 and
				sasuke_menu_complete then
			if telemetry.selected_command == COMMAND_END_ACTION then
				issue_key("A", telemetry)
			else
				issue_key("Down", telemetry)
			end
		else
			issue_key("A", telemetry)
		end
	elseif telemetry.phase == PHASE_ACTION_SELECTION then
		if telemetry.selected_unit == 1 then
			if not captured_screenshots["naruto-tool"] then
				if telemetry.action_index < 3 then
					issue_key("Down", telemetry)
				end
			elseif telemetry.action_index > 0 then
				issue_key("Up", telemetry)
			elseif telemetry.selected_action_id == ACTION_TELEPORT and
					captured_screenshots["naruto-actions"] then
				issue_key("A", telemetry)
			end
		elseif telemetry.selected_unit == 3 and
				telemetry.selected_action_id == ACTION_CLONE and
				captured_screenshots["sakura-actions"] then
			issue_key("A", telemetry)
		elseif telemetry.selected_unit == 2 then
			if telemetry.selected_action_id == 2 and
					captured_screenshots["sasuke-2"] then
				issue_key("Down", telemetry)
			elseif telemetry.selected_action_id == 5 and
					captured_screenshots["sasuke-5"] then
				issue_key("Down", telemetry)
			elseif telemetry.selected_action_id == 16 and
					captured_screenshots["sasuke-16"] then
				if issue_key("B", telemetry) then
					sasuke_menu_complete = true
				end
			end
		end
	elseif telemetry.phase == PHASE_COMBINATION_DECISION then
		if execute_sasuke_fire and telemetry.selected_unit == 2 then
			if not sasuke_fire_standalone_selected then
				if issue_key("Down", telemetry) then
					sasuke_fire_standalone_selected = true
				end
			else
				issue_key("A", telemetry)
			end
		end
	elseif telemetry.phase == PHASE_TARGET_SELECTION then
		if telemetry.cursor_y == 15 then
			issue_key("Up", telemetry)
		else
			issue_key("A", telemetry)
		end
	elseif telemetry.phase == PHASE_FACING_SELECTION then
		if telemetry.selected_unit == 1 and
				not captured_screenshots["naruto-teleport-result"] then
			return
		end
		if telemetry.selected_unit == 3 and
				not captured_screenshots["sakura-clone-result"] then
			return
		end
		issue_key("A", telemetry)
	elseif telemetry.phase == PHASE_DEFENSE_DECISION then
		issue_key("A", telemetry)
	end
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame == initial_press.frame then
		local key = assert(keys[initial_press.key])
		emu:addKey(key)
		active_key = key
		active_key_name = initial_press.key
		active_key_battle_id = nil
		active_key_scene_frame = nil
		release_frame = frame + 8
	end
	if trap_address and frame >= trap_start_frame and not trap_breakpoint then
		trap_breakpoint =
			emu:setBreakpoint(on_execution_trap, trap_address)
	end
	if watch_address and frame >= watch_start_frame and
			not memory_watchpoint then
		memory_watchpoint = emu:setRangeWatchpoint(
			on_memory_write_trap,
			watch_address,
			watch_address + 1,
			C.WATCHPOINT_TYPE.WRITE_CHANGE
		)
	end

	local telemetry = read_telemetry()
	local game_sampled_active_key =
			active_key_scene_frame == nil or
			not telemetry or
			telemetry.phase == PHASE_SCRIPT_BLOCKED or
			telemetry.battle_id ~= active_key_battle_id or
			telemetry.scene_frame >=
					active_key_scene_frame + 2
	if active_key and frame >= release_frame and
			game_sampled_active_key then
		emu:clearKey(active_key)
		append_file(
			input_events_path,
			string.format(
				'{"frame":%d,"event":"release","key":"%s"}\n',
				frame,
				active_key_name
			)
		)
		active_key = nil
		active_key_name = nil
		active_key_battle_id = nil
		active_key_scene_frame = nil
		last_release_frame = frame
		if telemetry then
			last_release_battle_id = telemetry.battle_id
			last_release_scene_frame = telemetry.scene_frame
		end
	end

	local current_signature = signature(telemetry)
	if pending_input then
		if current_signature ~= pending_input.signature then
			pending_input = nil
		elseif frame - pending_input.issued == 120 and telemetry then
			append_sample(frame, telemetry)
			emu:screenshot(output_dir .. "/stalled-input.png")
		elseif frame - pending_input.issued >= 180 then
			pending_input = nil
		end
	end

	if telemetry then
		if current_signature ~= last_signature then
			append_sample(frame, telemetry)
			last_signature = current_signature
		end
		if frame % 120 == 0 then
			append_sample(frame, telemetry)
			if frame == 120 then
				emu:screenshot(output_dir .. "/periodic-stall.png")
			end
		end
		capture_progress(telemetry)
	end
	flush_screenshots()
	if telemetry then
		drive_battle(telemetry)
	end

	if telemetry and telemetry.battle_id == 9 and
			telemetry.round >= expected_completion_round and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 and
			telemetry.active_units == expected_active_units and
			captured_screenshots["round-2-active-9"] and
			(not execute_sasuke_fire or
				(captured_screenshots["sasuke-fire-duel"] and
					captured_screenshots[
						"sasuke-fire-cutin-slide"] and
					captured_screenshots["sasuke-fire-title"] and
					captured_screenshots[
						"sasuke-fire-cutin-fade"] and
					captured_screenshots[
						"sasuke-fire-movie-actor"] and
					captured_screenshots[
						"sasuke-fire-movie-reference"] and
					captured_screenshots[
						"sasuke-fire-movie-expanded"] and
					captured_screenshots[
						"sasuke-fire-impact-00"] and
					captured_screenshots[
						"sasuke-fire-impact-04"] and
					captured_screenshots[
						"sasuke-fire-impact-08"] and
					captured_screenshots[
						"sasuke-fire-impact-12"] and
					captured_screenshots[
						"sasuke-fire-impact-15"] and
					captured_screenshots[
						"sasuke-fire-map-restored"])) and
			(not execute_sasuke_action_05 or
				(captured_screenshots[
					"sasuke-action-05-dust-01"] and
					captured_screenshots[
						"sasuke-action-05-dust-20"] and
					captured_screenshots[
						"sasuke-action-05-dust-58"] and
					captured_screenshots[
						"sasuke-action-05-reentry-60"] and
					captured_screenshots[
						"sasuke-action-05-impact-00"] and
					captured_screenshots[
						"sasuke-action-05-impact-04"] and
					captured_screenshots[
						"sasuke-action-05-impact-08"] and
					captured_screenshots[
						"sasuke-action-05-impact-12"] and
					captured_screenshots[
						"sasuke-action-05-impact-15"] and
					captured_screenshots[
						"sasuke-action-05-map-restored"])) and
			(not execute_sasuke_bomb or
				(captured_screenshots[
					"sasuke-bomb-projectile-01"] and
					captured_screenshots[
						"sasuke-bomb-projectile-07"] and
					captured_screenshots[
						"sasuke-bomb-impact-08"] and
					captured_screenshots[
						"sasuke-bomb-smoke-01"] and
					captured_screenshots[
						"sasuke-bomb-smoke-40"] and
					captured_screenshots[
						"sasuke-bomb-smoke-80"] and
					captured_screenshots[
						"sasuke-bomb-smoke-110"] and
					captured_screenshots[
						"sasuke-bomb-map-restored"])) and
			(not require_ai_resource or
				(observed.ai_resource and
					captured_screenshots[
						"enemy-resource-action"])) and
			#screenshot_queue == 0 then
		assert(observed.naruto_menu)
		assert(observed.naruto_tool)
		assert(observed.teleport)
		assert(observed.sakura_menu)
		assert(observed.clone)
		assert(observed.sasuke_2)
		assert(observed.sasuke_5)
		assert(observed.sasuke_16)
		if require_ai_substitution then
			assert(observed.ai_substitution)
		end
		if require_ai_resource then
			assert(observed.ai_resource)
		end
		assert(telemetry.last_control_error == 0)
		assert(telemetry.last_player_error == 0)
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"battle_id":9,"actual_active_units":%d,"actual_round":%d,"actual_phase":%d,"last_resolved_action_id":%d,"expected_active_units":%d,"expected_round":%d,"expected_action_level":1,"naruto_action":2,"naruto_tool":1,"sakura_action":1,"sasuke_actions":[2,5,16],"sasuke_fire_executed":%s,"sasuke_action_05_executed":%s,"sasuke_bomb_executed":%s,"ai_substitution_observed":%s,"ai_resource_required":%s,"ai_resource_observed":%s,"ai_resource_round":%d,"ai_resource_type":%d,"ai_resource_amount":%d,"ai_resource_hp_delta":%d,"ai_resource_chakra_delta":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","cycles":%d,"status":"capture-complete"}',
				frame,
				telemetry.active_units,
				telemetry.round,
				telemetry.phase,
				telemetry.last_resolved_action_id,
				expected_active_units,
				expected_completion_round,
				execute_sasuke_fire and "true" or "false",
				execute_sasuke_action_05 and "true" or "false",
				execute_sasuke_bomb and "true" or "false",
				observed.ai_substitution and "true" or "false",
				require_ai_resource and "true" or "false",
				observed.ai_resource and "true" or "false",
				observed_resource.round,
				observed_resource.resource_type,
				observed_resource.amount,
				observed_resource.hp_delta,
				observed_resource.chakra_delta,
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
