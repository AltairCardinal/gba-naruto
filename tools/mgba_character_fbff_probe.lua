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

local input_state = required_env("MGBA_FBFF_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_FBFF_INPUT_STATE_SHA256")
local output_dir = required_env("MGBA_FBFF_OUTPUT_DIR")
local done_marker = required_env("MGBA_FBFF_DONE_MARKER")
local run_id = required_env("MGBA_FBFF_RUN_ID")
local rom_sha256 = required_env("MGBA_FBFF_ROM_SHA256")
local capture_frame = assert(tonumber(required_env("MGBA_FBFF_CAPTURE_FRAME")))
local expected_trailer = required_env("MGBA_FBFF_EXPECTED_TRAILER")
assert(capture_frame > 0 and capture_frame == math.floor(capture_frame))
assert(expected_trailer == "FBFF" or expected_trailer == "FFFF")

local task_address = 0x03005940
local task_size = 0x3C
local oam_address = 0x07000000
local oam_size = 0x400
local injected_flags = 0xC0003601
local injected_tile_base = 0x0300
local injected_palette_bank = 0x0E
local valid_component_attr2 = 0xE340
local first_pseudo_component_attr2 = 0xFEFF
local renderer_loop_address = 0x080631FE
local anomalous_trailer_address = 0x0825A8E4
local frame = 0
local capture_complete = false
local renderer_breakpoint = nil
local renderer_loop_hits = {}

local function read_absolute_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function active_oam_entry(attr0)
	local affine = math.floor(attr0 / 0x100) % 2 == 1
	local disabled = not affine and math.floor(attr0 / 0x200) % 2 == 1
	return not disabled
end

local function relevant_renderer_pointer(pointer)
	return pointer >= anomalous_trailer_address
		and pointer <= anomalous_trailer_address + 0x3C
		and (pointer - anomalous_trailer_address) % 0x14 == 0
end

local function renderer_loop_json()
	local encoded = {}
	for index, hit in ipairs(renderer_loop_hits) do
		encoded[#encoded + 1] = string.format(
			'{"hit":%d,"cycle":%s,"pointer":"0x%08X",'
				.. '"raw_u16":"0x%04X","signed_value":%d}',
			index,
			hit.cycle,
			hit.pointer,
			hit.raw_u16,
			hit.signed_value
		)
	end
	return table.concat({
		'{"renderer_loop_address":"0x080631FE","hits":[',
		table.concat(encoded, ","),
		"]}",
	})
end

local function persist_result(payload)
	capture_complete = true
	if renderer_breakpoint then
		emu:clearBreakpoint(renderer_breakpoint)
		renderer_breakpoint = nil
	end
	write_file(
		output_dir .. "/task-after.bin",
		read_absolute_range(task_address, task_size),
		"wb"
	)
	write_file(
		output_dir .. "/oam.bin",
		read_absolute_range(oam_address, oam_size),
		"wb"
	)
	write_file(output_dir .. "/renderer-loop.json", renderer_loop_json())
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
end

assert(emu:loadStateFile(input_state), "failed to load input state")
assert(emu:read32(task_address) == injected_flags)
assert(emu:read16(task_address + 0x04) == 120)
assert(emu:read16(task_address + 0x06) == 80)
assert(emu:read16(task_address + 0x10) == injected_tile_base)
assert(emu:read16(task_address + 0x12) == injected_palette_bank)
assert(emu:read16(task_address + 0x14) == 0)
assert(emu:read16(task_address + 0x16) == 2)
assert(emu:read16(task_address + 0x18) == 0)
assert(emu:read32(task_address + 0x1C) == 0x0825A918)
assert(emu:read32(task_address + 0x20) == 0x0825A948)
assert(emu:read32(task_address + 0x24) == 0x08258CA0)
assert(emu:read32(task_address + 0x28) == 0)
write_file(
	output_dir .. "/task-before.bin",
	read_absolute_range(task_address, task_size),
	"wb"
)

renderer_breakpoint = emu:setBreakpoint(function()
	if capture_complete then
		return
	end
	local pointer = emu:readRegister("r8")
	if not relevant_renderer_pointer(pointer) then
		return
	end
	local raw_u16 = emu:read16(pointer)
	local signed_value = raw_u16
	if signed_value >= 0x8000 then
		signed_value = signed_value - 0x10000
	end
	renderer_loop_hits[#renderer_loop_hits + 1] = {
		cycle = tostring(emu:currentCycle()),
		pointer = pointer,
		raw_u16 = raw_u16,
		signed_value = signed_value,
	}

	if expected_trailer == "FBFF" and #renderer_loop_hits >= 4 then
		local first = renderer_loop_hits[1]
		local addresses_advance_by_component = true
		for index = 2, #renderer_loop_hits do
			if renderer_loop_hits[index].pointer
				~= renderer_loop_hits[index - 1].pointer + 0x14 then
				addresses_advance_by_component = false
			end
		end
		local success = first.pointer == anomalous_trailer_address
			and first.raw_u16 == 0xFBFF
			and first.signed_value == -1025
			and addresses_advance_by_component
		local payload = table.concat({
			'{"schema":"mgba-character-fbff-probe-v1"',
			',"run_id":', quoted(run_id),
			',"success":', success and "true" or "false",
			',"outcome":"renderer_continues_past_fbff"',
			',"input_state":', quoted(input_state),
			',"input_state_sha256":', quoted(input_state_sha256),
			',"rom_sha256":', quoted(rom_sha256),
			',"expected_trailer":"FBFF"',
			',"capture_frame":null',
			',"cycles":', tostring(emu:currentCycle()),
			',"task_address":"0x03005940"',
			',"injected_flags":"0xC0003601"',
			',"frame_pointer_table":"0x0825A918"',
			',"animation_pointer_table":"0x0825A948"',
			',"graphics_pointer":"0x08258CA0"',
			',"animation_id":0',
			',"keyframe_index":2',
			',"timer":0',
			',"tile_base":"0x0300"',
			',"palette_bank":14',
			',"anomalous_trailer_address":"0x0825A8E4"',
			',"anomalous_trailer_raw":"0xFBFF"',
			',"anomalous_trailer_signed":-1025',
			',"renderer_loop_hit_count":', tostring(#renderer_loop_hits),
			',"addresses_advance_by_component":',
				addresses_advance_by_component and "true" or "false",
			'}',
		})
		persist_result(payload)
	end
end, renderer_loop_address)

callbacks:add("frame", function()
	if capture_complete then
		return
	end
	frame = frame + 1
	if frame < capture_frame then
		return
	end

	local cycles = emu:currentCycle()
	local active_count = 0
	local valid_count = 0
	local pseudo_count = 0
	local signature_objects = {}
	for object_index = 0, 127 do
		local object_address = oam_address + object_index * 8
		local attr0 = emu:read16(object_address)
		local attr1 = emu:read16(object_address + 2)
		local attr2 = emu:read16(object_address + 4)
		if active_oam_entry(attr0) then
			active_count = active_count + 1
		end
		if attr2 == valid_component_attr2 then
			valid_count = valid_count + 1
		end
		if attr2 == first_pseudo_component_attr2 then
			pseudo_count = pseudo_count + 1
		end
		if attr2 == valid_component_attr2 or attr2 == first_pseudo_component_attr2 then
			signature_objects[#signature_objects + 1] = string.format(
				'{"index":%d,"attr0":"0x%04X","attr1":"0x%04X","attr2":"0x%04X"}',
				object_index,
				attr0,
				attr1,
				attr2
			)
		end
	end

	assert(emu:saveStateFile(output_dir .. "/output.ss9"))
	emu:screenshot(output_dir .. "/frame.png")

	local first_loop_hit = renderer_loop_hits[1]
	local behavior_matches_expectation = expected_trailer == "FFFF"
		and #renderer_loop_hits == capture_frame
		and first_loop_hit.pointer == anomalous_trailer_address
		and first_loop_hit.raw_u16 == 0xFFFF
		and first_loop_hit.signed_value == -1
		and renderer_loop_hits[#renderer_loop_hits].pointer
			== anomalous_trailer_address
		and renderer_loop_hits[#renderer_loop_hits].raw_u16 == 0xFFFF
		and valid_count >= 1
		and pseudo_count == 0
	local payload = table.concat({
		'{"schema":"mgba-character-fbff-probe-v1"',
		',"run_id":', quoted(run_id),
		',"success":', behavior_matches_expectation and "true" or "false",
		',"outcome":"renderer_stops_at_ffff"',
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"expected_trailer":', quoted(expected_trailer),
		',"capture_frame":', tostring(capture_frame),
		',"cycles":', tostring(cycles),
		',"task_address":"0x03005940"',
		',"injected_flags":"0xC0003601"',
		',"frame_pointer_table":"0x0825A918"',
		',"animation_pointer_table":"0x0825A948"',
		',"graphics_pointer":"0x08258CA0"',
		',"animation_id":0',
		',"keyframe_index":2',
		',"timer":0',
		',"tile_base":"0x0300"',
		',"palette_bank":14',
		',"valid_component_attr2":"0xE340"',
		',"first_pseudo_component_attr2":"0xFEFF"',
		',"active_oam_count":', tostring(active_count),
		',"valid_component_count":', tostring(valid_count),
		',"first_pseudo_component_count":', tostring(pseudo_count),
		',"signature_objects":[', table.concat(signature_objects, ","), "]",
		',"renderer_loop_hit_count":', tostring(#renderer_loop_hits),
		'}',
	})
	persist_result(payload)
end)
