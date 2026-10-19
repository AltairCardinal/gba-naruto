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

local output_dir =
	required_env("MGBA_B41_PRESENTATION_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_B41_PRESENTATION_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_B41_PRESENTATION_TELEMETRY_ADDRESS")
))

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1

local expected_text_addresses = {
	0x0805B2C0,
	0x0805B2EC,
	0x0805B327,
	0x0805B37E,
	0x0805B3CB,
}

local keys = {
	A = C.GBA_KEY.A,
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
		scene_frame = emu:read32(telemetry_address + 44),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		script_phase = emu:read32(telemetry_address + 148),
		script_selector = emu:read32(telemetry_address + 152),
		script_command_index = emu:read32(telemetry_address + 156),
		script_text_address = emu:read32(telemetry_address + 160),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local last_deployment_signature = ""
local script_page_count = 0
local current_text_address = 0
local page_ready_frame = nil
local page_captured = false
local page_advance_deadline = nil
local unit_selection_ready_frame = nil

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
		"%d:%d", telemetry.phase, telemetry.selected_unit
	)
	if signature ~= last_deployment_signature and press("A") then
		last_deployment_signature = signature
	end
	return true
end

local function observe_script_page(telemetry)
	assert(telemetry.round == 1, "presentation started outside round 1")
	assert(telemetry.side == 0, "presentation started outside player side")
	assert(telemetry.script_selector == 1, "unexpected selector")
	assert(
		telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT,
		"script is not waiting for page input"
	)

	if telemetry.script_text_address ~= current_text_address then
		local expected =
			expected_text_addresses[script_page_count + 1]
		assert(expected, "presentation produced too many text pages")
		assert(
			telemetry.script_text_address == expected,
			string.format(
				"page %d address mismatch: 0x%08X",
				script_page_count + 1,
				telemetry.script_text_address
			)
		)
		current_text_address = telemetry.script_text_address
		script_page_count = script_page_count + 1
		page_ready_frame = frame + 3
		page_captured = false
		page_advance_deadline = nil
	end

	if page_advance_deadline and frame >= page_advance_deadline then
		emu:screenshot(output_dir .. "/stalled-page.png")
		write_file(
			output_dir .. "/stalled-page.json",
			string.format(
				'{"capture_frame":%d,"scene_frame":%d,"phase":%d,"script_page_count":%d,"script_phase":%d,"script_command_index":%d,"script_text_address":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"page-advance-stalled"}',
				frame,
				telemetry.scene_frame,
				telemetry.phase,
				script_page_count,
				telemetry.script_phase,
				telemetry.script_command_index,
				telemetry.script_text_address,
				emu:readRegister("pc"),
				emu:readRegister("lr"),
				emu:readRegister("sp")
			)
		)
		complete = true
		return
	end

	if page_ready_frame and frame >= page_ready_frame then
		if not page_captured then
			emu:screenshot(
				output_dir .. "/page-" ..
					tostring(script_page_count) .. ".png"
			)
			page_captured = true
		end
		if press("A") then
			page_ready_frame = nil
			page_advance_deadline = frame + 30
		end
	end
end

local function finish(telemetry)
	assert(script_page_count == 5, "unit selection reached before five pages")
	assert(telemetry.round == 1, "unit selection reached outside round 1")
	assert(telemetry.side == 0, "unit selection reached outside player side")
	assert(telemetry.last_control_error == 0, "controller reported an error")
	assert(telemetry.last_player_error == 0, "player flow reported an error")
	emu:screenshot(output_dir .. "/unit-selection.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scene_frame":%d,"battle_id":%d,"round":%d,"side":%d,"phase":%d,"script_page_count":%d,"script_phase":%d,"script_selector":%d,"script_command_index":%d,"script_text_address":"0x%08X","last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"capture-complete"}',
			frame,
			telemetry.scene_frame,
			telemetry.battle_id,
			telemetry.round,
			telemetry.side,
			telemetry.phase,
			script_page_count,
			telemetry.script_phase,
			telemetry.script_selector,
			telemetry.script_command_index,
			telemetry.script_text_address,
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
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		observe_script_page(telemetry)
	elseif telemetry.phase == PHASE_UNIT_SELECTION then
		if not unit_selection_ready_frame then
			unit_selection_ready_frame = frame + 3
		elseif frame >= unit_selection_ready_frame then
			finish(telemetry)
		end
	elseif script_page_count > 0 then
		assert(false, "presentation left the script phase unexpectedly")
	end
end)
