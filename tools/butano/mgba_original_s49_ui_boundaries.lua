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

local input_state =
	required_env("MGBA_ORIGINAL_S49_INPUT_STATE")
local input_state_sha256 =
	required_env("MGBA_ORIGINAL_S49_INPUT_STATE_SHA256")
local output_dir =
	required_env("MGBA_ORIGINAL_S49_OUTPUT_DIR")
local done_marker =
	required_env("MGBA_ORIGINAL_S49_DONE_MARKER")
local sequence = parse_sequence(
	required_env("MGBA_ORIGINAL_S49_KEY_SEQUENCE")
)
local zero_input_frames = optional_number(
	"MGBA_ORIGINAL_S49_ZERO_INPUT_FRAMES",
	30
)
local settle_frames = optional_number(
	"MGBA_ORIGINAL_S49_SETTLE_FRAMES",
	30
)
local hold_frames = optional_number(
	"MGBA_ORIGINAL_S49_HOLD_FRAMES",
	6
)

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

assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local step = 0
local active_key = nil
local release_frame = nil
local capture_frame = zero_input_frames
local base_captured = false
local complete = false

local function finish()
	local payload = string.format(
		'{"status":"capture-complete","input_state_sha256":"%s","zero_input_frames":%d,"settle_frames":%d,"hold_frames":%d,"captured_steps":%d}',
		input_state_sha256,
		zero_input_frames,
		settle_frames,
		hold_frames,
		step
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

	if active_key and frame >= release_frame then
		emu:clearKey(assert(key_codes[active_key]))
		active_key = nil
		capture_frame = frame + settle_frames
		return
	end

	if not base_captured and frame >= capture_frame then
		emu:screenshot(output_dir .. "/step-00-base.png")
		assert(
			emu:saveStateFile(output_dir .. "/step-00-base.ss9"),
			"failed to save base state"
		)
		base_captured = true
		capture_frame = frame
	end

	if base_captured and not active_key and frame >= capture_frame then
		if step > 0 then
			local previous_key = sequence[step]
			emu:screenshot(
				output_dir .. string.format(
					"/step-%02d-%s.png",
					step,
					previous_key
				)
			)
			assert(
				emu:saveStateFile(
					output_dir .. string.format(
						"/step-%02d-%s.ss9",
						step,
						previous_key
					)
				),
				"failed to save step state"
			)
		end
		if step >= #sequence then
			finish()
			return
		end
		step = step + 1
		active_key = sequence[step]
		assert(key_codes[active_key], "unsupported key " .. active_key)
		emu:addKey(key_codes[active_key])
		release_frame = frame + hold_frames
	end
end)
