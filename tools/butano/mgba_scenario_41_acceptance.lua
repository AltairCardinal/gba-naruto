local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function json_escape(value)
	return (value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"))
end

local function quoted(value)
	return '"' .. json_escape(value) .. '"'
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir = required_env("MGBA_S41_OUTPUT_DIR")
local run_id = required_env("MGBA_S41_RUN_ID")
local rom_sha256 = required_env("MGBA_S41_ROM_SHA256")
local done_marker_path = required_env("MGBA_S41_DONE_MARKER")

local keys = {
	A = C.GBA_KEY.A,
	Up = C.GBA_KEY.UP,
	Down = C.GBA_KEY.DOWN,
	Start = C.GBA_KEY.START,
}

local input_plan = {
	{ 60, 68, "A" },
	{ 90, 98, "A" },
	{ 120, 128, "Up" },
	{ 150, 158, "Up" },
	{ 180, 188, "Up" },
	{ 210, 218, "A" },
	{ 240, 248, "Down" },
	{ 270, 278, "A" },
	{ 390, 398, "Start" },
	{ 480, 488, "Start" },
	{ 590, 598, "A" },
	{ 620, 628, "A" },
	{ 650, 658, "A" },
	{ 680, 688, "Up" },
	{ 710, 718, "A" },
	{ 810, 818, "A" },
	{ 870, 878, "A" },
}

local screenshot_plan = {
	[30] = "intro.png",
	[80] = "initial-player-turn.png",
	[110] = "initial-move-select.png",
	[360] = "turn-2.png",
	[560] = "turn-4.png",
	[605] = "debug-after-select.png",
	[635] = "debug-after-move.png",
	[665] = "debug-after-combo.png",
	[695] = "debug-after-target.png",
	[735] = "debug-after-hit.png",
	[780] = "victory.png",
	[840] = "result.png",
	[900] = "restart.png",
}

local function input_json()
	local records = {}
	for _, entry in ipairs(input_plan) do
		records[#records + 1] = table.concat({
			'{"down_frame":', tostring(entry[1]),
			',"up_frame":', tostring(entry[2]),
			',"key":', quoted(entry[3]),
			'}',
		})
	end
	return table.concat(records, ",")
end

local frame = 0
local capture_complete = false

callbacks:add("frame", function()
	if capture_complete then
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

	local screenshot_name = screenshot_plan[frame]
	if screenshot_name then
		emu:screenshot(output_dir .. "/" .. screenshot_name)
	end

	if frame == 930 then
		local state_path = output_dir .. "/final.ss9"
		local audit_path = output_dir .. "/audit.json"
		assert(emu:saveStateFile(state_path), "failed to save final state")
		local payload = table.concat({
			'{"run_id":', quoted(run_id),
			',"frame":930',
			',"inputs":[', input_json(), ']',
			',"screenshots":["intro.png","initial-player-turn.png","initial-move-select.png","turn-2.png","turn-4.png","victory.png","result.png","restart.png"]',
			',"state":"final.ss9"',
			',"audit":"audit.json"',
			',"rom_sha256":', quoted(rom_sha256),
			',"success":true',
			',"status":"capture-complete"}',
		})
		write_file(audit_path, payload)
		write_file(done_marker_path, table.concat({
			'{"run_id":', quoted(run_id),
			',"capture_frame":930',
			',"status":"capture-complete"}',
		}))
		capture_complete = true
	end
end)
