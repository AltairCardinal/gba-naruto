-- Trace one generic 0x0853F140 sprite pair from loader through OAM composition.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local input_state = required_env("MAP_SPRITES_TRACE_INPUT_STATE")
local input_state_sha256 = required_env("MAP_SPRITES_TRACE_INPUT_STATE_SHA256")
local output_dir = required_env("MAP_SPRITES_TRACE_OUTPUT_DIR")
local done_marker = required_env("MAP_SPRITES_TRACE_DONE_MARKER")
local run_id = required_env("MAP_SPRITES_TRACE_RUN_ID")
local rom_sha256 = required_env("MAP_SPRITES_TRACE_ROM_SHA256")
local script_sha256 = required_env("MAP_SPRITES_TRACE_SCRIPT_SHA256")
local binary_sha256 = required_env("MAP_SPRITES_TRACE_BINARY_SHA256")
local frame_limit = assert(tonumber(required_env("MAP_SPRITES_TRACE_FRAME_LIMIT")))
local schedule_text = os.getenv("MAP_SPRITES_TRACE_INPUT_SCHEDULE") or ""
assert(frame_limit >= 1 and frame_limit <= 900 and frame_limit == math.floor(frame_limit))

local keys = {
	Down = C.GBA_KEY.DOWN,
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	L = C.GBA_KEY.L,
	R = C.GBA_KEY.R,
	Up = C.GBA_KEY.UP,
	Right = C.GBA_KEY.RIGHT,
	Left = C.GBA_KEY.LEFT,
	Start = C.GBA_KEY.START,
}

local function parse_schedule(value)
	local result = {}
	local previous_up = 0
	if value == "" then return result end
	for record in value:gmatch("[^,]+") do
		local key_name, down_text, up_text = record:match("^([A-Za-z]+):(%d+):(%d+)$")
		assert(key_name, "invalid input schedule record")
		local key = assert(keys[key_name], "unsupported input key")
		local down_frame = assert(tonumber(down_text))
		local up_frame = assert(tonumber(up_text))
		assert(down_frame > 0 and down_frame < up_frame, "invalid input interval")
		assert(down_frame >= previous_up, "input intervals overlap")
		assert(up_frame < frame_limit, "input interval exceeds frame limit")
		result[#result + 1] = {
			key_name = key_name,
			key = key,
			down_frame = down_frame,
			up_frame = up_frame,
		}
		previous_up = up_frame
	end
	return result
end

local inputs = parse_schedule(schedule_text)

local PAIR_TABLE = 0x0853F140
local PAIR_COUNT = 43
local TASK_POOL = 0x03003BB8
local TASK_SIZE = 0x3C
local TASK_COUNT = 128
local bootstrap_slot_text = os.getenv("MAP_SPRITES_TRACE_BOOTSTRAP_TASK_SLOT") or ""
local bootstrap_id_text = os.getenv("MAP_SPRITES_TRACE_BOOTSTRAP_ID") or ""
local bootstrap_expected_text = os.getenv("MAP_SPRITES_TRACE_BOOTSTRAP_EXPECTED_DEFINITION") or ""
assert(
	(bootstrap_slot_text == "" and bootstrap_id_text == "" and bootstrap_expected_text == "")
		or (bootstrap_slot_text ~= "" and bootstrap_id_text ~= "" and bootstrap_expected_text ~= ""),
	"controlled bootstrap variables must be supplied together"
)
local controlled_bootstrap = bootstrap_slot_text ~= ""
local bootstrap_slot = controlled_bootstrap and assert(tonumber(bootstrap_slot_text)) or -1
local bootstrap_id = controlled_bootstrap and assert(tonumber(bootstrap_id_text)) or -1
local bootstrap_expected_definition = controlled_bootstrap
	and assert(tonumber(bootstrap_expected_text)) or 0
if controlled_bootstrap then
	assert(bootstrap_slot >= 0 and bootstrap_slot < TASK_COUNT, "invalid bootstrap task slot")
	assert(bootstrap_id >= 0 and bootstrap_id < PAIR_COUNT, "invalid bootstrap pair id")
end
local targets = {
	{name = "generic-loader", address = 0x08080B08},
	{name = "pair-install", address = 0x08062668},
	{name = "frame-select", address = 0x0806298C},
	{name = "oam-compose", address = 0x08063108},
}

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex32(value)
	return string.format("0x%08X", (value or 0) % 0x100000000)
end

local frame = 0
local complete = false
local CONTROLLED_POST_BOUNDARY_FRAMES = 2
local boundary_complete_frame = -1
local events = {}
local breakpoint_ids = {}
local hit_names = {}
local target_task = 0
local target_id = -1

local function inputs_json()
	local rows = {}
	for _, input in ipairs(inputs) do
		rows[#rows + 1] = table.concat({
			'{"key":', q(input.key_name),
			',"down_frame":', tostring(input.down_frame),
			',"up_frame":', tostring(input.up_frame),
			',"hold_frames":', tostring(input.up_frame - input.down_frame), '}',
		})
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function event_json(event)
	return table.concat({
		'{"name":', q(event.name),
		',"address":', q(hex32(event.address)),
		',"frame":', tostring(event.frame),
		',"cycle":', q(event.cycle),
		',"r0":', q(hex32(event.r0)),
		',"r1":', q(hex32(event.r1)),
		',"r2":', q(hex32(event.r2)),
		',"r3":', q(hex32(event.r3)),
		',"r4":', q(hex32(event.r4)),
		',"r5":', q(hex32(event.r5)),
		',"r6":', q(hex32(event.r6)),
		',"r7":', q(hex32(event.r7)),
		',"r8":', q(hex32(event.r8)),
		',"sp":', q(hex32(event.sp)),
		',"lr":', q(hex32(event.lr)),
		',"selected_id":', tostring(event.selected_id),
		',"task":', q(hex32(event.task)),
		',"definition":', q(hex32(event.definition)),
		',"animation":', q(hex32(event.animation)),
		',"task_definition":', q(hex32(event.task_definition)),
		',"task_animation":', q(hex32(event.task_animation)),
		',"task_flags":', q(hex32(event.task_flags)),
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
		'{"schema":"map-sprites-runtime-trace-v1"',
		',"run_id":', q(run_id),
		',"outcome":', q(outcome),
		',"frame":', tostring(frame),
		',"frame_limit":', tostring(frame_limit),
		',"input_mode":', q(#inputs == 0 and "zero-input-active-state" or "scheduled-input-active-state"),
		',"inputs":', inputs_json(),
		',"recovery_inputs":[]',
		',"input_state":', q(input_state),
		',"input_state_sha256":', q(input_state_sha256),
		',"rom_sha256":', q(rom_sha256),
		',"script_sha256":', q(script_sha256),
		',"binary_sha256":', q(binary_sha256),
		',"pair_table":', q(hex32(PAIR_TABLE)),
		',"controlled_task_materialization":', tostring(controlled_bootstrap),
		',"bootstrap_task_slot":', tostring(bootstrap_slot),
		',"bootstrap_expected_definition":', q(hex32(bootstrap_expected_definition)),
		',"post_boundary_frames":', tostring(controlled_bootstrap and CONTROLLED_POST_BOUNDARY_FRAMES or 0),
		',"target_task":', q(hex32(target_task)),
		',"target_id":', tostring(target_id),
		',"required_hit_count":', tostring(controlled_bootstrap and 3 or #targets),
		',"hit_count":', tostring(#events),
		',"events":[', table.concat(rows, ','), ']}',
	})
	local audit_file = assert(io.open(output_dir .. "/audit.json", "w"))
	audit_file:write(audit)
	audit_file:close()
	local done = assert(io.open(done_marker, "w"))
	done:write('{"run_id":' .. q(run_id) .. ',"status":' .. q(outcome)
		.. ',"target_id":' .. tostring(target_id)
		.. ',"hit_count":' .. tostring(#events) .. '}')
	done:close()
end

local function capture(name, address, selected_id, task)
	local definition = 0
	local animation = 0
	local task_definition = 0
	local task_animation = 0
	local task_flags = 0
	if selected_id >= 0 and selected_id < PAIR_COUNT then
		definition = emu:read32(PAIR_TABLE + selected_id * 8)
		animation = emu:read32(PAIR_TABLE + selected_id * 8 + 4)
	end
	if task >= TASK_POOL and task < TASK_POOL + TASK_SIZE * TASK_COUNT then
		task_flags = emu:read32(task)
		task_definition = emu:read32(task + 0x1C)
		task_animation = emu:read32(task + 0x20)
	end
	events[#events + 1] = {
		name = name,
		address = address,
		frame = frame,
		cycle = tostring(emu:currentCycle()),
		r0 = emu:readRegister("r0") or 0,
		r1 = emu:readRegister("r1") or 0,
		r2 = emu:readRegister("r2") or 0,
		r3 = emu:readRegister("r3") or 0,
		r4 = emu:readRegister("r4") or 0,
		r5 = emu:readRegister("r5") or 0,
		r6 = emu:readRegister("r6") or 0,
		r7 = emu:readRegister("r7") or 0,
		r8 = emu:readRegister("r8") or 0,
		sp = emu:readRegister("sp") or 0,
		lr = emu:readRegister("lr") or 0,
		selected_id = selected_id,
		task = task,
		definition = definition,
		animation = animation,
		task_definition = task_definition,
		task_animation = task_animation,
		task_flags = task_flags,
	}
	hit_names[name] = true
	if controlled_bootstrap and hit_names["controlled-bootstrap"]
		and hit_names["frame-select"] and hit_names["oam-compose"] then
		if boundary_complete_frame < 0 then boundary_complete_frame = frame end
	elseif not controlled_bootstrap and hit_names["generic-loader"] and hit_names["pair-install"]
		and hit_names["frame-select"] and hit_names["oam-compose"] then
		finish("all-boundaries-hit")
	end
end

assert(emu:loadStateFile(input_state), "failed to load map-sprites trace input state")
emu:setKeys(0)

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if controlled_bootstrap or complete or hit_names["generic-loader"] then return end
	local selected_id = (emu:readRegister("r1") or 0) % 256
	capture("generic-loader", 0x08080B08, selected_id, 0)
end, 0x08080B08))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if controlled_bootstrap or complete or hit_names["pair-install"] then return end
	local sp = emu:readRegister("sp") or 0
	local base = emu:read32(sp)
	local selected_id = emu:readRegister("r7") or -1
	local task = emu:readRegister("r4") or 0
	if base == PAIR_TABLE and selected_id >= 0 and selected_id < PAIR_COUNT
		and task >= TASK_POOL and task < TASK_POOL + TASK_SIZE * TASK_COUNT then
		target_id = selected_id
		target_task = task
		capture("pair-install", 0x08062668, selected_id, task)
	end
end, 0x08062668))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or hit_names["frame-select"] or target_task == 0 then return end
	local task = emu:readRegister("r7") or 0
	if task == target_task then capture("frame-select", 0x0806298C, target_id, task) end
end, 0x0806298C))

breakpoint_ids[#breakpoint_ids + 1] = assert(emu:setBreakpoint(function()
	if complete or hit_names["oam-compose"] or target_task == 0 then return end
	local task = emu:readRegister("r7") or 0
	if task == target_task then capture("oam-compose", 0x08063108, target_id, task) end
end, 0x08063108))

for _, breakpoint_id in ipairs(breakpoint_ids) do
	assert(breakpoint_id > 0, "failed to install map-sprites trace breakpoint")
end

if controlled_bootstrap then
	target_id = bootstrap_id
	target_task = TASK_POOL + bootstrap_slot * TASK_SIZE
	local table_definition = emu:read32(PAIR_TABLE + bootstrap_id * 8)
	local table_animation = emu:read32(PAIR_TABLE + bootstrap_id * 8 + 4)
	assert(emu:read32(target_task + 0x1C) == bootstrap_expected_definition,
		"bootstrap task definition mismatch")
	assert(emu:read32(target_task + 0x20) == table_animation,
		"bootstrap task animation mismatch")
	local task_flags = emu:read8(target_task)
	assert((task_flags & 0xFC) == 0x48, "bootstrap task flags mismatch")
	emu:write8(target_task, task_flags | 1)
	for byte = 0, 3 do
		emu:write8(target_task + 0x1C + byte, (table_definition >> (byte * 8)) & 0xFF)
	end
	capture("controlled-bootstrap", 0, target_id, target_task)
end

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	for _, input in ipairs(inputs) do
		if frame == input.down_frame then emu:addKey(input.key) end
		if frame == input.up_frame then emu:clearKey(input.key) end
	end
	if controlled_bootstrap and boundary_complete_frame >= 0
		and frame >= boundary_complete_frame + CONTROLLED_POST_BOUNDARY_FRAMES then
		finish("all-downstream-boundaries-hit")
	elseif frame >= frame_limit then
		finish("frame-limit")
	end
end)

while not complete do emu:frameAdvance() end
