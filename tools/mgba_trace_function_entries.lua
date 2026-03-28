local OUT_DIR = "/Users/altair/github/naruto/notes"
local frame = 0
local hit_count = 0
local break_id = nil

local KEY_A = 1 << 0
local KEY_START = 1 << 3

local TARGETS = {
	dialogue_wram_func = {
		address = 0x08066D14,
		prefix = "dialogue-entry-08066D14",
		max_hits = 16,
		timeout_frame = 3200,
	},
	dialogue_glyph_func = {
		address = 0x08065EB8,
		prefix = "dialogue-entry-08065EB8",
		max_hits = 16,
		timeout_frame = 3200,
	},
}

local target_name = os.getenv("NARUTO_ENTRY_TARGET") or "dialogue_wram_func"
local target = TARGETS[target_name]
if not target then
	error("unknown target: " .. target_name)
end

local log_path = string.format("%s/%s.log", OUT_DIR, target.prefix)
local done_path = string.format("%s/%s.done", OUT_DIR, target.prefix)
local shot_path = string.format("%s/%s-first-hit.png", OUT_DIR, target.prefix)
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

local function read_reg(name)
	local ok, value = pcall(function()
		return emu:readRegister(name)
	end)
	if ok and value then
		return value
	end
	return 0
end

local function hex8(value)
	return string.format("%08X", value or 0)
end

local function finish(status)
	if break_id then
		pcall(function()
			emu:clearBreakpoint(break_id)
		end)
		break_id = nil
	end
	append(done_path, status, "w")
	os.exit(0)
end

local function on_break(info)
	hit_count = hit_count + 1
	local pc = read_reg("pc")
	local lr = read_reg("lr")
	local sp = read_reg("sp")
	local r0 = read_reg("r0")
	local r1 = read_reg("r1")
	local r2 = read_reg("r2")
	local r3 = read_reg("r3")
	log(string.format(
		"hit=%d frame=%d cycle=%s pc=%s lr=%s sp=%s r0=%s r1=%s r2=%s r3=%s addr=%s",
		hit_count,
		frame,
		tostring(emu:currentCycle()),
		hex8(pc),
		hex8(lr),
		hex8(sp),
		hex8(r0),
		hex8(r1),
		hex8(r2),
		hex8(r3),
		hex8(info.address or 0)
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
	log(string.format("start target=%s address=%08X", target_name, target.address))
	break_id = emu:setBreakpoint(on_break, target.address)
	log("break_set id=" .. tostring(break_id))
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

	if frame == target.timeout_frame then
		finish(hit_count > 0 and "timeout_with_hits" or "timeout_no_hits")
	end
end)
