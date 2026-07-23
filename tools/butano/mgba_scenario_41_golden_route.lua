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
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
}

local presses = {
	{ 30, "Down" }, { 60, "Down" }, { 90, "A" }, { 120, "A" },
	{ 360, "A" },
	{ 450, "A" }, { 480, "Up" }, { 510, "A" },
	{ 540, "Down" }, { 570, "A" }, { 600, "Up" }, { 630, "A" },
	{ 660, "A" }, { 690, "A" },
	{ 780, "A" }, { 810, "A" }, { 840, "A" }, { 870, "A" },
	{ 900, "A" }, { 930, "Up" }, { 960, "A" }, { 990, "Down" },
	{ 1020, "A" }, { 1050, "Up" }, { 1080, "A" }, { 1110, "A" },
	{ 1140, "A" },
	{ 1210, "A" }, { 1240, "Up" }, { 1270, "Up" }, { 1300, "Right" },
	{ 1330, "A" }, { 1360, "Down" }, { 1390, "A" }, { 1420, "Up" },
	{ 1450, "A" }, { 1480, "A" }, { 1510, "A" },
	{ 1580, "A" }, { 1610, "A" }, { 1640, "A" }, { 1670, "A" },
	{ 1700, "Left" }, { 1730, "A" }, { 1760, "A" },
	{ 2030, "A" }, { 2060, "A" }, { 2090, "A" }, { 2120, "A" },
	{ 2150, "A" }, { 2180, "A" }, { 2210, "A" }, { 2240, "A" },
	{ 2270, "A" }, { 2300, "A" }, { 2330, "A" }, { 2360, "A" },
	{ 2390, "A" }, { 2420, "A" }, { 2450, "A" }, { 2480, "A" },
	{ 2510, "A" }, { 2540, "A" },
}

local screenshots = {
	[20] = "prebattle-menu-0.png",
	[50] = "prebattle-menu-1.png",
	[80] = "prebattle-menu-2.png",
	[110] = "prebattle-confirmation.png",
	[150] = "intro-player-appearance.png",
	[210] = "intro-enemy-appearance.png",
	[270] = "intro-start-title.png",
	[315] = "intro-black.png",
	[345] = "intro-dialogue.png",
	[390] = "intro-shuriken-transition.png",
	[430] = "battle-entry.png",
	[525] = "action-menu-0.png",
	[555] = "action-menu-1.png",
	[585] = "end-confirmation.png",
	[675] = "defense-confirmation.png",
	[760] = "tutorial.png",
	[1655] = "technique-menu.png",
	[1685] = "target-select.png",
	[1745] = "attack-confirmation.png",
	[1762] = "attack-animation-000.png",
	[1795] = "attack-animation-034.png",
	[1825] = "attack-animation-064.png",
	[1865] = "attack-animation-104.png",
	[1905] = "attack-animation-144.png",
	[1945] = "attack-animation-184.png",
	[1985] = "attack-animation-224.png",
	[2008] = "attack-animation-247.png",
	[2025] = "combat-dialogue.png",
	[2045] = "combat-popup.png",
	[2075] = "victory.png",
	[2105] = "result.png",
	[2135] = "level-up-1.png",
	[2165] = "level-up-2.png",
	[2195] = "postbattle-dialogue-1.png",
	[2225] = "postbattle-dialogue-2.png",
	[2255] = "postbattle-dialogue-3.png",
	[2285] = "postbattle-dialogue-4.png",
	[2315] = "postbattle-dialogue-5.png",
	[2345] = "postbattle-dialogue-6.png",
	[2375] = "postbattle-dialogue-7.png",
	[2405] = "postbattle-dialogue-8.png",
	[2435] = "postbattle-dialogue-9.png",
	[2465] = "postbattle-dialogue-10.png",
	[2495] = "postbattle-dialogue-11.png",
	[2560] = "postbattle.png",
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
	local screenshot = screenshots[frame]
	if screenshot then
		emu:screenshot(output_dir .. "/" .. screenshot)
	end
	if frame == 2580 then
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		write_file(output_dir .. "/audit.json", '{"frame":2580,"status":"capture-complete"}')
		write_file(done_marker_path, '{"capture_frame":2580,"status":"capture-complete"}')
		complete = true
	end
end)
