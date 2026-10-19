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

local output_dir = required_env("MGBA_OBJECT_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_OBJECT_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_OBJECT_TELEMETRY_ADDRESS")
))

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_MOVE_SELECTION = 2
local PHASE_COMMAND_SELECTION = 3
local PHASE_ACTION_SELECTION = 6
local PHASE_TARGET_SELECTION = 8
local PHASE_FACING_SELECTION = 9
local PHASE_DEFENSE_DECISION = 10
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1
local ACTION_KIND_NINJA_TOOL = 1
local COMMAND_END_ACTION = 5

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
		selected_command = emu:read32(telemetry_address + 32),
		scene_frame = emu:read32(telemetry_address + 44),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		presentation_busy = emu:read32(telemetry_address + 68),
		action_count = emu:read32(telemetry_address + 76),
		action_index = emu:read32(telemetry_address + 80),
		selected_action_id = emu:read32(telemetry_address + 84),
		last_resolved_action_id = emu:read32(telemetry_address + 92),
		selected_action_kind = emu:read32(telemetry_address + 104),
		script_phase = emu:read32(telemetry_address + 148),
		object_count = emu:read32(telemetry_address + 284),
		presentation_object = emu:read32(telemetry_address + 288),
		presentation_object_kind = emu:read32(telemetry_address + 292),
		presentation_object_slot = emu:read32(telemetry_address + 296),
		presentation_object_damage = emu:read32(telemetry_address + 300),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local last_deployment_signature = ""
local step = 0
local object_observed = false
local route_start_frame = nil
local last_trace_signature = ""
local trace = assert(io.open(output_dir .. "/trace.log", "w"))

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
	assert(object_observed, "expiry happened before object observation")
	assert(telemetry.object_count == 0, "expired object was not freed")
	assert(telemetry.presentation_object == 1)
	assert(telemetry.presentation_object_kind == 2)
	assert(telemetry.presentation_object_slot == 1)
	assert(telemetry.presentation_object_damage == 0)
	assert(telemetry.presentation_busy == 1)
	assert(telemetry.last_control_error == 0)
	assert(telemetry.last_player_error == 0)
	emu:screenshot(output_dir .. "/type-2-expiry.png")
	local audit = string.format(
		'{"capture_frame":%d,"scene_frame":%d,"battle_id":%d,' ..
		'"round":%d,"object_count":%d,"object_kind":%d,' ..
		'"object_slot":%d,"object_damage":%d,' ..
		'"last_control_error":%d,"last_player_error":%d,' ..
		'"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X",' ..
		'"status":"capture-complete"}',
		frame,
		telemetry.scene_frame,
		telemetry.battle_id,
		telemetry.round,
		telemetry.object_count,
		telemetry.presentation_object_kind,
		telemetry.presentation_object_slot,
		telemetry.presentation_object_damage,
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
	if route_start_frame and frame - route_start_frame > 1600 then
		emu:screenshot(output_dir .. "/stalled.png")
		write_file(
			output_dir .. "/stalled.json",
			string.format(
				'{"frame":%d,"step":%d,"phase":%d,' ..
				'"round":%d,"object_count":%d,' ..
				'"presentation_busy":%d,"presentation_object":%d,' ..
				'"last_control_error":%d,"last_player_error":%d}',
				frame,
				step,
				telemetry.phase,
				telemetry.round,
				telemetry.object_count,
				telemetry.presentation_busy,
				telemetry.presentation_object,
				telemetry.last_control_error,
				telemetry.last_player_error
			)
		)
		assert(false, "type-2 battlefield object route timed out")
	end
	if drive_deployment(telemetry) then
		return
	end
	local trace_signature = string.format(
		"%d:%d:%d:%d:%d:%d:%d",
		step,
		telemetry.phase,
		telemetry.round,
		telemetry.object_count,
		telemetry.presentation_busy,
		telemetry.presentation_object,
		telemetry.last_resolved_action_id
	)
	if trace_signature ~= last_trace_signature then
		trace:write(
			string.format(
				"%d %s command=%d action=%d/%d:%d error=%d/%d\n",
				frame,
				trace_signature,
				telemetry.selected_command,
				telemetry.action_index,
				telemetry.action_count,
				telemetry.selected_action_id,
				telemetry.last_control_error,
				telemetry.last_player_error
			)
		)
		trace:flush()
		last_trace_signature = trace_signature
	end
	if telemetry.presentation_object == 1 and
			telemetry.presentation_object_kind == 2 then
		finish(telemetry)
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
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
	elseif step == 1 and telemetry.phase == PHASE_MOVE_SELECTION then
		if press("A") then
			step = 2
		end
	elseif step == 2 and telemetry.phase == PHASE_COMMAND_SELECTION then
		if press("A") then
			step = 3
		end
	elseif step == 3 and telemetry.phase == PHASE_ACTION_SELECTION then
		if telemetry.selected_action_id == 37 and
			telemetry.selected_action_kind == ACTION_KIND_NINJA_TOOL then
			if press("A") then
				step = 4
			end
		else
			press("Down")
		end
	elseif step == 4 and telemetry.phase == PHASE_TARGET_SELECTION then
		if press("Up") then
			step = 5
		end
	elseif step == 5 and telemetry.phase == PHASE_TARGET_SELECTION then
		if press("A") then
			step = 6
		end
	elseif step == 6 and telemetry.phase == PHASE_FACING_SELECTION then
		assert(telemetry.object_count == 1)
		object_observed = true
		if press("A") then
			step = 7
		end
	elseif step == 7 and telemetry.phase == PHASE_DEFENSE_DECISION then
		assert(telemetry.object_count == 1)
		if press("A") then
			step = 8
		end
	elseif step == 8 and telemetry.round >= 2 and
			telemetry.phase == PHASE_UNIT_SELECTION then
		if press("A") then
			step = 9
		end
	elseif step == 9 and telemetry.phase == PHASE_MOVE_SELECTION then
		if press("A") then
			step = 10
		end
	elseif step == 10 and telemetry.phase == PHASE_COMMAND_SELECTION then
		if telemetry.selected_command == COMMAND_END_ACTION then
			if press("A") then
				step = 11
			end
		else
			press("Down")
		end
	elseif step == 11 and telemetry.phase == PHASE_FACING_SELECTION then
		if press("A") then
			step = 12
		end
	elseif step == 12 and telemetry.phase == PHASE_DEFENSE_DECISION then
		if press("A") then
			step = 13
		end
	end
end)
