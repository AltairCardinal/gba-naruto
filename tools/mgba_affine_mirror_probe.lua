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

local function json_escape(value)
	return (value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"))
end

local function quoted(value)
	return '"' .. json_escape(value) .. '"'
end

local input_state = required_env("MGBA_AFFINE_MIRROR_INPUT_STATE")
local input_state_sha256 =
	required_env("MGBA_AFFINE_MIRROR_INPUT_STATE_SHA256")
local output_dir = required_env("MGBA_AFFINE_MIRROR_OUTPUT_DIR")
local done_marker = required_env("MGBA_AFFINE_MIRROR_DONE_MARKER")
local run_id = required_env("MGBA_AFFINE_MIRROR_RUN_ID")
local rom_sha256 = required_env("MGBA_AFFINE_MIRROR_ROM_SHA256")
local capture_frame =
	assert(tonumber(required_env("MGBA_AFFINE_MIRROR_CAPTURE_FRAME")))
assert(capture_frame > 0 and capture_frame == math.floor(capture_frame))

local task_address = 0x03005940
local expected_flags = 0xC000B681
local oam_address = 0x07000000
local expected_pa = 0xFF10
local capture_complete = false
local frame = 0

local gpu_domains = {
	{ "io", 0x400, 0x04000000 },
	{ "pram", 0x400, 0x05000000 },
	{ "vram", 0x18000, 0x06000000 },
	{ "oam", 0x400, 0x07000000 },
}

local function read_absolute_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function dump_gpu_domains()
	for _, descriptor in ipairs(gpu_domains) do
		local name = descriptor[1]
		local size = descriptor[2]
		local address = descriptor[3]
		local bytes = nil
		local domain = emu.memory[name]
		if domain then
			local ok, result = pcall(function()
				return domain:readRange(0, size)
			end)
			if ok then
				bytes = result
			end
		end
		if not bytes or #bytes ~= size then
			bytes = read_absolute_range(address, size)
		end
		assert(bytes and #bytes == size, "short GPU memory read " .. name)
		write_file(output_dir .. "/" .. name .. ".bin", bytes, "wb")
	end
end

local function signed16(value)
	if value >= 0x8000 then
		return value - 0x10000
	end
	return value
end

assert(emu:loadStateFile(input_state), "failed to load input state")

callbacks:add("frame", function()
	if capture_complete then
		return
	end
	frame = frame + 1
	if frame < capture_frame then
		return
	end

	local flags = emu:read32(task_address) % 0x100000000
	local horizontal_mirror = math.floor(flags / 0x8000) % 2 == 1
	local keyframe_index = emu:read16(task_address + 0x16)
	local found = nil
	for object_index = 0, 127 do
		local object_address = oam_address + object_index * 8
		local attr0 = emu:read16(object_address)
		local attr1 = emu:read16(object_address + 2)
		local attr2 = emu:read16(object_address + 4)
		local affine = math.floor(attr0 / 0x100) % 2 == 1
		local tile_index = attr2 % 0x400
		local palette_bank = math.floor(attr2 / 0x1000) % 0x10
		if affine and tile_index == 472 and palette_bank == 7 then
			local matrix_index = math.floor(attr1 / 0x200) % 0x20
			local matrix_base = oam_address + matrix_index * 32
			local pa = emu:read16(matrix_base + 6)
			local pb = emu:read16(matrix_base + 14)
			local pc = emu:read16(matrix_base + 22)
			local pd = emu:read16(matrix_base + 30)
			if pa == expected_pa and pb == 0 and pc == 0 and pd == 240 then
				found = {
					index = object_index,
					attr0 = attr0,
					attr1 = attr1,
					attr2 = attr2,
					matrix_index = matrix_index,
					pa = signed16(pa),
					pb = signed16(pb),
					pc = signed16(pc),
					pd = signed16(pd),
				}
				break
			end
		end
	end

	dump_gpu_domains()
	assert(emu:saveStateFile(output_dir .. "/mirrored.ss9"))
	emu:screenshot(output_dir .. "/mirrored.png")

	local success = horizontal_mirror and found ~= nil
	local object_json = "null"
	if found then
		object_json = string.format(
			'{"index":%d,"attr0":"0x%04X","attr1":"0x%04X",'
				.. '"attr2":"0x%04X","matrix_index":%d,'
				.. '"matrix":{"PA":%d,"PB":%d,"PC":%d,"PD":%d}}',
			found.index,
			found.attr0,
			found.attr1,
			found.attr2,
			found.matrix_index,
			found.pa,
			found.pb,
			found.pc,
			found.pd
		)
	end
	local payload = table.concat({
		'{"schema":"mgba-affine-mirror-probe-v1"',
		',"run_id":', quoted(run_id),
		',"success":', success and "true" or "false",
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"task_address":"0x03005940"',
		',"task_flags":', string.format('"0x%08X"', flags),
		',"expected_task_flags":"0xC000B681"',
		',"horizontal_mirror":', horizontal_mirror and "true" or "false",
		',"capture_frame":', tostring(capture_frame),
		',"keyframe_index":', tostring(keyframe_index),
		',"object":', object_json,
		'}',
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
	capture_complete = true
end)
