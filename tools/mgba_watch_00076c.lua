local WATCH_ADDR = 0x0800076C
local WATCH_LEN = 8
local FRAME_INTERVAL = 30

local logbuf = console:createBuffer("naruto-watch-00076c")
local frame_count = 0

local function hex_bytes(addr, len)
	local parts = {}
	for i = 0, len - 1 do
		local b = emu:read8(addr + i)
		parts[#parts + 1] = string.format("%02X", b)
	end
	return table.concat(parts, " ")
end

local function log_state(reason)
	local pc = emu:readRegister("pc")
	logbuf:clear()
	logbuf:print(string.format("[naruto-watch] %s", reason))
	logbuf:print(string.format("pc=%s", tostring(pc)))
	logbuf:print(string.format("addr=0x%08X", WATCH_ADDR))
	logbuf:print(string.format("bytes=%s", hex_bytes(WATCH_ADDR, WATCH_LEN)))
end

local function on_start()
	frame_count = 0
	log_state("start")
	console:log("[naruto-watch] watching 0x0800076C")
end

local function on_frame()
	frame_count = frame_count + 1
	if frame_count % FRAME_INTERVAL == 0 then
		log_state("frame " .. tostring(frame_count))
	end
end

callbacks:add("start", on_start)
callbacks:add("reset", on_start)
callbacks:add("frame", on_frame)

if emu then
	on_start()
end
