local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function json_escape(value)
	return (value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"))
end

local function quoted(value)
	return '"' .. json_escape(value) .. '"'
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local input_state = required_env("MGBA_REPLAY_INPUT_STATE")
local output_state = required_env("MGBA_REPLAY_OUTPUT_STATE")
local output_png = required_env("MGBA_REPLAY_OUTPUT_PNG")
local audit_path = required_env("MGBA_REPLAY_AUDIT")
local sentinel_path = required_env("MGBA_REPLAY_SENTINEL")
local done_marker_path = required_env("MGBA_REPLAY_DONE_MARKER")
local capture_frame = assert(tonumber(required_env("MGBA_REPLAY_CAPTURE_FRAME")))
local run_id = required_env("MGBA_REPLAY_RUN_ID")
local rom_sha256 = required_env("MGBA_REPLAY_ROM_SHA256")
local input_state_sha256 = required_env("MGBA_REPLAY_INPUT_STATE_SHA256")
local schedule_text = required_env("MGBA_INPUT_SEQUENCE_SCHEDULE")
local keys = {
	Down = C.GBA_KEY.DOWN,
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	L = C.GBA_KEY.L,
	R = C.GBA_KEY.R,
	Up = C.GBA_KEY.UP,
	Right = C.GBA_KEY.RIGHT,
	Left = C.GBA_KEY.LEFT,
	Start = C.GBA_KEY.START,
}

local events = {}
local previous_up = 0
for encoded in schedule_text:gmatch("([^,]+)") do
	local key_name, down_text, up_text = encoded:match("^([A-Za-z]+):(%d+):(%d+)$")
	assert(key_name and down_text and up_text, "invalid input schedule event")
	local key = assert(keys[key_name], "invalid input schedule key")
	local down_frame = assert(tonumber(down_text))
	local up_frame = assert(tonumber(up_text))
	assert(down_frame > 0 and down_frame < up_frame, "invalid input interval")
	assert(down_frame >= previous_up, "input intervals overlap")
	assert(up_frame < capture_frame, "input interval exceeds capture frame")
	table.insert(events, {
		key_name = key_name,
		key = key,
		down_frame = down_frame,
		up_frame = up_frame,
	})
	previous_up = up_frame
end
assert(#events > 0, "input schedule must not be empty")

local function inputs_json()
	local rows = {}
	for _, event in ipairs(events) do
		table.insert(rows, table.concat({
			'{"key":', quoted(event.key_name),
			',"down_frame":', tostring(event.down_frame),
			',"up_frame":', tostring(event.up_frame),
			',"hold_frames":', tostring(event.up_frame - event.down_frame),
			'}',
		}))
	end
	return '[' .. table.concat(rows, ',') .. ']'
end

assert(capture_frame > 0 and capture_frame == math.floor(capture_frame), "invalid capture frame")
assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local capture_complete = false
callbacks:add("frame", function()
	if capture_complete then
		return
	end
	frame = frame + 1
	for _, event in ipairs(events) do
		if frame == event.down_frame then
			emu:addKey(event.key)
		elseif frame == event.up_frame then
			emu:clearKey(event.key)
		end
	end
	if frame == capture_frame then
		assert(emu:saveStateFile(output_state), "failed to save output state")
		emu:screenshot(output_png)
		local payload = table.concat({
			'{"run_id":', quoted(run_id),
			',"frame":', tostring(frame),
			',"capture_frame":', tostring(capture_frame),
			',"inputs":', inputs_json(),
			',"automatic_inputs":[]',
			',"recovery_inputs":[]',
			',"evidence_mode":"input-sequence"',
			',"zero_input_verified":false',
			',"success":true',
			',"status":"capture-complete"',
			',"input_state":', quoted(input_state),
			',"output_state":', quoted(output_state),
			',"output_png":', quoted(output_png),
			',"audit":', quoted(audit_path),
			',"sentinel":', quoted(sentinel_path),
			',"rom_sha256":', quoted(rom_sha256),
			',"input_state_sha256":', quoted(input_state_sha256),
			'}',
		})
		write_file(audit_path, payload)
		write_file(sentinel_path, payload)
		write_file(done_marker_path, table.concat({
			'{"run_id":', quoted(run_id),
			',"capture_frame":', tostring(capture_frame),
			',"status":"capture-complete"}',
		}))
		capture_complete = true
	end
end)
