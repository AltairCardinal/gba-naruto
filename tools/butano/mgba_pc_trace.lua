-- Log the program counter once per emulated frame.
--
-- The GDB probe stops on a single address, so it cannot show *which* routine
-- reacts to an input: the boundary captures always land back in the main loop.
-- Reading PC from a frame callback gives a cheap PC trace over exactly the
-- frames that matter, using the same Lua pipeline as every other capture.
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

local input_state = required_env("MGBA_PC_TRACE_INPUT_STATE")
local output_dir = required_env("MGBA_PC_TRACE_OUTPUT_DIR")
local done_marker = required_env("MGBA_PC_TRACE_DONE_MARKER")
local frame_count = optional_number("MGBA_PC_TRACE_FRAME_COUNT", 120)
local input_after_frame = optional_number("MGBA_PC_TRACE_INPUT_AFTER_FRAME", 0)
local input_hold_frames = optional_number("MGBA_PC_TRACE_INPUT_HOLD_FRAMES", 4)
local input_key = os.getenv("MGBA_PC_TRACE_KEY") or "None"

local key_codes = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Start = C.GBA_KEY.START,
	Select = C.GBA_KEY.SELECT,
}

assert(frame_count > 0, "frame count must be positive")
assert(input_key == "None" or key_codes[input_key], "unsupported key " .. input_key)
assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local complete = false
local lines = {}
local pressed = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	lines[#lines + 1] = string.format(
		"%d 0x%08X", frame, emu:readRegister("pc"))
	if input_key ~= "None" and not pressed and frame == input_after_frame then
		emu:addKey(key_codes[input_key])
		pressed = true
	end
	if input_key ~= "None" and pressed and frame == input_after_frame + input_hold_frames then
		emu:clearKey(key_codes[input_key])
		pressed = false
	end
	if frame < frame_count then
		return
	end
	local payload = table.concat(lines, "\n") .. "\n"
	write_file(output_dir .. "/pc-trace.txt", payload)
	local marker = string.format(
		'{"status":"pc-trace-complete","frames":%d,"input_after_frame":%d,"key":"%s"}',
		frame_count, input_after_frame, input_key)
	write_file(output_dir .. "/audit.json", marker)
	write_file(done_marker, marker)
	complete = true
end)
