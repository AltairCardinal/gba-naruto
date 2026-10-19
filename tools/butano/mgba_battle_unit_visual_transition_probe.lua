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
	required_env("MGBA_UNIT_VISUAL_PROBE_OUTPUT_DIR")
local done_marker_path =
	required_env("MGBA_UNIT_VISUAL_PROBE_DONE_MARKER")
local telemetry_address = assert(parse_number(
	required_env("MGBA_UNIT_VISUAL_PROBE_TELEMETRY_ADDRESS")
))

local TELEMETRY_MAGIC = 0x4B42544C
local PHASE_DEPLOY_UNIT = 0xFFFFFFFE
local PHASE_DEPLOY_START = 0xFFFFFFFD
local PHASE_UNIT_SELECTION = 1

local frame = 0
local active_key = nil
local release_frame = 0
local next_bootstrap_select_frame = 30
local transition_frame = nil
local complete = false

local function read_telemetry()
	if emu:read32(telemetry_address) ~= TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id = emu:read32(telemetry_address + 4),
		phase = emu:read32(telemetry_address + 8),
		round = emu:read32(telemetry_address + 12),
		selected_unit = emu:read32(telemetry_address + 20),
		selected_character_id =
			emu:read32(telemetry_address + 72),
	}
end

local function press(key)
	if active_key then
		return false
	end
	active_key = key
	emu:addKey(key)
	release_frame = frame + 6
	return true
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if active_key and frame >= release_frame then
		emu:clearKey(active_key)
		active_key = nil
	end

	local telemetry = read_telemetry()
	if not transition_frame then
		if not telemetry and
				frame >= next_bootstrap_select_frame and
				not active_key then
			press(C.GBA_KEY.SELECT)
			next_bootstrap_select_frame = frame + 60
		elseif telemetry and not active_key then
			if telemetry.phase == PHASE_DEPLOY_UNIT or
					telemetry.phase == PHASE_DEPLOY_START then
				press(C.GBA_KEY.A)
			elseif telemetry.battle_id == 43 and
					telemetry.phase == PHASE_UNIT_SELECTION then
				emu:screenshot(
					output_dir ..
						"/scenario-43-before-select.png"
				)
				press(C.GBA_KEY.SELECT)
				transition_frame = frame
			end
		end
	elseif frame >= transition_frame + 60 then
		emu:screenshot(output_dir .. "/after-select.png")
		local current = read_telemetry()
		write_file(
			output_dir .. "/audit.json",
			string.format(
				'{"capture_frame":%d,"telemetry_magic":"0x%08X","battle_id":%d,"phase":%d,"round":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"capture-complete"}',
				frame,
				emu:read32(telemetry_address),
				current and current.battle_id or -1,
				current and current.phase or -1,
				current and current.round or -1,
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
end)

