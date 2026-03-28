local OUT = "/Users/altair/github/naruto/notes/mgba-io-2160.txt"
local frame = 0

local KEY_A = 1 << 0
local KEY_START = 1 << 3

local function pulse(keys, start_frame, duration)
	return frame >= start_frame and frame < start_frame + duration and keys or 0
end

local function dump_io()
	local io_domain = emu.memory.io
	local f = io.open(OUT, "w")
	if not f then
		return
	end
	local data = io_domain:readRange(0, 0x60)
	for off = 0, #data - 1, 16 do
		local chunk = {data:byte(off + 1, math.min(off + 16, #data))}
		local parts = {}
		for _, b in ipairs(chunk) do
			parts[#parts + 1] = string.format("%02X", b)
		end
		f:write(string.format("%04X  %s\n", off, table.concat(parts, " ")))
	end
	f:close()
end

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

	if frame == 2160 then
		dump_io()
		os.exit(0)
	end
end)
