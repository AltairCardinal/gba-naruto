-- W1 (wave 11): frame-exact recorder with a capture window.
--
-- Same contract as ``tools/s49_victory_capture/capture_victory_frames.lua``
-- (which W4 wrote for the original ROM), plus one thing this stream needs:
-- the recording can start at a given **frame**, so the settlement chain --
-- the part the task asks for -- can be captured frame by frame without
-- writing the whole battle to disk.
--
-- Environment:
--   MGBA_W1_OUTPUT_DIR     directory for frame-XXXXX.png (required)
--   MGBA_W1_KEY_SEQUENCE   "Down,Down,A,A:90:4" (required)
--   MGBA_W1_ZERO_FRAMES    frames to run before the first key (default 0)
--   MGBA_W1_HOLD_FRAMES    frames a key is held (default 4)
--   MGBA_W1_SETTLE_FRAMES  frames between the key steps (default 90)
--   MGBA_W1_CAPTURE        "all" = every frame, "step" = one frame per step
--   MGBA_W1_CAPTURE_FROM   first frame that is written (default 1)
--
-- Key token syntax: "A" (default settle), "A:90" (per key settle),
-- "A:90:4" (settle + hold) and ":90" (a pure wait).

local output_dir = assert(os.getenv("MGBA_W1_OUTPUT_DIR"))
local sequence_text = os.getenv("MGBA_W1_KEY_SEQUENCE") or ""
local zero_frames = tonumber(os.getenv("MGBA_W1_ZERO_FRAMES") or "0")
local hold_frames = tonumber(os.getenv("MGBA_W1_HOLD_FRAMES") or "4")
local settle_frames = tonumber(os.getenv("MGBA_W1_SETTLE_FRAMES") or "90")
local capture_mode = os.getenv("MGBA_W1_CAPTURE") or "all"
local capture_from = tonumber(os.getenv("MGBA_W1_CAPTURE_FROM") or "1")

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

	if frame >= capture_from then
		if capture_mode == "all" then
			emu:screenshot(string.format("%s/frame-%05d.png", output_dir, frame))
		elseif capture_mode == "step" and active_key == nil
				and frame >= next_key_frame then
			emu:screenshot(string.format("%s/frame-%05d.png", output_dir, frame))
		end
	end

	if not active_key and frame >= next_key_frame then
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
