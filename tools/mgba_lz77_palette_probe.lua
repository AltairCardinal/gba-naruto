local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_file(path, payload, mode)
	local output = assert(io.open(path, mode or "w"))
	output:write(payload)
	output:close()
end

local function quoted(value)
	return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n") .. '"'
end

local function read_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local input_state = required_env("MGBA_LZ77_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_LZ77_INPUT_STATE_SHA256")
local rom_sha256 = required_env("MGBA_LZ77_ROM_SHA256")
local binary_sha256 = required_env("MGBA_LZ77_BINARY_SHA256")
local output_dir = required_env("MGBA_LZ77_OUTPUT_DIR")
local done_marker = required_env("MGBA_LZ77_DONE_MARKER")
local run_id = required_env("MGBA_LZ77_RUN_ID")
local route_name = required_env("MGBA_LZ77_ROUTE")

local target_pc = nil
local target_tile_first = nil
local target_tile_last = nil
local inputs = nil

if route_name == "scenario-41-target-confirmation" then
	target_pc = 0x08071BD0
	target_tile_first = 800
	target_tile_last = 841
	inputs = {
		{ 2, 4, "Up", C.GBA_KEY.UP },
		{ 18, 20, "Up", C.GBA_KEY.UP },
		{ 34, 36, "Up", C.GBA_KEY.UP },
		{ 50, 52, "Up", C.GBA_KEY.UP },
		{ 66, 68, "Up", C.GBA_KEY.UP },
		{ 82, 84, "Up", C.GBA_KEY.UP },
		{ 114, 116, "A", C.GBA_KEY.A },
	}
elseif route_name == "profile-browser-init" then
	target_pc = 0x0808B5EE
	target_tile_first = 940
	target_tile_last = 943
	inputs = {
		{ 2, 4, "Down", C.GBA_KEY.DOWN },
		{ 18, 20, "Down", C.GBA_KEY.DOWN },
		{ 34, 36, "A", C.GBA_KEY.A },
		{ 50, 52, "A", C.GBA_KEY.A },
	}
else
	error("unsupported MGBA_LZ77_ROUTE " .. route_name)
end

local post_hit_watch_frames = 240
local pre_hit_timeout_frames = 240
local frame = 0
local complete = false
local hit_frame = nil
local hit_pc = nil
local hit_lr = nil
local breakpoint_id = nil
local observed_object = nil

local function inputs_json()
	local rows = {}
	for _, event in ipairs(inputs) do
		rows[#rows + 1] = string.format(
			'{"key":%s,"down_frame":%d,"up_frame":%d,"hold_frames":%d}',
			quoted(event[3]),
			event[1],
			event[2],
			event[2] - event[1]
		)
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function scan_oam(base, domain)
	for index = 0, 127 do
		local address = base + index * 8
		local attr0 = emu:read16(address)
		local attr1 = emu:read16(address + 2)
		local attr2 = emu:read16(address + 4)
		local hidden = math.floor(attr0 / 0x100) % 4 == 2
		local tile = attr2 % 0x400
		if not hidden and tile >= target_tile_first and tile <= target_tile_last then
			return {
				domain = domain,
				index = index,
				attr0 = attr0,
				attr1 = attr1,
				attr2 = attr2,
				tile = tile,
				palette_bank = math.floor(attr2 / 0x1000) % 16,
			}
		end
	end
	return nil
end

local function object_json(object)
	if not object then
		return "null"
	end
	return string.format(
		'{"domain":%s,"index":%d,"attr0":"0x%04X","attr1":"0x%04X",'
			.. '"attr2":"0x%04X","tile":%d,"palette_bank":%d}',
		quoted(object.domain),
		object.index,
		object.attr0,
		object.attr1,
		object.attr2,
		object.tile,
		object.palette_bank
	)
end

local function finish(outcome)
	if complete then
		return
	end
	complete = true
	if breakpoint_id then
		emu:clearBreakpoint(breakpoint_id)
		breakpoint_id = nil
	end
	assert(emu:saveStateFile(output_dir .. "/final.ss9"))
	emu:screenshot(output_dir .. "/final.png")
	local payload = string.format(
		'{"schema":"mgba-lz77-palette-probe-v1","run_id":%s,'
			.. '"route":%s,"outcome":%s,"frame":%d,'
			.. '"input_state":%s,"input_state_sha256":%s,'
			.. '"rom_sha256":%s,"binary_sha256":%s,'
			.. '"target_pc":"0x%08X","target_tiles":[%d,%d],'
			.. '"hit_frame":%s,"hit_pc":%s,"hit_lr":%s,'
			.. '"post_hit_watch_frames":%d,"inputs":%s,"object":%s}',
		quoted(run_id),
		quoted(route_name),
		quoted(outcome),
		frame,
		quoted(input_state),
		quoted(input_state_sha256),
		quoted(rom_sha256),
		quoted(binary_sha256),
		target_pc,
		target_tile_first,
		target_tile_last,
		hit_frame and tostring(hit_frame) or "null",
		hit_pc and quoted(string.format("0x%08X", hit_pc)) or "null",
		hit_lr and quoted(string.format("0x%08X", hit_lr)) or "null",
		post_hit_watch_frames,
		inputs_json(),
		object_json(observed_object)
	)
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)
breakpoint_id = emu:setBreakpoint(function()
	if hit_frame then
		return
	end
	hit_frame = frame
	hit_pc = emu:readRegister("pc")
	hit_lr = emu:readRegister("lr")
	emu:clearBreakpoint(breakpoint_id)
	breakpoint_id = nil
	write_file(output_dir .. "/pram.bin", read_range(0x05000000, 0x400), "wb")
	write_file(output_dir .. "/vram.bin", read_range(0x06000000, 0x18000), "wb")
	write_file(output_dir .. "/oam.bin", read_range(0x07000000, 0x400), "wb")
	write_file(output_dir .. "/shadow-oam.bin", read_range(0x0300027C, 0x400), "wb")
	assert(emu:saveStateFile(output_dir .. "/hit.ss9"))
	emu:screenshot(output_dir .. "/hit.png")
	observed_object = scan_oam(0x07000000, "hardware")
		or scan_oam(0x0300027C, "shadow")
	if observed_object then
		finish("oam-observed-at-load")
	end
end, target_pc)
assert(breakpoint_id and breakpoint_id > 0, "failed to install target breakpoint")

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	for _, event in ipairs(inputs) do
		if frame == event[1] then
			emu:addKey(event[4])
		elseif frame == event[2] then
			emu:clearKey(event[4])
		end
	end

	if not hit_frame then
		if frame >= pre_hit_timeout_frames then
			finish("load-not-observed")
		end
		return
	end

	observed_object = scan_oam(0x07000000, "hardware")
		or scan_oam(0x0300027C, "shadow")
	if observed_object then
		finish("oam-observed-after-load")
	elseif frame - hit_frame >= post_hit_watch_frames then
		finish("oam-not-observed")
	end
end)
