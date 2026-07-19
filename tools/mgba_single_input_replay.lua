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
local key_name = required_env("MGBA_SINGLE_INPUT_KEY")
local down_frame = assert(tonumber(required_env("MGBA_SINGLE_INPUT_DOWN_FRAME")))
local up_frame = assert(tonumber(required_env("MGBA_SINGLE_INPUT_UP_FRAME")))
local keys = { Down = C.GBA_KEY.DOWN, A = C.GBA_KEY.A, B = C.GBA_KEY.B, L = C.GBA_KEY.L, Up = C.GBA_KEY.UP, Right = C.GBA_KEY.RIGHT, Left = C.GBA_KEY.LEFT, Start = C.GBA_KEY.START }
local key = assert(keys[key_name], "input key must be Down, Up, Left, Right, A, B, L, or Start")
local frame = 0
local capture_complete = false

assert(down_frame > 0 and down_frame == math.floor(down_frame), "invalid down frame")
assert(up_frame == math.floor(up_frame), "invalid up frame")
assert(capture_frame == math.floor(capture_frame), "invalid capture frame")
assert(down_frame < up_frame and up_frame < capture_frame, "invalid frame order")
assert(emu:loadStateFile(input_state), "failed to load input state")

callbacks:add("frame", function()
	if capture_complete then
		return
	end
	frame = frame + 1
	if frame == down_frame then
		emu:addKey(key)
	elseif frame == up_frame then
		emu:clearKey(key)
	elseif frame == capture_frame then
		assert(emu:saveStateFile(output_state), "failed to save output state")
		emu:screenshot(output_png)
		local event = table.concat({
			'{"key":', quoted(key_name),
			',"down_frame":', tostring(down_frame),
			',"up_frame":', tostring(up_frame),
			',"hold_frames":', tostring(up_frame - down_frame),
			'}'
		})
		local payload = table.concat({
			'{"run_id":', quoted(run_id),
			',"frame":', tostring(frame),
			',"capture_frame":', tostring(capture_frame),
			',"inputs":[', event, ']',
			',"evidence_mode":"single-input"',
			',"zero_input_verified":false',
			',"automatic_inputs":[]',
			',"recovery_inputs":[]',
			',"success":true',
			',"status":"capture-complete"',
			',"input_state":', quoted(input_state),
			',"output_state":', quoted(output_state),
			',"output_png":', quoted(output_png),
			',"audit":', quoted(audit_path),
			',"sentinel":', quoted(sentinel_path),
			',"rom_sha256":', quoted(rom_sha256),
			',"input_state_sha256":', quoted(input_state_sha256),
			'}'
		})
		write_file(audit_path, payload)
		write_file(sentinel_path, payload)
		write_file(done_marker_path, table.concat({
			'{"run_id":', quoted(run_id),
			',"capture_frame":', tostring(capture_frame),
			',"status":"capture-complete"}'
		}))
		capture_complete = true
	end
end)
