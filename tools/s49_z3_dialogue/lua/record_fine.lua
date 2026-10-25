-- Record the original's dialogue window at **one frame per capture**.
--
-- The semantic walk recorder (``tools/s49_pairing/lua/record_walk.lua``)
-- samples every four frames because it has to cover a whole battle walk; the
-- dialogue timings (the advance press and the first glyph of the next line)
-- need a frame exact measurement, so this recorder captures every single
-- frame of a frame window and saves no savestate.
--
-- Environment:
--   X2_OUTPUT_DIR        where the PNGs go
--   X2_DONE_MARKER       the "walk finished" marker file
--   X2_KEY_SEQUENCE      comma separated keys, one beat each
--   X2_INPUT_STATE       savestate to load first
--   X2_ZERO_INPUT_FRAMES frames to wait before the first capture
--   X2_SETTLE_FRAMES     frames to wait after a key was released
--   X2_HOLD_FRAMES       how long the key stays down
--   X2_CAPTURE_FROM      first frame to capture (inclusive)
--   X2_CAPTURE_TO        last frame to capture (inclusive)

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function optional_number(name, fallback)
	local value = os.getenv(name)
	if value == nil or value == "" then
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
local capture_from = optional_number("X2_CAPTURE_FROM", 0)
local capture_to = optional_number("X2_CAPTURE_TO", 100000)

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
	local stem = string.format("%s/step-%05d-%s", output_dir, capture, name)
	emu:screenshot(stem .. ".png")
	capture = capture + 1
end

local function finish()
	local payload = string.format(
		'{"status":"capture-complete","zero_input_frames":%d,"settle_frames":%d,"hold_frames":%d,"capture_from":%d,"capture_to":%d,"beats":%d,"captures":%d}',
		zero_input_frames,
		settle_frames,
		hold_frames,
		capture_from,
		capture_to,
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

	-- The capture happens **before** the key bookkeeping, so the frame the
	-- key goes down and the frame it comes back up are on the record too.
	if frame >= capture_from and frame <= capture_to then
		shot("in")
	end
	if frame > capture_to then
		finish()
		return
	end

	if active_key and frame >= release_frame then
		emu:clearKey(assert(key_codes[active_key]))
		active_key = nil
		settle_start = frame
		beat_end = frame + settle_frames
		return
	end

	if settle_start and frame >= beat_end then
		settle_start = nil
		beat = beat + 1
		if beat > #sequence then
			finish()
			return
		end
		active_key = sequence[beat]
		emu:addKey(assert(key_codes[active_key]))
		release_frame = frame + hold_frames
		return
	end

	if not base_captured and frame >= zero_input_frames then
		base_captured = true
		beat = 1
		active_key = sequence[beat]
		emu:addKey(assert(key_codes[active_key]))
		release_frame = frame + hold_frames
	end
end)
