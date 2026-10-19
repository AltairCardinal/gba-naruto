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
	required_env("MGBA_BATTLE_RESULT_ROUTING_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_BATTLE_RESULT_ROUTING_DONE_MARKER")
local telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_RESULT_ROUTING_TELEMETRY_ADDRESS"
)))

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1
local PHASE_SCRIPT_BLOCKED = 18
local SCRIPT_WAIT_FOR_INPUT = 1

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
		selected_unit = emu:read32(telemetry_address + 20),
		scene_frame = emu:read32(telemetry_address + 44),
		last_control_error = emu:read32(telemetry_address + 56),
		last_player_error = emu:read32(telemetry_address + 60),
		script_phase = emu:read32(telemetry_address + 148),
	}
end

local frame = 0
local complete = false
local active_key = nil
local release_frame = 0
local next_press_frame = 0
local preparation_confirmed = false
local last_deployment_signature = ""
local unit_selection_ready_frame = nil
local verification_frame = nil
local battle_id_before_select = nil
local phase_before_select = nil

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

local function finish(telemetry)
	assert(
		telemetry.battle_id == battle_id_before_select,
		"SELECT changed the active battle"
	)
	assert(
		telemetry.phase == phase_before_select,
		"SELECT changed the battle phase"
	)
	assert(telemetry.round == 1, "SELECT advanced the battle round")
	assert(
		telemetry.last_control_error == 0,
		"controller reported an error"
	)
	assert(
		telemetry.last_player_error == 0,
		"player flow reported an error"
	)
	emu:screenshot(output_dir .. "/select-retained-battle.png")
	write_file(
		output_dir .. "/audit.json",
		string.format(
			'{"capture_frame":%d,"scene_frame":%d,"battle_id_before_select":%d,"battle_id_after_select":%d,"phase_before_select":%d,"phase_after_select":%d,"round":%d,"last_control_error":%d,"last_player_error":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"select-does-not-route"}',
			frame,
			telemetry.scene_frame,
			battle_id_before_select,
			telemetry.battle_id,
			phase_before_select,
			telemetry.phase,
			telemetry.round,
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
			'{"capture_frame":%d,"status":"select-does-not-route"}',
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
		if not preparation_confirmed and
				frame >= 30 and press("A") then
			preparation_confirmed = true
		end
		return
	end
	if drive_deployment(telemetry) then
		return
	end
	if telemetry.phase == PHASE_SCRIPT_BLOCKED then
		if telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT then
			press("A")
		end
		return
	end
	if telemetry.phase ~= PHASE_UNIT_SELECTION then
		return
	end
	if not unit_selection_ready_frame then
		unit_selection_ready_frame = frame + 10
		return
	end
	if not verification_frame and
			frame >= unit_selection_ready_frame and
			press("Select") then
		battle_id_before_select = telemetry.battle_id
		phase_before_select = telemetry.phase
		verification_frame = frame + 30
		return
	end
	if verification_frame and
			frame >= verification_frame and
			not active_key then
		finish(telemetry)
	end
end)
