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
	B = C.GBA_KEY.B,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
}

local input_plan = {
	{ 60, 68, "A" },
	{ 90, 98, "A" },
	{ 120, 128, "A" },
	{ 150, 158, "A" },
	{ 180, 188, "B" },
	{ 210, 218, "Down" },
	{ 240, 248, "A" },
	{ 270, 278, "Up" },
	{ 300, 308, "A" },
}

local screenshot_plan = {
	[110] = "move-select.png",
	[170] = "technique-menu.png",
	[320] = "facing.png",
}

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	for _, entry in ipairs(input_plan) do
		local key = assert(keys[entry[3]])
		if frame == entry[1] then
			emu:addKey(key)
		elseif frame == entry[2] then
			emu:clearKey(key)
		end
	end
	local screenshot = screenshot_plan[frame]
	if screenshot then
		emu:screenshot(output_dir .. "/" .. screenshot)
	end
	if frame == 340 then
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(output_dir .. "/audit.json", '{"frame":340,"status":"capture-complete"}')
		write_file(done_marker_path, '{"capture_frame":340,"status":"capture-complete"}')
		complete = true
	end
end)
