local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0

local KEY_A = 1 << 0
local KEY_START = 1 << 3
local KEY_DOWN = 1 << 7

local function log(line)
	local f = io.open(OUT_DIR .. "/mgba-newgame-walk.log", frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function screenshot(tag)
	local name = string.format("%s/newgame-%04d.png", OUT_DIR, frame)
	emu:screenshot(name)
	log(string.format("frame=%d screenshot=%s tag=%s", frame, name, tag))
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

	if frame % 180 == 0 then
		screenshot("interval")
	end

	local keys = 0
	keys = keys | pulse(KEY_A, 330, 8)
	keys = keys | pulse(KEY_A, 540, 8)
	keys = keys | pulse(KEY_A, 750, 8)
	keys = keys | pulse(KEY_START, 960, 8)
	keys = keys | pulse(KEY_A, 1140, 8)
	keys = keys | pulse(KEY_A, 1590, 8)
	keys = keys | pulse(KEY_A, 1830, 8)
	keys = keys | pulse(KEY_A, 2070, 8)
	keys = keys | pulse(KEY_A, 2310, 8)
	keys = keys | pulse(KEY_A, 2550, 8)

	emu:setKeys(keys)
	if keys ~= 0 then
		log(string.format("frame=%d keys=0x%X", frame, keys))
	end

	if frame == 2700 then
		screenshot("final")
		local f = io.open(OUT_DIR .. "/mgba-newgame-walk.done", "w")
		if f then
			f:write("done\n")
			f:close()
		end
		os.exit(0)
	end
end)
