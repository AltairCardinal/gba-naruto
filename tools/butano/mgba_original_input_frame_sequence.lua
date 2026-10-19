local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function optional_number(name, fallback)
	local value = os.getenv(name)
	if not value or value == "" then
		return fallback
	end
	return assert(tonumber(value), "invalid numeric environment " .. name)
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local input_state =
	required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE")
local input_state_sha256 =
	required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE_SHA256")
local output_dir =
	required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_OUTPUT_DIR")
local done_marker =
	required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_DONE_MARKER")
local key_name =
	required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_KEY")
local hold_frames =
	optional_number("MGBA_ORIGINAL_INPUT_SEQUENCE_HOLD_FRAMES", 6)
local frame_count =
	optional_number("MGBA_ORIGINAL_INPUT_SEQUENCE_FRAME_COUNT", 300)
local record_all = os.getenv("MGBA_ORIGINAL_INPUT_SEQUENCE_RECORD_ALL") == "1"
local pre_input_frames = optional_number("MGBA_ORIGINAL_INPUT_SEQUENCE_PRE_INPUT_FRAMES", 30)

local key_codes = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	L = C.GBA_KEY.L,
	R = C.GBA_KEY.R,
	Start = C.GBA_KEY.START,
	Select = C.GBA_KEY.SELECT,
}

assert(key_codes[key_name] or (record_all and key_name == "None"), "unsupported key " .. key_name)
assert(hold_frames > 0, "hold frames must be positive")
assert(frame_count > 0, "frame count must be positive")
if record_all then
	assert(pre_input_frames >= 0 and pre_input_frames + hold_frames < frame_count,
		"input must finish before capture ends")
end
assert(emu:loadStateFile(input_state), "failed to load input state")

-- The same GBA API works for the original and the Butano ROM. Legacy mode
-- keeps old capture contracts; record-all mode includes the press itself.
if record_all then
	local restored = output_dir .. "/restored.ss9"
	assert(emu:saveStateFile(restored), "failed to save restored checkpoint")
	assert(emu:loadStateFile(restored), "failed to restore saved checkpoint")
	local index = 0
	local finished = false
	callbacks:add("frame", function()
		if finished then return end
		emu:screenshot(output_dir .. string.format("/frame-%03d.png", index))
		-- Input is applied AFTER this captured frame, affecting the next tick.
		if key_name ~= "None" then
			if index == pre_input_frames then emu:addKey(key_codes[key_name]) end
			if index == pre_input_frames + hold_frames then emu:clearKey(key_codes[key_name]) end
		end
		index = index + 1
		if index == frame_count then
			assert(emu:saveStateFile(output_dir .. "/final.ss9"), "failed to save final checkpoint")
			local payload = string.format(
				'{"status":"capture-complete","record_all":true,"input_state_sha256":"%s","key":"%s","hold_frames":%d,"input_after_frame":%d,"frame_count":%d}',
				input_state_sha256, key_name, hold_frames, pre_input_frames, frame_count)
			write_file(output_dir .. "/audit.json", payload)
			write_file(done_marker, payload)
			finished = true
		end
	end)
	return
end

local input_frames = 0
local captured_frames = 0
local key_pressed = false
local capturing = false
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	if not key_pressed then
		emu:addKey(key_codes[key_name])
		key_pressed = true
		return
	end
	if not capturing then
		input_frames = input_frames + 1
		if input_frames < hold_frames then
			return
		end
		emu:clearKey(key_codes[key_name])
		capturing = true
	end

	emu:screenshot(
		output_dir .. string.format(
			"/frame-%03d.png", captured_frames
		)
	)
	captured_frames = captured_frames + 1
	if captured_frames >= frame_count then
		local payload = string.format(
			'{"status":"capture-complete","input_state_sha256":"%s","key":"%s","hold_frames":%d,"frame_count":%d}',
			input_state_sha256,
			key_name,
			hold_frames,
			frame_count
		)
		write_file(output_dir .. "/audit.json", payload)
		write_file(done_marker, payload)
		complete = true
	end
end)
