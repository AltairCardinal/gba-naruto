local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local input_state =
	required_env("MGBA_ORIGINAL_BATTLE_PROBE_INPUT_STATE")
local input_state_sha256 =
	required_env("MGBA_ORIGINAL_BATTLE_PROBE_INPUT_STATE_SHA256")
local output_path =
	required_env("MGBA_ORIGINAL_BATTLE_PROBE_OUTPUT")
local done_marker =
	required_env("MGBA_ORIGINAL_BATTLE_PROBE_DONE_MARKER")

local UNIT_POOL_BASE = 0x020240C0
local UNIT_STRIDE = 0x01D4
local BATTLE_CONTROL_BASE = 0x02026804
local SLOT_COUNT = 13

assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local complete = false

local function unit_json(slot)
	local address = UNIT_POOL_BASE + slot * UNIT_STRIDE
	return string.format(
		'{"slot":%d,"character_id":%d,"affiliation":%d,' ..
		'"current_hp":%d,"maximum_hp":%d,' ..
		'"position_x":%d,"position_y":%d,"state_word":%u}',
		slot,
		emu:read8(address),
		emu:read8(address + 0xCC),
		emu:read16(address + 0x0C),
		emu:read16(address + 0x0E),
		emu:read8(address + 0xC4),
		emu:read8(address + 0xC5),
		emu:read32(address + 0xC0)
	)
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < 30 then
		return
	end

	local units = {}
	for slot = 0, SLOT_COUNT - 1 do
		units[#units + 1] = unit_json(slot)
	end
	local battle_control = {}
	for offset = 0, 15 do
		battle_control[#battle_control + 1] = string.format(
			"%02X",
			emu:read8(BATTLE_CONTROL_BASE + offset)
		)
	end
	local payload = string.format(
		'{"status":"probe-complete","input_state_sha256":"%s",' ..
		'"battle_control_hex":"%s","units":[%s]}',
		input_state_sha256,
		table.concat(battle_control),
		table.concat(units, ",")
	)
	write_file(output_path, payload)
	write_file(done_marker, payload)
	complete = true
end)
