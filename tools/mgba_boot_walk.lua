local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0

local KEY_A = 1 << 0
local KEY_START = 1 << 3
local KEY_DOWN = 1 << 7

local function log(line)
	local f = io.open(OUT_DIR .. "/mgba-boot-walk.log", frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function screenshot(name)
	emu:screenshot(OUT_DIR .. "/" .. name)
	log(string.format("frame=%d screenshot=%s", frame, name))
end

local function press(keys)
	emu:setKeys(keys)
	log(string.format("frame=%d keys=0x%X", frame, keys))
end

callbacks:add("start", function()
	frame = 0
	log("start")
end)

callbacks:add("frame", function()
	frame = frame + 1

	if frame == 30 then screenshot("walk-0030-boot.png") end
	if frame == 300 then screenshot("walk-0300-splash.png") end

	if frame >= 330 and frame <= 336 then
		press(KEY_A)
	end
	if frame == 390 then
		press(0)
		screenshot("walk-0390-post-splash.png")
	end

	if frame >= 480 and frame <= 486 then
		press(KEY_START)
	end
	if frame == 540 then
		press(0)
		screenshot("walk-0540-post-start.png")
	end

	if frame >= 570 and frame <= 575 then
		press(KEY_DOWN)
	end
	if frame == 630 then
		press(0)
		screenshot("walk-0630-post-down.png")
	end

	if frame >= 660 and frame <= 666 then
		press(KEY_A)
	end
	if frame == 750 then
		press(0)
		screenshot("walk-0750-post-a.png")
		local f = io.open(OUT_DIR .. "/mgba-boot-walk.done", "w")
		if f then
			f:write("done\n")
			f:close()
		end
		os.exit(0)
	end
end)
