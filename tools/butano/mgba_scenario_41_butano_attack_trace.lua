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
	Right = C.GBA_KEY.RIGHT,
}

local presses = {
	{ 30, "Down" }, { 60, "Down" }, { 90, "A" }, { 120, "A" },
	{ 150, "A" }, { 210, "Up" }, { 240, "A" },
	{ 270, "Down" }, { 300, "A" }, { 330, "Up" }, { 360, "A" },
	{ 390, "A" }, { 420, "A" },
	{ 510, "A" }, { 540, "A" }, { 570, "A" }, { 600, "A" },
	{ 630, "A" }, { 660, "Up" }, { 690, "A" }, { 720, "Down" },
	{ 750, "A" }, { 780, "Up" }, { 810, "A" }, { 840, "A" },
	{ 870, "A" },
	{ 940, "A" }, { 970, "Up" }, { 1000, "Up" }, { 1030, "Right" },
	{ 1060, "A" }, { 1090, "Down" }, { 1120, "A" }, { 1150, "Up" },
	{ 1180, "A" }, { 1210, "A" }, { 1240, "A" },
	{ 1310, "A" }, { 1340, "Up" }, { 1370, "Up" }, { 1400, "Right" },
	{ 1430, "A" }, { 1460, "A" }, { 1490, "A" }, { 1520, "Up" },
	{ 1550, "A" }, { 1580, "A" },
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
	if frame >= 1578 and frame <= 1870 then
		emu:screenshot(output_dir .. "/" .. string.format("render-%04d.png", frame))
	end
	if frame == 1632 or frame == 1645 then
		assert(emu:saveStateFile(
			output_dir .. "/" .. string.format("state-%04d.ss9", frame)))
	end
	if frame == 1870 then
		write_file(done_marker_path, '{"capture_frame":1870,"status":"capture-complete"}')
		complete = true
	end
end)
