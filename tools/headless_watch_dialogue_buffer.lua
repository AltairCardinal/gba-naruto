local OUT = "/Users/altair/github/naruto/notes/headless-watch-dialogue-buffer.log"
local frame = 0
local watch_id = nil
local hit_count = 0

local KEY_A = 1 << 0
local KEY_START = 1 << 3

local function log(line)
	local f = io.open(OUT, frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function pulse(keys, start_frame, duration)
	return frame >= start_frame and frame < start_frame + duration and keys or 0
end

local function on_watch(info)
	hit_count = hit_count + 1
	local pc = emu:readRegister("pc")
	log(string.format(
		"hit=%d frame=%d cycle=%s pc=%08X addr=%08X old=%d new=%d type=%d width=%d",
		hit_count,
		frame,
		tostring(emu:currentCycle()),
		pc,
		info.address or 0,
		info.oldValue or -1,
		info.newValue or -1,
		info.accessType or -1,
		info.width or -1
	))
	if hit_count >= 16 and watch_id then
		emu:clearBreakpoint(watch_id)
		log("watch_cleared")
		os.exit(0)
	end
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
	keys = keys | pulse(KEY_A, 2310, 8)
	keys = keys | pulse(KEY_A, 2550, 8)
	emu:setKeys(keys)

	if frame == 1500 and not watch_id then
		watch_id = emu:setRangeWatchpoint(on_watch, 0x0200A900, 0x0200AA4C, C.WATCHPOINT_TYPE.WRITE_CHANGE)
		log(string.format("watch_set frame=%d id=%s", frame, tostring(watch_id)))
	end

	if frame == 3000 then
		log("timeout")
		os.exit(0)
	end
end)
