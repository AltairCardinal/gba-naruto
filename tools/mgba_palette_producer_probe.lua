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

local function read_absolute_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function is_readable_state_pointer(address)
	local state_end = address + 0x2C + 16
	return (address >= 0x02000000 and state_end <= 0x02040000)
		or (address >= 0x03000000 and state_end <= 0x03008000)
end

local input_state = required_env("MGBA_PALETTE_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_PALETTE_INPUT_STATE_SHA256")
local input_key = required_env("MGBA_PALETTE_INPUT_KEY")
local input_down_frame = assert(tonumber(required_env("MGBA_PALETTE_INPUT_DOWN_FRAME")))
local input_up_frame = assert(tonumber(required_env("MGBA_PALETTE_INPUT_UP_FRAME")))
local rom_sha256 = required_env("MGBA_PALETTE_ROM_SHA256")
local output_dir = required_env("MGBA_PALETTE_OUTPUT_DIR")
local done_marker = required_env("MGBA_PALETTE_DONE_MARKER")
local run_id = required_env("MGBA_PALETTE_RUN_ID")

local enqueue_callsite = 0x08096536
local enqueue_helper = 0x080635B8
local enqueue_return = 0x0809653B
local scratch_start = 0x02002880
local scratch_end = 0x02002900
local scratch_size = scratch_end - scratch_start
local portrait_slot_table = 0x03005E50
local max_write_events = 1024
local timeout_frames = 240

assert(input_key == "None" or input_key == "A", "input key must be None or A")
assert(
	input_down_frame == math.floor(input_down_frame)
		and input_up_frame == math.floor(input_up_frame),
	"input frames must be integers"
)
if input_key == "None" then
	assert(input_down_frame == 0 and input_up_frame == 0, "None input frames must be zero")
else
	assert(
		0 < input_down_frame
			and input_down_frame < input_up_frame
			and input_up_frame < timeout_frames,
		"invalid A input frame order"
	)
end
local input_key_code = input_key == "A" and C.GBA_KEY.A or nil

local frame = 0
local capture_complete = false
local enqueue_breakpoint = nil
local scratch_watchpoint = nil
local trace_breakpoints = {}
local write_events = {}
local trace_events = {}
local trace_points = {
	{ name = "chapter_opcode_17", address = 0x08097966 },
	{ name = "portrait_transition_helper", address = 0x08096B74 },
	{ name = "portrait_mode_dispatch", address = 0x08096B9C },
	{ name = "palette_fill_mode_0", address = 0x08096BD4 },
	{ name = "palette_fill_mode_0_complete", address = 0x08096BE4 },
	{
		name = "palette_fill_cpuset_wrapper",
		address = 0x0809C0E0,
		expected_lr = 0x08096BE5,
	},
	{ name = "portrait_state_0x40", address = 0x0809651C },
}

local function inputs_json()
	if input_key == "None" then
		return "[]"
	end
	return table.concat({
		'[{"key":', quoted(input_key),
		',"down_frame":', tostring(input_down_frame),
		',"up_frame":', tostring(input_up_frame),
		',"hold_frames":', tostring(input_up_frame - input_down_frame),
		"}]",
	})
end

local function provenance_json()
	return table.concat({
		'"run_id":', quoted(run_id),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"inputs":', inputs_json(),
	})
end

local function writes_json()
	local rows = {}
	for index, event in ipairs(write_events) do
		rows[#rows + 1] = string.format(
			'{"index":%d,"frame":%d,"cycle":%s,"pc":"0x%08X",'
				.. '"lr":"0x%08X","address":"0x%08X","old_value":%d,'
				.. '"new_value":%d,"width":%d}',
			index,
			event.frame,
			event.cycle,
			event.pc,
			event.lr,
			event.address,
			event.old_value,
			event.new_value,
			event.width
		)
	end
	return table.concat({
		'{"schema":"mgba-palette-producer-writes-v1","events":[',
		table.concat(rows, ","),
		"]}",
	})
end

local function trace_json()
	local rows = {}
	for index, event in ipairs(trace_events) do
		rows[#rows + 1] = string.format(
			'{"index":%d,"name":%s,"address":"0x%08X","frame":%d,'
				.. '"cycle":%s,"pc":"0x%08X","lr":"0x%08X",'
				.. '"r0":"0x%08X","r1":"0x%08X","r2":"0x%08X",'
				.. '"r4":"0x%08X","r7":"0x%08X",'
				.. '"slot0":"0x%08X","slot1":"0x%08X",'
				.. '"target_slot":"0x%08X","scratch_first":%d,'
				.. '"scratch_second":%d}',
			index,
			quoted(event.name),
			event.address,
			event.frame,
			event.cycle,
			event.pc,
			event.lr,
			event.r0,
			event.r1,
			event.r2,
			event.r4,
			event.r7,
			event.slot0,
			event.slot1,
			event.target_slot,
			event.scratch_first,
			event.scratch_second
		)
	end
	return table.concat({
		'{"schema":"mgba-palette-producer-trace-v1","events":[',
		table.concat(rows, ","),
		"]}",
	})
end

local function clear_observers()
	if enqueue_breakpoint then
		emu:clearBreakpoint(enqueue_breakpoint)
		enqueue_breakpoint = nil
	end
	for _, breakpoint_id in ipairs(trace_breakpoints) do
		emu:clearBreakpoint(breakpoint_id)
	end
	trace_breakpoints = {}
	if scratch_watchpoint then
		emu:clearBreakpoint(scratch_watchpoint)
		scratch_watchpoint = nil
	end
end

local function persist_hit()
	if capture_complete then
		return
	end
	capture_complete = true

	local r0 = emu:readRegister("r0")
	local r1 = emu:readRegister("r1")
	local r2 = emu:readRegister("r2")
	local r4 = emu:readRegister("r4")
	local lr = emu:readRegister("lr")
	local pc = emu:readRegister("pc")
	local cycle = tostring(emu:currentCycle())
	local state = emu:read8(r4)
	local record_id = emu:read8(r4 + 2)
	local variant_id = emu:read8(r4 + 3)
	local palette_bank = emu:read8(r4 + 7)
	local tick = emu:read16(r4 + 8)
	local slot0 = emu:read32(portrait_slot_table)
	local slot1 = emu:read32(portrait_slot_table + 4)
	local arguments_match = lr == enqueue_return
		and r0 == scratch_start and r2 == scratch_size
		and r1 == 0x05000200 + palette_bank * 32
		and state == 0x40

	clear_observers()
	write_file(
		output_dir .. "/scratch.bin",
		read_absolute_range(scratch_start, scratch_size),
		"wb"
	)
	write_file(output_dir .. "/portrait-state.bin", read_absolute_range(r4, 16), "wb")
	write_file(output_dir .. "/writes.json", writes_json())
	write_file(output_dir .. "/trace.json", trace_json())
	assert(emu:saveStateFile(output_dir .. "/hit.ss9"))
	emu:screenshot(output_dir .. "/hit.png")

	local payload = table.concat({
		'{"schema":"mgba-palette-producer-probe-v1"',
		',"run_id":', quoted(run_id),
		',"success":', arguments_match and "true" or "false",
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"inputs":', inputs_json(),
		',"callsite":"0x08096536"',
		',"frame":', tostring(frame),
		',"cycle":', cycle,
		',"pc":', quoted(string.format("0x%08X", pc)),
		',"lr":', quoted(string.format("0x%08X", lr)),
		',"r0":', quoted(string.format("0x%08X", r0)),
		',"r1":', quoted(string.format("0x%08X", r1)),
		',"r2":', quoted(string.format("0x%08X", r2)),
		',"r4":', quoted(string.format("0x%08X", r4)),
		',"state":', tostring(state),
		',"record_id":', tostring(record_id),
		',"variant_id":', tostring(variant_id),
		',"palette_bank":', tostring(palette_bank),
		',"tick":', tostring(tick),
		',"slot0":', quoted(string.format("0x%08X", slot0)),
		',"slot1":', quoted(string.format("0x%08X", slot1)),
		',"write_event_count":', tostring(#write_events),
		',"arguments_match":', arguments_match and "true" or "false",
		'}',
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)

scratch_watchpoint = emu:setRangeWatchpoint(
	function(info)
		if capture_complete or #write_events >= max_write_events then
			return
		end
		write_events[#write_events + 1] = {
			frame = frame,
			cycle = tostring(emu:currentCycle()),
			pc = emu:readRegister("pc"),
			lr = emu:readRegister("lr"),
			address = info.address or 0,
			old_value = info.oldValue or -1,
			new_value = info.newValue or -1,
			width = info.width or -1,
		}
	end,
	scratch_start,
	scratch_end,
	C.WATCHPOINT_TYPE.WRITE_CHANGE
)
assert(
	scratch_watchpoint and scratch_watchpoint > 0,
	"failed to install scratch range watchpoint"
)

enqueue_breakpoint = emu:setBreakpoint(function()
	if emu:readRegister("lr") == enqueue_return then
		persist_hit()
	end
end, enqueue_helper)
assert(
	enqueue_breakpoint and enqueue_breakpoint > 0,
	"failed to install enqueue breakpoint"
)

for _, point in ipairs(trace_points) do
	local trace_point = point
	local breakpoint_id = emu:setBreakpoint(function()
		if capture_complete then
			return
		end
		local current_lr = emu:readRegister("lr")
		if trace_point.expected_lr and current_lr ~= trace_point.expected_lr then
			return
		end
		local current_r0 = emu:readRegister("r0")
		trace_events[#trace_events + 1] = {
			name = trace_point.name,
			address = trace_point.address,
			frame = frame,
			cycle = tostring(emu:currentCycle()),
			pc = emu:readRegister("pc"),
			lr = current_lr,
			r0 = current_r0,
			r1 = emu:readRegister("r1"),
			r2 = emu:readRegister("r2"),
			r4 = emu:readRegister("r4"),
			r7 = emu:readRegister("r7"),
			slot0 = emu:read32(portrait_slot_table),
			slot1 = emu:read32(portrait_slot_table + 4),
			target_slot = current_r0 <= 1
				and emu:read32(portrait_slot_table + current_r0 * 4)
				or 0,
			scratch_first = emu:read16(scratch_start),
			scratch_second = emu:read16(scratch_start + 2),
		}
	end, trace_point.address)
	assert(
		breakpoint_id and breakpoint_id > 0,
		"failed to install trace breakpoint " .. trace_point.name
	)
	trace_breakpoints[#trace_breakpoints + 1] = breakpoint_id
end

write_file(
	output_dir .. "/startup.json",
	table.concat({
		'{"schema":"mgba-palette-producer-startup-v1",',
		provenance_json(),
		',"scratch_watchpoint":', tostring(scratch_watchpoint),
		',"enqueue_breakpoint":', tostring(enqueue_breakpoint),
		'}',
	})
)

callbacks:add("frame", function()
	if capture_complete then
		return
	end
	frame = frame + 1
	if frame == input_down_frame then
		emu:addKey(input_key_code)
	elseif frame == input_up_frame then
		emu:clearKey(input_key_code)
	end
	if frame % 60 == 0 then
		console:log(string.format(
			"palette-producer progress frame=%d writes=%d",
			frame,
			#write_events
		))
	end
	if frame >= timeout_frames then
		capture_complete = true
		clear_observers()
		write_file(output_dir .. "/scratch.bin", read_absolute_range(
			scratch_start,
			scratch_size
		), "wb")
		write_file(output_dir .. "/writes.json", writes_json())
		write_file(output_dir .. "/trace.json", trace_json())
		local slot0 = emu:read32(portrait_slot_table)
		local slot1 = emu:read32(portrait_slot_table + 4)
		write_file(
			output_dir .. "/portrait-slots.bin",
			read_absolute_range(portrait_slot_table, 8),
			"wb"
		)
		write_file(
			output_dir .. "/portrait-slot0-state.bin",
			is_readable_state_pointer(slot0)
				and read_absolute_range(slot0 + 0x2C, 16)
				or "",
			"wb"
		)
		write_file(
			output_dir .. "/portrait-slot1-state.bin",
			is_readable_state_pointer(slot1)
				and read_absolute_range(slot1 + 0x2C, 16)
				or "",
			"wb"
		)
		assert(emu:saveStateFile(output_dir .. "/timeout.ss9"))
		emu:screenshot(output_dir .. "/timeout.png")
		local payload = table.concat({
			'{"schema":"mgba-palette-producer-probe-v1",',
			provenance_json(),
			',"success":false',
			',"outcome":"timeout"',
			',"frames":', tostring(frame),
			',"write_event_count":', tostring(#write_events),
			',"slot0":', quoted(string.format("0x%08X", slot0)),
			',"slot1":', quoted(string.format("0x%08X", slot1)),
			'}',
		})
		write_file(output_dir .. "/audit.json", payload)
		write_file(done_marker, payload)
	end
end)
