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

local output_dir = required_env("MGBA_S43_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_S43_DONE_MARKER")
local telemetry_address =
	assert(parse_number(required_env("MGBA_S43_TELEMETRY_ADDRESS")))
local register_samples_path = output_dir .. "/register-samples.jsonl"
write_file(register_samples_path, "")

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_ENEMY_TURN = 12
local keys = {
	A = C.GBA_KEY.A,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
	Select = C.GBA_KEY.SELECT,
}

-- These inputs select the clone ability through the real command and action
-- browsers. Captures and completion are controller-state-driven below.
local presses = {
	{ 30, "Select" },
	{ 120, "A" },
	{ 150, "A" },
	{ 180, "A" },
	{ 210, "Down" },
	{ 240, "Down" },
	{ 270, "A" },
	{ 300, "Up" },
	{ 330, "A" },
	{ 600, "A" },
	{ 660, "A" },
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
		"%d:%d:%d:%d:%d:%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.round,
		telemetry.selected_unit,
		telemetry.active_units,
		telemetry.player_completed,
		telemetry.enemy_completed,
		telemetry.presentation_busy
	)
end

local function append_sample(frame, telemetry)
	append_file(
		register_samples_path,
		string.format(
			'{"frame":%d,"battle_id":%d,"phase":%d,"round":%d,"selected_unit":%d,"active_units":%d,"unit_count":%d,"player_completed":%d,"enemy_completed":%d,"scene_frame":%d,"cursor_x":%d,"cursor_y":%d,"last_control_error":%d,"last_player_error":%d,"render_stage":%d,"presentation_busy":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","keys":"0x%04X","cycles":%d}\n',
			frame,
			telemetry.battle_id,
			telemetry.phase,
			telemetry.round,
			telemetry.selected_unit,
			telemetry.active_units,
			telemetry.unit_count,
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
local last_signature = "none"
local screenshots = {}
local screenshot_queue = {}
local deployment_key_active = false
local deployment_key_release = 0
local deployment_next_press_frame = 0
local last_deployment_signature = "none"

local function capture_once(key, name)
	if screenshots[key] then
		return
	end
	emu:screenshot(output_dir .. "/" .. name)
	screenshots[key] = true
end

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

local function capture_progress(telemetry)
	if telemetry.battle_id ~= 43 then
		return
	end
	if telemetry.phase == PHASE_DEPLOY_UNIT and
			telemetry.selected_unit == 1 then
		capture_once(
			"deployment-unit-1",
			"deployment-unit-1.png"
		)
	end
	if telemetry.phase == PHASE_DEPLOY_START then
		capture_once(
			"deployment-start",
			"deployment-start.png"
		)
	end
	if telemetry.round == 1 and
			telemetry.active_units == 4 then
		capture_once("formation", "formation.png")
	end
	if telemetry.active_units == 5 then
		capture_once("clone", "clone-created.png")
	end
	if telemetry.phase == PHASE_ENEMY_TURN then
		if telemetry.enemy_completed >= 1 then
			capture_once("enemy-1", "enemy-unit-1-complete.png")
		end
		if telemetry.enemy_completed >= 2 then
			capture_once("enemy-2", "enemy-unit-2-complete.png")
		end
		if telemetry.enemy_completed >= 3 then
			capture_once("enemy-3", "enemy-unit-3-complete.png")
		end
	end
	-- The controller resets completion flags when the final enemy advances
	-- the round, while its presentation is still active.
	if telemetry.round >= 2 and
			telemetry.presentation_busy == 1 then
		capture_once("enemy-3", "enemy-unit-3-complete.png")
	end
	if telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 then
		queue_screenshot("round-2", "round-2-player.png")
	end
end

local function deployment_signature(telemetry)
	return string.format(
		"%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.selected_unit
	)
end

local function drive_deployment(telemetry)
	if telemetry.phase ~= PHASE_DEPLOY_UNIT and
			telemetry.phase ~= PHASE_DEPLOY_START then
		return
	end
	local current = deployment_signature(telemetry)
	if deployment_key_active or
			frame < deployment_next_press_frame or
			current == last_deployment_signature then
		return
	end
	emu:addKey(keys.A)
	deployment_key_active = true
	deployment_key_release = frame + 8
	last_deployment_signature = current
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if deployment_key_active and
			frame >= deployment_key_release then
		emu:clearKey(keys.A)
		deployment_key_active = false
		deployment_next_press_frame = frame + 3
	end
	for _, press in ipairs(presses) do
		local key = assert(keys[press[2]])
		if frame == press[1] then
			emu:addKey(key)
		elseif frame == press[1] + 8 then
			emu:clearKey(key)
		end
	end

	local telemetry = read_telemetry()
	local current_signature = signature(telemetry)
	if telemetry and current_signature ~= last_signature then
		append_sample(frame, telemetry)
		last_signature = current_signature
	end
	if telemetry then
		capture_progress(telemetry)
		drive_deployment(telemetry)
	end
	flush_screenshots()

	if telemetry and telemetry.battle_id == 43 and
			telemetry.active_units == 5 and
			telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION and
			telemetry.presentation_busy == 0 and
			screenshots["formation"] and
			screenshots["clone"] and
			screenshots["enemy-1"] and
			screenshots["enemy-2"] and
			screenshots["enemy-3"] and
			screenshots["round-2"] and
			#screenshot_queue == 0 then
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"scenario":43,"actual_active_units":%d,"actual_round":%d,"actual_phase":%d,"expected_active_units":5,"expected_round":2,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","cycles":%d,"status":"capture-complete"}',
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
