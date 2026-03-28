local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0

local KEY_A = 1 << 0
local KEY_START = 1 << 3

local function write_file(path, data)
	local f = io.open(path, "wb")
	if f then
		f:write(data)
		f:close()
	end
end

local function log(line)
	local f = io.open(OUT_DIR .. "/mgba-newgame-snapshot.log", frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function pulse(keys, start_frame, duration)
	return frame >= start_frame and frame < start_frame + duration and keys or 0
end

local function dump_domain(name, size)
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
	local path = string.format("%s/newgame-%04d-%s.bin", OUT_DIR, frame, name)
	write_file(path, data)
	log(string.format("frame=%d dump=%s size=0x%X", frame, path, size))
end

callbacks:add("start", function()
	frame = 0
	log("start")
end)

callbacks:add("frame", function()
	frame = frame + 1

	local keys = 0
	keys = keys | pulse(KEY_A, 330, 8)
	keys = keys | pulse(KEY_A, 540, 8)
	keys = keys | pulse(KEY_A, 750, 8)
	keys = keys | pulse(KEY_START, 960, 8)
	keys = keys | pulse(KEY_A, 1140, 8)
	keys = keys | pulse(KEY_A, 1590, 8)
	keys = keys | pulse(KEY_A, 1830, 8)
	keys = keys | pulse(KEY_A, 2070, 8)

	emu:setKeys(keys)
	if keys ~= 0 then
		log(string.format("frame=%d keys=0x%X", frame, keys))
	end

	if frame == 2160 then
		local png = string.format("%s/newgame-%04d-snapshot.png", OUT_DIR, frame)
		emu:screenshot(png)
		log(string.format("frame=%d screenshot=%s", frame, png))
		dump_domain("wram", 0x40000)
		dump_domain("iwram", 0x8000)
		dump_domain("vram", 0x18000)
		dump_domain("palette", 0x400)
		dump_domain("oam", 0x400)
		local f = io.open(OUT_DIR .. "/mgba-newgame-snapshot.done", "w")
		if f then
			f:write("done\n")
			f:close()
		end
		os.exit(0)
	end
end)
