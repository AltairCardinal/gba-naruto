-- Capture every frame of a key sequence, inside the probe process.
--
-- Why a Lua script and not the Python client: the probe's frame callback runs
-- in the emulator process, so a screenshot per frame costs one PNG encode
-- instead of a pipe round trip per frame.  The frame index written into the
-- file name is the *true* GBA frame index of the capture.
--
-- Environment:
--   MGBA_W3_OUTPUT_DIR      directory for frame-XXXXX.png (required)
--   MGBA_W3_INPUT_STATE     savestate to load first (optional, may be empty)
--   MGBA_W3_KEY_SEQUENCE    "Down,Down,A,A*20" (required)
--   MGBA_W3_ZERO_FRAMES     frames to run before the first key (default 0)
--   MGBA_W3_HOLD_FRAMES     frames a key is held (default 4)
--   MGBA_W3_SETTLE_FRAMES   frames between the key steps (default 90)
--   MGBA_W3_CAPTURE         "all" = every frame, "step" = one frame per step
--
-- Used by tools/s49_blackfade/blackfade_report.py.

local output_dir = assert(os.getenv("MGBA_W3_OUTPUT_DIR"))
local input_state = os.getenv("MGBA_W3_INPUT_STATE") or ""
local sequence_text = assert(os.getenv("MGBA_W3_KEY_SEQUENCE"))
local zero_frames = tonumber(os.getenv("MGBA_W3_ZERO_FRAMES") or "0")
local hold_frames = tonumber(os.getenv("MGBA_W3_HOLD_FRAMES") or "4")
local settle_frames = tonumber(os.getenv("MGBA_W3_SETTLE_FRAMES") or "90")
local capture_mode = os.getenv("MGBA_W3_CAPTURE") or "all"

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

-- A token is either "A" (the default settle) or "A:90" (a per key settle).
local function parse_sequence(value)
	local result = {}
	for token in value:gmatch("[^,]+") do
		local normalized = token:gsub("^%s+", ""):gsub("%s+$", "")
		assert(normalized ~= "", "empty key token")
		local key, settle = normalized:match("^([^:]+):(%d+)$")
		if key then
			result[#result + 1] = {key = key, settle = tonumber(settle)}
		else
			result[#result + 1] = {key = normalized, settle = nil}
		end
	end
	assert(#result > 0, "empty key sequence")
	return result
end

local sequence = parse_sequence(sequence_text)

if input_state ~= "" then
	assert(emu:loadStateFile(input_state), "failed to load input state")
end

local frame = 0
local step = 0
local active_key = nil
local pending_settle = nil
local release_frame = nil
local next_key_frame = zero_frames
local done = false

callbacks:add("frame", function()
	if done then
		return
	end
	frame = frame + 1

	if active_key and frame >= release_frame then
		emu:clearKey(assert(key_codes[active_key]))
		active_key = nil
		next_key_frame = frame + (pending_settle or settle_frames)
	end

	if capture_mode == "all" then
		emu:screenshot(string.format("%s/frame-%05d.png", output_dir, frame))
	elseif capture_mode == "step" and active_key == nil and frame >= next_key_frame then
		emu:screenshot(string.format("%s/frame-%05d.png", output_dir, frame))
	end

	if not active_key and frame >= next_key_frame then
		if step >= #sequence then
			done = true
			return
		end
		step = step + 1
		local entry = sequence[step]
		active_key = entry.key
		pending_settle = entry.settle
		assert(key_codes[active_key], "unsupported key " .. active_key)
		emu:addKey(key_codes[active_key])
		release_frame = frame + hold_frames
	end
end)
