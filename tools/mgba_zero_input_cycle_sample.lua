local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local output_dir = required_env("MGBA_CYCLE_OUTPUT_DIR")
local max_frame = assert(tonumber(required_env("MGBA_CYCLE_MAX_FRAME")))
local frame = 0

assert(max_frame == 600, "MGBA_CYCLE_MAX_FRAME must equal 600")

callbacks:add("frame", function()
	frame = frame + 1
	if frame <= max_frame then
		local path = string.format("%s/frame-%04d.png", output_dir, frame)
		emu:screenshot(path)
		if frame % 30 == 0 then
			print(string.format("cycle-sample frame %d/%d", frame, max_frame))
		end
	end
end)
