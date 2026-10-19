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
	required_env("MGBA_ORIGINAL_SEQUENCE_INPUT_STATE")
local input_state_sha256 =
	required_env("MGBA_ORIGINAL_SEQUENCE_INPUT_STATE_SHA256")
local output_dir =
	required_env("MGBA_ORIGINAL_SEQUENCE_OUTPUT_DIR")
local done_marker =
	required_env("MGBA_ORIGINAL_SEQUENCE_DONE_MARKER")
local frame_count =
	optional_number("MGBA_ORIGINAL_SEQUENCE_FRAME_COUNT", 32)

assert(frame_count > 0, "frame count must be positive")
assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	emu:screenshot(
		output_dir .. string.format("/frame-%02d.png", frame)
	)
	frame = frame + 1
	if frame >= frame_count then
		local payload = string.format(
			'{"status":"capture-complete","input_state_sha256":"%s","frame_count":%d}',
			input_state_sha256,
			frame_count
		)
		write_file(output_dir .. "/audit.json", payload)
		write_file(done_marker, payload)
		complete = true
	end
end)
