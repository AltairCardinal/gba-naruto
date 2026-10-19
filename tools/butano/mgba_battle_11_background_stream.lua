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

local output_dir = required_env("MGBA_B11_STREAM_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_B11_STREAM_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_B11_STREAM_TELEMETRY_ADDRESS")
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
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local SAME_STATE_RETRY_FRAMES = 15

local keys = {
	A = C.GBA_KEY.A,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Select = C.GBA_KEY.SELECT,
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
		scene_frame = emu:read32(telemetry_address + 44),
		cursor_x = emu:read32(telemetry_address + 48),
		cursor_y = emu:read32(telemetry_address + 52),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		render_stage = emu:read32(telemetry_address + 64),
		presentation_busy = emu:read32(telemetry_address + 68),
		background_chunk_index = emu:read32(telemetry_address + 96),
		background_chunk_count = emu:read32(telemetry_address + 100),
		script_phase = emu:read32(telemetry_address + 148),
		script_command_index = emu:read32(telemetry_address + 156),
	}
end

local function signature(telemetry)
	if not telemetry then
		return "none"
	end
	return string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.round,
		telemetry.selected_unit,
		telemetry.cursor_x,
		telemetry.cursor_y,
		telemetry.background_chunk_index,
		telemetry.script_phase,
		telemetry.script_command_index
	)
end

local function append_sample(frame, telemetry)
	append_file(
		samples_path,
		string.format(
			'{"frame":%d,"battle_id":%d,"phase":%d,"round":%d,"selected_unit":%d,"active_units":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"background_chunk_index":%d,"background_chunk_count":%d,"last_control_error":%d,"last_player_error":%d,"render_stage":%d,"presentation_busy":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","keys":"0x%04X","cycles":%d}\n',
			frame,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.round,
			telemetry.selected_unit,
			telemetry.active_units,
			telemetry.scene_frame,
			telemetry.cursor_x,
			telemetry.cursor_y,
			telemetry.background_chunk_index,
			telemetry.background_chunk_count,
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
local initial_select_sent = false
local active_key = nil
local active_key_name = nil
local release_frame = 0
local last_release_frame = -100
local last_issued_signature = "none"
local last_issue_frame = -100
local stage = "enter-43"
local last_sample_signature = "none"
local screenshots = {}
local screenshot_queue = {}
local observed_initial_chunk = false
local observed_right_chunk = false
local observed_return_chunk = false
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

local function issue_key(name, telemetry)
	if active_key or frame - last_release_frame < 3 then
		return false
	end
	local current_signature = signature(telemetry)
	if current_signature == last_issued_signature and
			frame - last_issue_frame <
					SAME_STATE_RETRY_FRAMES then
		return false
	end
	local key = assert(keys[name])
	emu:addKey(key)
	active_key = key
	active_key_name = name
	release_frame = frame + 6
	last_issued_signature = current_signature
	last_issue_frame = frame
	append_file(
		inputs_path,
		string.format(
			'{"frame":%d,"event":"press","key":"%s","stage":"%s","battle_id":%d,"phase":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"chunk":%d}\n',
			frame,
			name,
			stage,
			telemetry and telemetry.battle_id or -1,
			telemetry and telemetry.phase or -1,
			telemetry and telemetry.scene_frame or -1,
			telemetry and telemetry.cursor_x or -1,
			telemetry and telemetry.cursor_y or -1,
			telemetry and
				telemetry.background_chunk_index or -1
		)
	)
	return true
end

local function drive_deployment(telemetry)
	if telemetry.phase == PHASE_DEPLOY_UNIT or
			telemetry.phase == PHASE_DEPLOY_START then
		issue_key("A", telemetry)
		return true
	end
	return false
end

local function advance_fixture(next_stage, telemetry)
	stage = next_stage
	issue_key("Select", telemetry)
end

local function drive_route(telemetry)
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		stage = "advance-script"
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			issue_key("A", telemetry)
		end
		return
	end
	if telemetry.battle_id == 43 then
		advance_fixture("enter-9", telemetry)
		return
	end
	if telemetry.battle_id == 9 then
		advance_fixture("enter-11", telemetry)
		return
	end
	if telemetry.battle_id ~= 11 then
		return
	end
	assert(
		telemetry.background_chunk_count == 2,
		"battle 11 must expose two background chunks"
	)
	assert(
		telemetry.last_control_error == 0,
		"battle 11 controller rejected stream route input"
	)
	assert(
		telemetry.last_player_error == 0,
		"battle 11 player flow failed during stream route"
	)

	if telemetry.phase == PHASE_UNIT_SELECTION then
		stage = "scroll-right"
		if telemetry.background_chunk_index == 0 then
			observed_initial_chunk = true
			queue_screenshot(
				"chunk-0",
				"battle-11-chunk-0.png"
			)
			issue_key("A", telemetry)
		end
		return
	end
	if telemetry.phase ~= PHASE_MOVE_SELECTION then
		return
	end

	if not observed_right_chunk then
		if telemetry.background_chunk_index == 1 then
			observed_right_chunk = true
			stage = "scroll-left"
			queue_screenshot(
				"chunk-1",
				"battle-11-chunk-1.png"
			)
		elseif telemetry.cursor_x < 13 then
			issue_key("Right", telemetry)
		end
		return
	end

	if telemetry.cursor_x > 4 then
		issue_key("Left", telemetry)
		return
	end
	if telemetry.background_chunk_index == 0 and
			not observed_return_chunk then
		observed_return_chunk = true
		stage = "complete"
		queue_screenshot(
			"chunk-0-return",
			"battle-11-chunk-0-return.png"
		)
		completion_frame = frame + 8
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

	if not initial_select_sent and frame >= 30 and
			not active_key then
		local key = keys.Select
		emu:addKey(key)
		active_key = key
		active_key_name = "Select"
		release_frame = frame + 6
		last_issued_signature = "initial-select"
		last_issue_frame = frame
		initial_select_sent = true
		append_file(
			inputs_path,
			string.format(
				'{"frame":%d,"event":"press","key":"Select","stage":"enter-43"}\n',
				frame
			)
		)
	elseif telemetry and not active_key then
		drive_route(telemetry)
	end

	flush_screenshots()
	if completion_frame and frame >= completion_frame and
			#screenshot_queue == 0 then
		assert(observed_initial_chunk)
		assert(observed_right_chunk)
		assert(observed_return_chunk)
		assert(telemetry and telemetry.battle_id == 11)
		assert(telemetry.background_chunk_index == 0)
		assert(telemetry.cursor_x == 4)
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"battle_id":11,"active_units":%d,"round":%d,"phase":%d,"cursor_x":%d,"cursor_y":%d,"background_chunk_count":%d,"observed_chunks":[0,1,0],"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","cycles":%d,"status":"capture-complete"}',
				frame,
				telemetry.active_units,
				telemetry.round,
				telemetry.phase,
				telemetry.cursor_x,
				telemetry.cursor_y,
				telemetry.background_chunk_count,
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

	assert(frame < 3600, "battle 11 background stream route timed out")
end)
