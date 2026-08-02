local input_state = assert(os.getenv("AI_OBSERVER_INPUT_STATE"))
local output_state = assert(os.getenv("AI_OBSERVER_OUTPUT_STATE"))
local output_png = assert(os.getenv("AI_OBSERVER_OUTPUT_PNG"))
local audit_path = assert(os.getenv("AI_OBSERVER_AUDIT"))
local done_path = assert(os.getenv("AI_OBSERVER_DONE"))
local run_id = assert(os.getenv("AI_OBSERVER_RUN_ID"))
local rom_sha256 = assert(os.getenv("AI_OBSERVER_ROM_SHA256"))
local input_state_sha256 = assert(os.getenv("AI_OBSERVER_INPUT_STATE_SHA256"))
local script_sha256 = assert(os.getenv("AI_OBSERVER_SCRIPT_SHA256"))
local skip_action_ids_text = assert(os.getenv("AI_OBSERVER_SKIP_ACTION_IDS"))
local input_schedule = assert(os.getenv("AI_OBSERVER_INPUT_SCHEDULE"))

-- 0x0807A22A stores candidate[r7+0x0C] to runtime[r4+0x770].  Break at the
-- following instruction so both the source register and destination byte are current.
local runtime_copy_address = 0x0807A22C
local capture_frame_limit = 1800
local frame = 0
local selection = nil
local events = {}
local skipped_action_ids = {}
local input_events = {}
local complete = false
local breakpoint_id = nil

local function q(value)
	return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function write(path, payload)
	local file = assert(io.open(path, "w"))
	file:write(payload)
	file:close()
end

local function hex(value)
	return string.format("0x%08X", value or 0)
end

for value in skip_action_ids_text:gmatch("[^,]+") do
	local action_id = assert(tonumber(value))
	skipped_action_ids[action_id] = true
end

local key_map = {
	Down = C.GBA_KEY.DOWN, A = C.GBA_KEY.A, B = C.GBA_KEY.B,
	L = C.GBA_KEY.L, R = C.GBA_KEY.R, Up = C.GBA_KEY.UP,
	Right = C.GBA_KEY.RIGHT, Left = C.GBA_KEY.LEFT,
	Start = C.GBA_KEY.START,
}

for value in input_schedule:gmatch("[^,]+") do
	local key, down_frame, up_frame = value:match("^([^:]+):(%d+):(%d+)$")
	assert(key and key_map[key])
	table.insert(input_events, {
		key = key,
		key_code = key_map[key],
		down_frame = assert(tonumber(down_frame)),
		up_frame = assert(tonumber(up_frame)),
	})
end

local function input_events_json()
	local values = {}
	for index, event in ipairs(input_events) do
		values[index] = table.concat({
			'{"key":', q(event.key),
			',"down_frame":', tostring(event.down_frame),
			',"up_frame":', tostring(event.up_frame),
			',"hold_frames":', tostring(event.up_frame - event.down_frame), '}'
		})
	end
	return "[" .. table.concat(values, ",") .. "]"
end

local function skipped_action_ids_json()
	local values = {}
	for action_id in pairs(skipped_action_ids) do table.insert(values, action_id) end
	table.sort(values)
	for index, action_id in ipairs(values) do values[index] = tostring(action_id) end
	return "[" .. table.concat(values, ",") .. "]"
end

local function event_json(event)
	return table.concat({
		'{"address":', q(hex(runtime_copy_address)),
		',"cycle":', q(event.cycle),
		',"runtime_pointer":', q(hex(event.runtime_pointer)),
		',"action_address":', q(hex(event.action_address)),
		',"action_id":', tostring(event.action_id),
		',"candidate_pointer":', q(hex(event.candidate_pointer)),
		',"source_action_address":', q(hex(event.source_action_address)),
		',"source_action_id":', tostring(event.source_action_id),
		',"r5":', q(hex(event.r5)), '}'
	})
end

local function events_json()
	local values = {}
	for index, event in ipairs(events) do values[index] = event_json(event) end
	return "[" .. table.concat(values, ",") .. "]"
end

local function selection_json()
	if not selection then return "null" end
	return event_json(selection)
end

local function finish()
	if complete then return end
	complete = true
	emu:setKeys(0)
	if breakpoint_id then emu:clearBreakpoint(breakpoint_id) end
	assert(emu:saveStateFile(output_state))
	emu:screenshot(output_png)
	write(audit_path, table.concat({
		'{"schema":"battle-ai-action-observer-v4"',
		',"run_id":', q(run_id),
		',"frame":', tostring(frame),
		',"capture_frame_limit":1800',
		',"rom_sha256":', q(rom_sha256),
		',"input_state_sha256":', q(input_state_sha256),
		',"script_sha256":', q(script_sha256),
		',"inputs":', input_events_json(),
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"skipped_action_ids":', skipped_action_ids_json(),
		',"events":', events_json(),
		',"selection":', selection_json(), '}'
	}))
	write(done_path, '{"run_id":' .. q(run_id) .. ',"status":"observer-complete"}')
end

assert(emu:loadStateFile(input_state))
emu:setKeys(0)
breakpoint_id = assert(emu:setBreakpoint(function()
	if selection then return end
	local runtime_pointer = emu:readRegister("r4") or 0
	local action_address = runtime_pointer + 0x770
	local candidate_pointer = emu:readRegister("r7") or 0
	local event = {
		cycle = tostring(emu:currentCycle()),
		runtime_pointer = runtime_pointer,
		action_address = action_address,
		action_id = emu:read8(action_address),
		candidate_pointer = candidate_pointer,
		source_action_address = candidate_pointer + 0x0C,
		source_action_id = (emu:readRegister("r1") or 0) % 256,
		r5 = emu:readRegister("r5") or 0,
	}
	table.insert(events, event)
	if not skipped_action_ids[event.action_id] then selection = event end
end, runtime_copy_address))

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	for _, event in ipairs(input_events) do
		if frame == event.down_frame then emu:addKey(event.key_code) end
		if frame == event.up_frame then emu:clearKey(event.key_code) end
	end
	if selection or frame >= capture_frame_limit then finish() end
end)
