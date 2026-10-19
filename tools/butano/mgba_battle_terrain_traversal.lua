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

local output_dir = required_env("MGBA_TERRAIN_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_TERRAIN_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_TERRAIN_BATTLE_TELEMETRY_ADDRESS")
))

local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local MOVE_REJECTED = 4

local keys = {
	A = C.GBA_KEY.A,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Up = C.GBA_KEY.UP,
}

local function read_battle()
	if emu:read32(telemetry_address) ~=
			BATTLE_TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id = emu:read32(telemetry_address + 4),
		phase = emu:read32(telemetry_address + 8),
		selected_unit = emu:read32(telemetry_address + 20),
		cursor_x = emu:read32(telemetry_address + 48),
		cursor_y = emu:read32(telemetry_address + 52),
		last_control_error =
			emu:read32(telemetry_address + 56),
		last_player_error =
			emu:read32(telemetry_address + 60),
		script_phase =
			emu:read32(telemetry_address + 148),
	}
end

local frame = 0
local step = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 30
local last_deployment_signature = ""
local rejected_error = 0

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

local function finish(battle)
	assert(battle.battle_id == 41)
	assert(battle.phase == PHASE_COMMAND_SELECTION)
	assert(battle.cursor_x == 4)
	assert(battle.cursor_y == 10)
	assert(rejected_error == MOVE_REJECTED)
	assert(battle.last_control_error == 0)
	emu:screenshot(output_dir .. "/terrain-origin-accepted.png")
	local audit = string.format(
		'{"capture_frame":%d,"battle_id":%d,"battle_phase":%d,"rejected_cursor_x":3,"rejected_cursor_y":9,"rejected_player_error":%d,"accepted_cursor_x":%d,"accepted_cursor_y":%d,"last_control_error":%d,"last_player_error":%d,"status":"terrain-traversal-complete"}',
		frame,
		battle.battle_id,
		battle.phase,
		rejected_error,
		battle.cursor_x,
		battle.cursor_y,
		battle.last_control_error,
		battle.last_player_error
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
	if frame > 1800 then
		emu:screenshot(output_dir .. "/stalled.png")
		assert(false, "terrain traversal route timed out")
	end
	if active_key and frame >= release_frame then
		emu:clearKey(assert(keys[active_key]))
		active_key = nil
		next_press_frame = frame + 12
	end

	local battle = read_battle()
	if not battle or battle.battle_id ~= 41 then
		if step == 0 and press("A") then
			step = 1
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

	if step == 1 and battle.phase == PHASE_UNIT_SELECTION then
		if press("A") then
			step = 2
		end
	elseif step == 2 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 4 and battle.cursor_y == 10 then
		if press("Left") then
			step = 3
		end
	elseif step == 3 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 3 and battle.cursor_y == 10 then
		if press("Up") then
			step = 4
		end
	elseif step == 4 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 3 and battle.cursor_y == 9 then
		if press("A") then
			step = 5
		end
	elseif step == 5 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 3 and battle.cursor_y == 9 and
			battle.last_player_error == MOVE_REJECTED then
		rejected_error = battle.last_player_error
		emu:screenshot(output_dir .. "/class-seven-rejected.png")
		if press("Right") then
			step = 6
		end
	elseif step == 6 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 4 and battle.cursor_y == 9 then
		if press("Down") then
			step = 7
		end
	elseif step == 7 and battle.phase == PHASE_MOVE_SELECTION and
			battle.cursor_x == 4 and battle.cursor_y == 10 then
		if press("A") then
			step = 8
		end
	elseif step == 8 and
			battle.phase == PHASE_COMMAND_SELECTION then
		finish(battle)
	end
end)
