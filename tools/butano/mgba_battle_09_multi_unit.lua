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

local output_dir = required_env("MGBA_B09_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_B09_DONE_MARKER")
local telemetry_address =
	assert(parse_number(required_env("MGBA_B09_TELEMETRY_ADDRESS")))
local register_samples_path = output_dir .. "/register-samples.jsonl"
local input_events_path = output_dir .. "/input-events.jsonl"
write_file(register_samples_path, "")
write_file(input_events_path, "")

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
local PHASE_ENEMY_TURN = 12
local COMMAND_END_ACTION = 5

local keys = {
	A = C.GBA_KEY.A,
	Down = C.GBA_KEY.DOWN,
	Right = C.GBA_KEY.RIGHT,
	Select = C.GBA_KEY.SELECT,
}

-- The first SELECT enters the generic battle route. All later input is
-- driven by the exported controller snapshot, not by guessed frame timing.
local initial_presses = {
	{ 30, "Select" },
}

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
	}
end

local function signature(telemetry)
	if not telemetry then
		return "none"
	end
	return string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.round,
		telemetry.selected_unit,
		telemetry.selected_command,
		telemetry.player_completed,
		telemetry.enemy_completed,
		telemetry.cursor_x,
		telemetry.cursor_y,
		telemetry.last_control_error,
		telemetry.last_player_error,
		telemetry.presentation_busy
	)
end

local function append_sample(frame, telemetry)
	append_file(
		register_samples_path,
		string.format(
			'{"frame":%d,"battle_id":%d,"phase":%d,"round":%d,"selected_unit":%d,"selected_command":%d,"player_completed":%d,"enemy_completed":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"last_control_error":%d,"last_player_error":%d,"render_stage":%d,"presentation_busy":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","keys":"0x%04X","cycles":%d}\n',
			frame,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.round,
			telemetry.selected_unit,
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
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp"),
			emu:read16(0x04000130),
			emu:currentCycle()
		)
	)
end

local frame = 0
local complete = false
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
local screenshots = {}
local screenshot_queue = {}

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

local function issue_key(name, telemetry)
	if active_key or pending_input or
			frame - last_release_frame < 3 then
		return false
	end
	if telemetry and
			telemetry.battle_id == last_release_battle_id and
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
			'{"frame":%d,"event":"press","key":"%s","battle_id":%d,"phase":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d}\n',
			frame,
			name,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.scene_frame,
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
	if telemetry.round == 1 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.player_completed == 0 then
		queue_screenshot("formation", "formation-3v5.png")
	end
	if telemetry.phase == PHASE_MOVE_SELECTION then
		if telemetry.selected_unit == 1 then
			queue_screenshot("p1", "player-1-selected.png")
		elseif telemetry.selected_unit == 2 then
			queue_screenshot("p2", "player-2-selected.png")
		elseif telemetry.selected_unit == 3 then
			queue_screenshot("p3", "player-3-selected.png")
		end
	end
	if telemetry.phase == PHASE_ENEMY_TURN then
		if telemetry.enemy_completed == 0 then
			queue_screenshot("enemy-start", "enemy-phase-start.png")
		elseif telemetry.enemy_completed == 1 then
			queue_screenshot("enemy-1", "enemy-done-1-of-5.png")
		elseif telemetry.enemy_completed == 2 then
			queue_screenshot("enemy-2", "enemy-done-2-of-5.png")
		elseif telemetry.enemy_completed == 3 then
			queue_screenshot("enemy-3", "enemy-done-3-of-5.png")
		elseif telemetry.enemy_completed == 4 then
			queue_screenshot("enemy-4", "enemy-done-4-of-5.png")
		end
	end
	if telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot("round-2", "round-2-player.png")
	end
end

local function drive_battle(telemetry)
	if telemetry.battle_id == 43 then
		if telemetry.scene_frame >= 2 then
			issue_key("Select", telemetry)
		end
		return
	end
	if telemetry.battle_id ~= 9 or telemetry.round >= 2 then
		return
	end

	if telemetry.phase == PHASE_UNIT_SELECTION or
			telemetry.phase == PHASE_FACING_SELECTION or
			telemetry.phase == PHASE_DEFENSE_DECISION then
		issue_key("A", telemetry)
	elseif telemetry.phase == PHASE_MOVE_SELECTION then
		local origins = {
			[1] = { x = 11, y = 15 },
			[2] = { x = 9, y = 15 },
			[3] = { x = 13, y = 15 },
		}
		local origin = origins[telemetry.selected_unit]
		if origin and telemetry.cursor_x == origin.x and
				telemetry.cursor_y == origin.y then
			issue_key("Right", telemetry)
		else
			issue_key("A", telemetry)
		end
	elseif telemetry.phase == PHASE_COMMAND_SELECTION then
		if telemetry.selected_command == COMMAND_END_ACTION then
			issue_key("A", telemetry)
		else
			issue_key("Down", telemetry)
		end
	end
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1

	for _, press in ipairs(initial_presses) do
		local key = assert(keys[press[2]])
		if frame == press[1] then
			emu:addKey(key)
			active_key = key
			active_key_name = press[2]
			active_key_battle_id = nil
			active_key_scene_frame = nil
			release_frame = frame + 8
		end
	end

	local telemetry = read_telemetry()
	local game_sampled_active_key =
			active_key_scene_frame == nil or
			not telemetry or
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
			-- The last edge was not observed during a long renderer update.
			-- Retry only after the key has been released.
			pending_input = nil
		end
	end

	if telemetry then
		if current_signature ~= last_signature then
			append_sample(frame, telemetry)
			last_signature = current_signature
		end
		capture_progress(telemetry)
		drive_battle(telemetry)
	end
	flush_screenshots()

	if telemetry and telemetry.battle_id == 9 and
			telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 and
			screenshots["round-2"] and
			#screenshot_queue == 0 then
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"battle_id":9,"actual_active_units":%d,"actual_round":%d,"actual_phase":%d,"expected_active_units":8,"expected_round":2,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","cycles":%d,"status":"capture-complete"}',
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
