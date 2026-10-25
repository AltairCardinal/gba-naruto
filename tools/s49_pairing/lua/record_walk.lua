-- Record a *semantic* walk: a script of beats, each beat being
--   "press the confirm key, hold it, release it, wait for the settle",
-- with the frame of every beat captured.  The frame of every beat is also
-- captured at a finer stride inside the settle, because the two games are
-- not frame aligned: the original reaches a beat's end state about one
-- sub-beat later than the remake does (measured with the camera's vertical
-- scroll and the acting unit pointer).  Without the inner samples the two
-- sides cannot be sampled at the same game moment.
--
-- Environment (all optional except the first three):
--   X2_OUTPUT_DIR        where the frames and the savestates go
--   X2_DONE_MARKER       the "walk finished" marker file
--   X2_KEY_SEQUENCE      comma separated keys, one beat each
--   X2_INPUT_STATE       savestate to load first; empty means "boot from power on"
--   X2_ZERO_INPUT_FRAMES frames to wait before the first capture
--   X2_SETTLE_FRAMES     frames to wait after a key was released
--   X2_HOLD_FRAMES       how long the key stays down
--   X2_CAPTURE_STRIDE    inner capture stride in frames (0 = only the beat end)
--   X2_CAPTURE_BASE      1 = capture the frame before the first beat

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

local function parse_sequence(value)
	local result = {}
	for token in value:gmatch("[^,]+") do
		local normalized = token:gsub("^%s+", ""):gsub("%s+$", "")
		assert(normalized ~= "", "empty key token")
		result[#result + 1] = normalized
	end
	assert(#result > 0, "empty key sequence")
	return result
end

local output_dir = required_env("X2_OUTPUT_DIR")
local done_marker = required_env("X2_DONE_MARKER")
local sequence = parse_sequence(required_env("X2_KEY_SEQUENCE"))
local input_state = os.getenv("X2_INPUT_STATE") or ""
local zero_input_frames = optional_number("X2_ZERO_INPUT_FRAMES", 30)
local settle_frames = optional_number("X2_SETTLE_FRAMES", 30)
local hold_frames = optional_number("X2_HOLD_FRAMES", 6)
local capture_stride = optional_number("X2_CAPTURE_STRIDE", 0)
local capture_base = optional_number("X2_CAPTURE_BASE", 1)

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

for _, key in ipairs(sequence) do
	assert(key_codes[key], "unsupported key " .. key)
end

if input_state ~= "" then
	assert(emu:loadStateFile(input_state), "failed to load input state")
end

local frame = 0
local beat = 0
local capture = 0
local active_key = nil
local release_frame = nil
local settle_start = nil
local beat_end = nil
local base_captured = false
local complete = false

local function shot(name)
	local stem = string.format("%s/step-%04d-%s", output_dir, capture, name)
	emu:screenshot(stem .. ".png")
	assert(emu:saveStateFile(stem .. ".ss9"), "failed to save step state")
	capture = capture + 1
end

local function finish()
	local payload = string.format(
		'{"status":"capture-complete","zero_input_frames":%d,"settle_frames":%d,"hold_frames":%d,"capture_stride":%d,"beats":%d,"captures":%d}',
		zero_input_frames,
		settle_frames,
		hold_frames,
		capture_stride,
		beat,
		capture
	)
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
	complete = true
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1

	-- the key is released: the settle of this beat starts
	if active_key and frame >= release_frame then
		emu:clearKey(assert(key_codes[active_key]))
		active_key = nil
		settle_start = frame
		beat_end = frame + settle_frames
		return
	end

	-- inside the settle: capture the inner samples
	if settle_start and capture_stride > 0 and frame < beat_end then
		if (frame - settle_start) % capture_stride == 0 then
			shot("in")
		end
		return
	end

	if settle_start and frame >= beat_end then
		settle_start = nil
		shot("beat")
		if beat >= #sequence then
			finish()
			return
		end
		beat = beat + 1
		active_key = sequence[beat]
		emu:addKey(assert(key_codes[active_key]))
		release_frame = frame + hold_frames
		return
	end

	if not base_captured and frame >= zero_input_frames then
		if capture_base == 1 then
			shot("base")
		end
		base_captured = true
		if #sequence == 0 then
			finish()
			return
		end
		beat = 1
		active_key = sequence[beat]
		emu:addKey(assert(key_codes[active_key]))
		release_frame = frame + hold_frames
	end
end)
