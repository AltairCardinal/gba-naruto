local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0

local KEY_START = 1 << 3
local KEY_DOWN = 1 << 7
local KEY_A = 1 << 0

local function write_log(line)
	local f = io.open(OUT_DIR .. "/mgba-auto-title.log", frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function snapshot(name)
	emu:screenshot(OUT_DIR .. "/" .. name)
	write_log(string.format("frame=%d screenshot=%s", frame, name))
end

local function press(keys)
	emu:setKeys(keys)
	write_log(string.format("frame=%d keys=0x%X", frame, keys))
end

callbacks:add("start", function()
	frame = 0
	write_log("start")
end)

callbacks:add("frame", function()
	frame = frame + 1

	if frame == 30 then
		snapshot("auto-0030-title.png")
	end

	if frame >= 120 and frame <= 126 then
		press(KEY_START)
	end

	if frame == 180 then
		press(0)
		snapshot("auto-0180-after-start.png")
	end

	if frame >= 210 and frame <= 214 then
		press(KEY_DOWN)
	end

	if frame == 240 then
		press(0)
		snapshot("auto-0240-after-down.png")
	end

	if frame >= 270 and frame <= 276 then
		press(KEY_A)
	end

	if frame == 330 then
		press(0)
		snapshot("auto-0330-after-a.png")
		local f = io.open(OUT_DIR .. "/mgba-auto-title.done", "w")
		if f then
			f:write("done\n")
			f:close()
		end
		os.exit(0)
	end
end)
