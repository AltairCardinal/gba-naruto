-- Navigate to first battle from title screen (with save data loaded)
-- Then dump WRAM before and during battle to find battle config structures
local OUT_DIR = "/root/gba-naruto/notes"
local frame = 0

local KEY_A = 1 << 0
local KEY_B = 1 << 1
local KEY_SELECT = 1 << 2
local KEY_START = 1 << 3
local KEY_RIGHT = 1 << 4
local KEY_LEFT = 1 << 5
local KEY_UP = 1 << 6
local KEY_DOWN = 1 << 7
local KEY_R = 1 << 8
local KEY_L = 1 << 9

local function log(line)
	local f = io.open(OUT_DIR .. "/mgba-battle-walk.log", frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function screenshot(tag)
	local name = string.format("%s/battle-%04d.png", OUT_DIR, frame)
	emu:screenshot(name)
	log(string.format("frame=%d screenshot=%s tag=%s", frame, name, tag))
end

local function dump_domain(name, size, tag)
	local domain = emu.memory[name]
	if not domain then
		log("missing_domain=" .. name)
		return
	end
	local ok, data = pcall(function()
		return domain:readRange(0, size)
	end)
	if not ok or not data then
		log("dump_failed=" .. name)
		return
	end
	local path = string.format("%s/battle-%04d-%s-%s.bin", OUT_DIR, frame, name, tag)
	local f = io.open(path, "wb")
	if f then
		f:write(data)
		f:close()
	end
	log(string.format("frame=%d dump=%s size=0x%X tag=%s", frame, path, size, tag))
end

local function pulse(keys, start_frame, duration)
	return frame >= start_frame and frame < start_frame + duration and keys or 0
end

callbacks:add("start", function()
	frame = 0
	log("start")
end)

callbacks:add("frame", function()
	frame = frame + 1

	-- Screenshot every 180 frames
	if frame % 180 == 0 then
		screenshot("interval")
	end

	local keys = 0

	-- Title screen navigation (with save data):
	-- Frame 300: Press A to start (title screen)
	keys = keys | pulse(KEY_A, 300, 8)
	-- Frame 480: Press A to select save slot
	keys = keys | pulse(KEY_A, 480, 8)
	-- Frame 660: Press A to confirm load
	keys = keys | pulse(KEY_A, 660, 8)
	-- Frame 900: Press A to skip any intro
	keys = keys | pulse(KEY_A, 900, 8)
	-- Frame 1080: Press A to continue
	keys = keys | pulse(KEY_A, 1080, 8)
	-- Frame 1260: Press A
	keys = keys | pulse(KEY_A, 1260, 8)
	-- Frame 1440: Press A (continue past any dialogue)
	keys = keys | pulse(KEY_A, 1440, 8)
	-- Frame 1620: Press A
	keys = keys | pulse(KEY_A, 1620, 8)
	-- Frame 1800: Try pressing START to get to menu
	keys = keys | pulse(KEY_START, 1800, 8)
	-- Frame 1980: Press A
	keys = keys | pulse(KEY_A, 1980, 8)
	-- Frame 2160: Press A
	keys = keys | pulse(KEY_A, 2160, 8)
	-- Frame 2340: Press A
	keys = keys | pulse(KEY_A, 2340, 8)
	-- Frame 2520: Press A
	keys = keys | pulse(KEY_A, 2520, 8)
	-- Frame 2700: Try DOWN + A for menu navigation
	keys = keys | pulse(KEY_DOWN, 2700, 4)
	keys = keys | pulse(KEY_A, 2708, 8)
	-- Frame 2880: Press A
	keys = keys | pulse(KEY_A, 2880, 8)
	-- Frame 3060: Press A
	keys = keys | pulse(KEY_A, 3060, 8)
	-- Frame 3240: Press A
	keys = keys | pulse(KEY_A, 3240, 8)
	-- Frame 3420: Press A
	keys = keys | pulse(KEY_A, 3420, 8)
	-- Frame 3600: Press A
	keys = keys | pulse(KEY_A, 3600, 8)
	-- Frame 3780: Press START to try to enter battle
	keys = keys | pulse(KEY_START, 3780, 8)
	-- Frame 3960: Press A
	keys = keys | pulse(KEY_A, 3960, 8)

	emu:setKeys(keys)
	if keys ~= 0 then
		log(string.format("frame=%d keys=0x%X", frame, keys))
	end

	-- Dump WRAM at key frames
	if frame == 600 then
		screenshot("pre-save-load")
		dump_domain("wram", 0x8000, "pre-save")
	elseif frame == 1200 then
		screenshot("post-load")
		dump_domain("wram", 0x8000, "post-load")
	elseif frame == 1800 then
		screenshot("pre-menu")
		dump_domain("wram", 0x8000, "pre-menu")
	elseif frame == 2400 then
		screenshot("mid-menu")
		dump_domain("wram", 0x8000, "mid-menu")
	elseif frame == 3600 then
		screenshot("late-menu")
		dump_domain("wram", 0x8000, "late-menu")
	end

	if frame == 4200 then
		screenshot("final")
		dump_domain("wram", 0x8000, "final")
		local f = io.open(OUT_DIR .. "/mgba-battle-walk.done", "w")
		if f then
			f:write("done\n")
			f:close()
		end
		os.exit(0)
	end
end)
