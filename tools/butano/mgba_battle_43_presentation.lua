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
	required_env("MGBA_B43_PRESENTATION_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_B43_PRESENTATION_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_B43_PRESENTATION_TELEMETRY_ADDRESS")
))
local page_audit_path = output_dir .. "/pages.jsonl"
write_file(page_audit_path, "")

local TELEMETRY_MAGIC = 0x4B42544C
local TARGET_BATTLE_ID = 43
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1

local expected_pages = {
	{
		selector = 1, command_index = 2, text_address = 0x0805B6AB,
		p0_id = 1, p0_expression = 0, p0_focused = 0,
		p1_id = 44, p1_expression = 0, p1_focused = 1,
	},
	{
		selector = 1, command_index = 4, text_address = 0x0805B6EC,
		p0_id = 1, p0_expression = 0, p0_focused = 0,
		p1_id = 44, p1_expression = 0, p1_focused = 1,
	},
	{
		selector = 1, command_index = 6, text_address = 0x0805B727,
		p0_id = 1, p0_expression = 0, p0_focused = 0,
		p1_id = 44, p1_expression = 0, p1_focused = 1,
	},
	{
		selector = 1, command_index = 8, text_address = 0x0805B774,
		p0_id = 1, p0_expression = 0, p0_focused = 0,
		p1_id = 44, p1_expression = 0, p1_focused = 1,
	},
	{
		selector = 1, command_index = 11, text_address = 0x0805B7C3,
		p0_id = 1, p0_expression = 4, p0_focused = 1,
		p1_id = 44, p1_expression = 0, p1_focused = 0,
	},
}

local keys = {
	A = C.GBA_KEY.A,
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
		side = emu:read32(telemetry_address + 16),
		selected_unit = emu:read32(telemetry_address + 20),
		scene_frame = emu:read32(telemetry_address + 44),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		script_phase = emu:read32(telemetry_address + 148),
		script_selector = emu:read32(telemetry_address + 152),
		script_command_index = emu:read32(telemetry_address + 156),
		script_text_address = emu:read32(telemetry_address + 160),
		script_message_window_visible =
			emu:read32(telemetry_address + 164),
		portrait_0_visible = emu:read32(telemetry_address + 168),
		portrait_0_focused = emu:read32(telemetry_address + 172),
		portrait_0_id = emu:read32(telemetry_address + 176),
		portrait_0_expression = emu:read32(telemetry_address + 180),
		portrait_0_motion = emu:read32(telemetry_address + 184),
		portrait_1_visible = emu:read32(telemetry_address + 188),
		portrait_1_focused = emu:read32(telemetry_address + 192),
		portrait_1_id = emu:read32(telemetry_address + 196),
		portrait_1_expression = emu:read32(telemetry_address + 200),
		portrait_1_motion = emu:read32(telemetry_address + 204),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local initial_select_issued = false
local deployment_signature = ""
local current_page_signature = ""
local script_page_count = 0
local page_ready_frame = nil
local page_captured = false
local page_press_frame = nil
local unit_selection_ready_frame = nil

local function press(name)
	if active_key or frame < next_press_frame then
		return false
	end
	active_key = assert(keys[name])
	emu:addKey(active_key)
	release_frame = frame + 6
	return true
end

local function drive_deployment(telemetry)
	if telemetry.phase ~= PHASE_DEPLOY_UNIT and
			telemetry.phase ~= PHASE_DEPLOY_START then
		return false
	end
	local signature = string.format(
		"%d:%d:%d",
		telemetry.battle_id,
		telemetry.phase,
		telemetry.selected_unit
	)
	if signature ~= deployment_signature and press("A") then
		deployment_signature = signature
	end
	return true
end

local function observe_script_page(telemetry)
	if telemetry.script_phase ~= SCRIPT_WAIT_FOR_INPUT then
		return
	end
	assert(
		telemetry.script_message_window_visible == 1,
		"script text page has no visible message window"
	)
	assert(
		telemetry.portrait_0_visible == 1 or
			telemetry.portrait_1_visible == 1,
		"script text page has no visible portrait"
	)
	local signature = string.format(
		"%d:%08X:%d",
		telemetry.script_selector,
		telemetry.script_text_address,
		telemetry.script_command_index
	)
	if signature ~= current_page_signature then
		current_page_signature = signature
		script_page_count = script_page_count + 1
		local expected = expected_pages[script_page_count]
		assert(expected, "battle-43 produced too many script pages")
		assert(
			telemetry.script_selector == expected.selector and
				telemetry.script_command_index == expected.command_index and
				telemetry.script_text_address == expected.text_address,
			"battle-43 script page identity mismatch"
		)
		assert(
			telemetry.portrait_0_visible == 1 and
				telemetry.portrait_0_id == expected.p0_id and
				telemetry.portrait_0_expression ==
					expected.p0_expression and
				telemetry.portrait_0_focused ==
					expected.p0_focused and
				telemetry.portrait_1_visible == 1 and
				telemetry.portrait_1_id == expected.p1_id and
				telemetry.portrait_1_expression ==
					expected.p1_expression and
				telemetry.portrait_1_focused ==
					expected.p1_focused,
			"battle-43 structured portrait state mismatch"
		)
		page_ready_frame = frame + 8
		page_captured = false
		page_press_frame = nil
		append_file(
			page_audit_path,
			string.format(
				'{"page":%d,"selector":%d,"command_index":%d,"text_address":"0x%08X","window":%d,"portrait_0":{"visible":%d,"focused":%d,"id":%d,"expression":%d,"motion":%d},"portrait_1":{"visible":%d,"focused":%d,"id":%d,"expression":%d,"motion":%d}}\n',
				script_page_count,
				telemetry.script_selector,
				telemetry.script_command_index,
				telemetry.script_text_address,
				telemetry.script_message_window_visible,
				telemetry.portrait_0_visible,
				telemetry.portrait_0_focused,
				telemetry.portrait_0_id,
				telemetry.portrait_0_expression,
				telemetry.portrait_0_motion,
				telemetry.portrait_1_visible,
				telemetry.portrait_1_focused,
				telemetry.portrait_1_id,
				telemetry.portrait_1_expression,
				telemetry.portrait_1_motion
			)
		)
	end
	if page_ready_frame and frame >= page_ready_frame then
		if not page_captured then
			emu:screenshot(
				output_dir .. "/page-" ..
					tostring(script_page_count) .. ".png"
			)
			page_captured = true
			page_press_frame = frame + 2
		end
	end
	if page_press_frame and frame >= page_press_frame then
		if press("A") then
			page_ready_frame = nil
			page_press_frame = nil
		end
	end
end

local function finish(telemetry)
	assert(
		script_page_count == #expected_pages,
		"battle-43 did not complete all expected script pages"
	)
	assert(telemetry.last_control_error == 0, "controller reported an error")
	assert(telemetry.last_player_error == 0, "player flow reported an error")
	emu:screenshot(output_dir .. "/unit-selection.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scene_frame":%d,"battle_id":%d,"round":%d,"side":%d,"phase":%d,"script_page_count":%d,"last_control_error":%d,"last_player_error":%d,"status":"capture-complete"}',
			frame,
			telemetry.scene_frame,
			telemetry.battle_id,
			telemetry.round,
			telemetry.side,
			telemetry.phase,
			script_page_count,
			telemetry.last_control_error,
			telemetry.last_player_error
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
		emu:clearKey(active_key)
		active_key = nil
		next_press_frame = frame + 3
	end

	if not initial_select_issued and frame >= 30 and press("Select") then
		initial_select_issued = true
	end

	local telemetry = read_telemetry()
	if not telemetry then
		return
	end
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.battle_id ~= TARGET_BATTLE_ID then
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
		assert(false, "battle-43 presentation left the script phase unexpectedly")
	end
end)
