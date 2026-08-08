-- Trace natural C3 expiry through map-events E4 primary dispatch and group-3 rendering.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local input_state = required_env("MAP_EVENTS_E4_INPUT_STATE")
local input_state_sha256 = required_env("MAP_EVENTS_E4_INPUT_STATE_SHA256")
local output_dir = required_env("MAP_EVENTS_E4_OUTPUT_DIR")
local done_marker = required_env("MAP_EVENTS_E4_DONE_MARKER")
local run_id = required_env("MAP_EVENTS_E4_RUN_ID")
local rom_sha256 = required_env("MAP_EVENTS_E4_ROM_SHA256")
local script_sha256 = required_env("MAP_EVENTS_E4_SCRIPT_SHA256")
local binary_sha256 = required_env("MAP_EVENTS_E4_BINARY_SHA256")
local expected_handler = assert(tonumber(required_env("MAP_EVENTS_E4_EXPECTED_HANDLER")))
local expect_group3 = required_env("MAP_EVENTS_E4_EXPECT_GROUP3") == "1"
local frame_limit = assert(tonumber(required_env("MAP_EVENTS_E4_FRAME_LIMIT")))
assert(frame_limit >= 70 and frame_limit <= 600 and frame_limit == math.floor(frame_limit))

local EXPIRY_ACTION_READ = 0x08081D74
local TABLE_ADDRESS_READY = 0x0807FD36
local TABLE_HANDLER_LOADED = 0x0807FD38
local INDIRECT_TRAMPOLINE = 0x0809C114
local NATIVE_GROUP3_HANDLER = 0x0807F208
local GROUP3_RENDERER_POST = 0x08063328
local E4_ENTRY_ADDRESS = 0x0853EDB8
local GROUP3_DEFINITION = 0x083425D8
local GROUP3_ANIMATION = 0x083426CC
local TASK_POOL = 0x03003BB8
local TASK_SIZE = 0x3C
local TASK_COUNT = 128
local POST_DISPATCH_FRAMES = 3

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex32(value)
	return string.format("0x%08X", (value or 0) % 0x100000000)
end

local function write_file(path, payload)
	local file = assert(io.open(path, "w"))
	file:write(payload)
	file:close()
end

local function find_group3_task()
	for slot = 0, TASK_COUNT - 1 do
		local task = TASK_POOL + slot * TASK_SIZE
		if emu:read32(task) & 1 ~= 0
			and emu:read32(task + 0x1C) == GROUP3_DEFINITION
			and emu:read32(task + 0x20) == GROUP3_ANIMATION then
			return slot, task, emu:read32(task)
		end
	end
	return -1, 0, 0
end

local frame = 0
local complete = false
local expiry_seen = false
local table_address_seen = false
local table_handler_seen = false
local dispatch_seen = false
local native_handler_seen = false
local group3_seen = false
local dispatch_frame = -1
local events = {}
local breakpoint_ids = {}

local function capture(name, address, extra)
	local event = {
		name = name,
		address = address,
		frame = frame,
		cycle = tostring(emu:currentCycle()),
		r0 = emu:readRegister("r0") or 0,
		r1 = emu:readRegister("r1") or 0,
		r7 = emu:readRegister("r7") or 0,
		r8 = emu:readRegister("r8") or 0,
		r9 = emu:readRegister("r9") or 0,
		lr = emu:readRegister("lr") or 0,
		extra = extra or {},
	}
	events[#events + 1] = event
end

local function event_json(event)
	local extra = event.extra
	return table.concat({
		'{"name":', q(event.name),
		',"address":', q(hex32(event.address)),
		',"frame":', tostring(event.frame),
		',"cycle":', q(event.cycle),
		',"r0":', q(hex32(event.r0)),
		',"r1":', q(hex32(event.r1)),
		',"r7":', q(hex32(event.r7)),
		',"r8":', q(hex32(event.r8)),
		',"r9":', q(hex32(event.r9)),
		',"lr":', q(hex32(event.lr)),
		',"encoded_action":', q(hex32(extra.encoded_action or 0)),
		',"table_entry_address":', q(hex32(extra.table_entry_address or 0)),
		',"table_handler":', q(hex32(extra.table_handler or 0)),
		',"task_slot":', tostring(extra.task_slot or -1),
		',"task_address":', q(hex32(extra.task_address or 0)),
		',"task_flags":', q(hex32(extra.task_flags or 0)),
		'}',
	})
end

local function finish(outcome)
	if complete then return end
	complete = true
	emu:setKeys(0)
	for _, breakpoint_id in ipairs(breakpoint_ids) do
		pcall(function() emu:clearBreakpoint(breakpoint_id) end)
	end
	assert(emu:saveStateFile(output_dir .. "/final.ss9"), "failed to save trace state")
	emu:screenshot(output_dir .. "/final.png")
	local rows = {}
	for _, event in ipairs(events) do rows[#rows + 1] = event_json(event) end
	local audit = table.concat({
		'{"schema":"map-events-e4-runtime-trace-v1"',
		',"run_id":', q(run_id),
		',"outcome":', q(outcome),
		',"frame":', tostring(frame),
		',"frame_limit":', tostring(frame_limit),
		',"post_dispatch_frames":', tostring(POST_DISPATCH_FRAMES),
		',"input_mode":"zero-input-natural-expiry"',
		',"inputs":[]',
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"input_state":', q(input_state),
		',"input_state_sha256":', q(input_state_sha256),
		',"rom_sha256":', q(rom_sha256),
		',"script_sha256":', q(script_sha256),
		',"binary_sha256":', q(binary_sha256),
		',"expected_handler":', q(hex32(expected_handler)),
		',"expect_group3":', tostring(expect_group3),
		',"expiry_seen":', tostring(expiry_seen),
		',"table_address_seen":', tostring(table_address_seen),
		',"table_handler_seen":', tostring(table_handler_seen),
		',"dispatch_seen":', tostring(dispatch_seen),
		',"native_handler_seen":', tostring(native_handler_seen),
		',"group3_seen":', tostring(group3_seen),
		',"events":[', table.concat(rows, ','), ']}'
	})
	write_file(output_dir .. "/audit.json", audit)
	write_file(done_marker, '{"run_id":' .. q(run_id) .. ',"status":' .. q(outcome) .. '}')
end

assert(emu:loadStateFile(input_state), "failed to load E4 trace input state")
emu:setKeys(0)

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or expiry_seen then return end
	local object = emu:readRegister("r8") or 0
	local encoded_action = object ~= 0 and emu:read8(object + 4) or 0
	if encoded_action == 0xC3 then
		expiry_seen = true
		capture("c3-expiry", EXPIRY_ACTION_READ, {encoded_action = encoded_action})
	end
end, EXPIRY_ACTION_READ))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or table_address_seen then return end
	local entry = emu:readRegister("r0") or 0
	if entry == E4_ENTRY_ADDRESS and emu:read32(entry) == expected_handler then
		table_address_seen = true
		capture("e4-table-address", TABLE_ADDRESS_READY, {
			table_entry_address = entry,
			table_handler = emu:read32(entry),
		})
	end
end, TABLE_ADDRESS_READY))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or table_handler_seen or not table_address_seen then return end
	local handler = emu:readRegister("r1") or 0
	if handler == expected_handler then
		table_handler_seen = true
		capture("e4-handler-loaded", TABLE_HANDLER_LOADED, {
			table_entry_address = E4_ENTRY_ADDRESS,
			table_handler = handler,
		})
	end
end, TABLE_HANDLER_LOADED))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or dispatch_seen or not table_handler_seen then return end
	local handler = emu:readRegister("r1") or 0
	if handler == expected_handler then
		dispatch_seen = true
		dispatch_frame = frame
		capture("e4-trampoline", INDIRECT_TRAMPOLINE, {
			table_entry_address = E4_ENTRY_ADDRESS,
			table_handler = handler,
		})
	end
end, INDIRECT_TRAMPOLINE))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or native_handler_seen then return end
	native_handler_seen = true
	capture("native-group3-handler", NATIVE_GROUP3_HANDLER, {})
end, NATIVE_GROUP3_HANDLER))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or group3_seen then return end
	local slot, task, flags = find_group3_task()
	if slot >= 0 then
		group3_seen = true
		capture("group3-renderer", GROUP3_RENDERER_POST, {
			task_slot = slot,
			task_address = task,
			task_flags = flags,
		})
	end
end, GROUP3_RENDERER_POST))

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	emu:setKeys(0)
	if dispatch_seen and frame >= dispatch_frame + POST_DISPATCH_FRAMES then
		if group3_seen == expect_group3 then
			finish("post-dispatch-window-complete")
		else
			finish("group3-contract-mismatch")
		end
	elseif frame >= frame_limit then
		finish("frame-limit")
	end
end)
