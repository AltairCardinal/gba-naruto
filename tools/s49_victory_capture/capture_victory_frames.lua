-- Capture every frame of a key sequence **and** the live battle state of the
-- very same frame, inside the probe process.
--
-- Why this exists (stream W4, fifth attempt at the original victory screen)
--
-- The four previous attempts (K -> M -> W3 -> X3) all failed in the same place:
-- the driver had to *guess* which screen it was on from pixel thresholds, and
-- the guess was sometimes one step behind the game.  This script removes the
-- guesswork from the **recording** side: the frame callback runs inside the
-- emulator, so the PNG and the state words it writes belong to the same frame.
-- Whatever the driver does, the recording is frame exact.
--
-- Environment:
--   MGBA_W4_OUTPUT_DIR     directory for frame-XXXXX.png (required)
--   MGBA_W4_INPUT_STATE    savestate to load first (optional)
--   MGBA_W4_KEY_SEQUENCE   "Down,Down,A,A*20" (required)
--   MGBA_W4_ZERO_FRAMES    frames to run before the first key (default 0)
--   MGBA_W4_HOLD_FRAMES    frames a key is held (default 4)
--   MGBA_W4_SETTLE_FRAMES  frames between the key steps (default 90)
--   MGBA_W4_CAPTURE        "all" = every frame, "step" = one frame per step
--   MGBA_W4_STATE_FILE     per-frame state CSV (default <output>/state.csv)
--
-- Key token syntax: "A" (default settle) or "A:90" (per key settle).

local output_dir = assert(os.getenv("MGBA_W4_OUTPUT_DIR"))
local input_state = os.getenv("MGBA_W4_INPUT_STATE") or ""
local sequence_text = os.getenv("MGBA_W4_KEY_SEQUENCE") or ""
local zero_frames = tonumber(os.getenv("MGBA_W4_ZERO_FRAMES") or "0")
local hold_frames = tonumber(os.getenv("MGBA_W4_HOLD_FRAMES") or "4")
local settle_frames = tonumber(os.getenv("MGBA_W4_SETTLE_FRAMES") or "90")
local capture_mode = os.getenv("MGBA_W4_CAPTURE") or "all"

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

local function parse_sequence(value)
	local result = {}
	for token in value:gmatch("[^,]+") do
		local normalized = token:gsub("^%s+", ""):gsub("%s+$", "")
		assert(normalized ~= "", "empty key token")
		-- ":settle" and ":settle:hold" are pure waits (no key press).
		local key, settle, hold =
			normalized:match("^([^:]*):(%d+):(%d+)$")
		if key then
			result[#result + 1] = {key = key,
					settle = tonumber(settle),
					hold = tonumber(hold)}
		else
			local plain_key, plain_settle =
				normalized:match("^([^:]*):(%d+)$")
			if plain_key then
				result[#result + 1] = {key = plain_key,
						settle = tonumber(plain_settle)}
			else
				result[#result + 1] = {key = normalized, settle = nil}
			end
		end
	end
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
local pending_hold = nil
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
		-- an empty sequence means "record only": the driver injects the keys
		if #sequence > 0 and step >= #sequence then
			done = true
			return
		end
		if #sequence == 0 then
			return
		end
		step = step + 1
		local entry = sequence[step]
		pending_settle = entry.settle
		pending_hold = entry.hold
		if entry.key == "" then
			-- a pure wait: no key is pressed, the frames simply run
			next_key_frame = frame + (pending_settle or settle_frames)
			return
		end
		active_key = entry.key
		assert(key_codes[active_key], "unsupported key " .. active_key)
		emu:addKey(key_codes[active_key])
		release_frame = frame + (pending_hold or hold_frames)
	end
end)
