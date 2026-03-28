local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0
local hit_count = 0
local watch_id = nil

local KEY_A = 1 << 0
local KEY_START = 1 << 3

local TARGETS = {
	wram = {
		start_addr = 0x0200A900,
		end_addr = 0x0200AA4C,
		watch_frame = 1500,
		max_hits = 64,
		timeout_frame = 3000,
		prefix = "dialogue-watch-wram",
	},
	vram_tilemap = {
		start_addr = 0x06001800,
		end_addr = 0x06002000,
		watch_frame = 1500,
		max_hits = 64,
		timeout_frame = 3000,
		prefix = "dialogue-watch-vram-tilemap",
	},
	vram_glyph = {
		start_addr = 0x06002000,
		end_addr = 0x06002800,
		watch_frame = 1500,
		max_hits = 64,
		timeout_frame = 3000,
		prefix = "dialogue-watch-vram-glyph",
	},
	sb_struct = {
		start_addr = 0x02002880,
		end_addr = 0x020029C0,
		watch_frame = 1500,
		max_hits = 96,
		timeout_frame = 3000,
		prefix = "dialogue-watch-sb-struct",
	},
	record_bank = {
		start_addr = 0x02002E30,
		end_addr = 0x02003070,
		watch_frame = 1500,
		max_hits = 96,
		timeout_frame = 3000,
		prefix = "dialogue-watch-record-bank",
	},
}

local target_name = os.getenv("NARUTO_TRACE_TARGET") or "wram"
local target = TARGETS[target_name]
if not target then
	error("unknown target: " .. target_name)
end

local log_path = string.format("%s/%s.log", OUT_DIR, target.prefix)
local summary_path = string.format("%s/%s-summary.txt", OUT_DIR, target.prefix)
local done_path = string.format("%s/%s.done", OUT_DIR, target.prefix)
local shot_path = string.format("%s/%s-first-hit.png", OUT_DIR, target.prefix)

local pc_counts = {}
local addr_counts = {}
local first_hit_taken = false

local function append(path, line, mode)
	local f = io.open(path, mode or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function log(line)
	append(log_path, line, frame == 0 and "w" or "a")
end

local function pulse(keys, start_frame, duration)
	return frame >= start_frame and frame < start_frame + duration and keys or 0
end

local function hex8(value)
	return string.format("%08X", value or 0)
end

local function read_reg(name)
	local ok, value = pcall(function()
		return emu:readRegister(name)
	end)
	if ok and value then
		return value
	end
	return 0
end

local function write_summary(status)
	local pcs = {}
	for pc, count in pairs(pc_counts) do
		table.insert(pcs, { pc = pc, count = count })
	end
	table.sort(pcs, function(a, b)
		if a.count ~= b.count then
			return a.count > b.count
		end
		return a.pc < b.pc
	end)

	local addrs = {}
	for addr, count in pairs(addr_counts) do
		table.insert(addrs, { addr = addr, count = count })
	end
	table.sort(addrs, function(a, b)
		if a.count ~= b.count then
			return a.count > b.count
		end
		return a.addr < b.addr
	end)

	local f = io.open(summary_path, "w")
	if not f then
		return
	end
	f:write(string.format("target=%s\n", target_name))
	f:write(string.format("status=%s\n", status))
	f:write(string.format("watch_id=%s\n", tostring(watch_id)))
	f:write(string.format("hits=%d\n", hit_count))
	f:write(string.format("range=%08X-%08X\n", target.start_addr, target.end_addr))
	f:write("pcs:\n")
	for _, item in ipairs(pcs) do
		f:write(string.format("%08X %d\n", item.pc, item.count))
	end
	f:write("addresses:\n")
	for _, item in ipairs(addrs) do
		f:write(string.format("%08X %d\n", item.addr, item.count))
	end
	f:close()
end

local function finish(status)
	if watch_id then
		pcall(function()
			emu:clearBreakpoint(watch_id)
		end)
		watch_id = nil
	end
	write_summary(status)
	append(done_path, status, "w")
	os.exit(0)
end

local function on_watch(info)
	hit_count = hit_count + 1
	local pc = read_reg("pc")
	local lr = read_reg("lr")
	local sp = read_reg("sp")
	local addr = info.address or 0
	pc_counts[pc] = (pc_counts[pc] or 0) + 1
	addr_counts[addr] = (addr_counts[addr] or 0) + 1

	log(string.format(
		"hit=%d frame=%d cycle=%s pc=%s lr=%s sp=%s addr=%s old=%d new=%d type=%d width=%d",
		hit_count,
		frame,
		tostring(emu:currentCycle()),
		hex8(pc),
		hex8(lr),
		hex8(sp),
		hex8(addr),
		info.oldValue or -1,
		info.newValue or -1,
		info.accessType or -1,
		info.width or -1
	))

	if not first_hit_taken then
		first_hit_taken = true
		pcall(function()
			emu:screenshot(shot_path)
		end)
		log("first_hit_screenshot=" .. shot_path)
	end

	if hit_count >= target.max_hits then
		finish("max_hits")
	end
end

callbacks:add("start", function()
	frame = 0
	log(string.format(
		"start target=%s range=%08X-%08X",
		target_name,
		target.start_addr,
		target.end_addr
	))
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

	if frame == target.watch_frame and not watch_id then
		watch_id = emu:setRangeWatchpoint(
			on_watch,
			target.start_addr,
			target.end_addr,
			C.WATCHPOINT_TYPE.WRITE_CHANGE
		)
		log(string.format("watch_set frame=%d id=%s", frame, tostring(watch_id)))
	end

	if frame == target.timeout_frame then
		finish(hit_count > 0 and "timeout_with_hits" or "timeout_no_hits")
	end
end)
