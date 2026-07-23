local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir = required_env("MGBA_S41_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_S41_DONE_MARKER")
local keys = {
	A = C.GBA_KEY.A,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
}
local presses = {
	{ 30, "Down" }, { 60, "Down" }, { 90, "A" }, { 120, "A" },
	{ 360, "A" }, { 450, "A" }, { 480, "Up" }, { 510, "A" },
	{ 540, "Down" }, { 570, "A" }, { 600, "Up" }, { 630, "A" },
	{ 660, "A" }, { 690, "A" },
}

local frame = 0
local complete = false
callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	for _, press in ipairs(presses) do
		local key = assert(keys[press[2]])
		if frame == press[1] then
			emu:addKey(key)
		elseif frame == press[1] + 8 then
			emu:clearKey(key)
		end
	end
	if frame >= 670 and frame <= 800 and frame % 5 == 0 then
		emu:screenshot(output_dir .. "/frame-" .. tostring(frame) .. ".png")
	end
	if frame == 800 then
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(done_marker_path, '{"capture_frame":800,"status":"capture-complete"}')
		complete = true
	end
end)
