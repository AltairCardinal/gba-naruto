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

local input_state = required_env("MGBA_EFFECT_PHASE_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_EFFECT_PHASE_INPUT_STATE_SHA256")
local output_dir = required_env("MGBA_EFFECT_PHASE_OUTPUT_DIR")
local done_marker = required_env("MGBA_EFFECT_PHASE_DONE_MARKER")
local run_id = required_env("MGBA_EFFECT_PHASE_RUN_ID")
local rom_sha256 = required_env("MGBA_EFFECT_PHASE_ROM_SHA256")
local input_schedule = os.getenv("MGBA_EFFECT_PHASE_INPUT_SCHEDULE") or ""
local input_mode = required_env("MGBA_EFFECT_PHASE_INPUT_MODE")
local expected_group_id = assert(tonumber(required_env("MGBA_EFFECT_PHASE_GROUP_ID")))
local expected_definition = assert(tonumber(required_env("MGBA_EFFECT_PHASE_DEFINITION_POINTER")))
local expected_animation = assert(tonumber(required_env("MGBA_EFFECT_PHASE_ANIMATION_POINTER")))
local capture_frames = assert(tonumber(required_env("MGBA_EFFECT_PHASE_CAPTURE_FRAMES")))
local timeout_frames = assert(tonumber(required_env("MGBA_EFFECT_PHASE_TIMEOUT_FRAMES")))

local TASK_POOL_BASE = 0x03003BB8
local TASK_RECORD_SIZE = 0x3C
local TASK_SLOT_COUNT = 128
local TASK_POOL_SIZE = TASK_RECORD_SIZE * TASK_SLOT_COUNT
local ACTIVE_TASK_COUNT = 0x03005BB8
local ACTIVE_TASK_POINTERS = 0x030059B8
local RUNTIME_OFFSETS = 0x03000054
local SHADOW_OAM = 0x0300027C
local HARDWARE_OAM = 0x07000000
local OAM_SIZE = 0x400
local SUBMISSION_PENDING = 0x0300067C
local VRAM_BASE = 0x06000000
local VRAM_SIZE = 0x18000
local PRAM_BASE = 0x05000000
local PRAM_SIZE = 0x400
local IO_BASE = 0x04000000
local IO_SIZE = 0x400

local RENDERER_POST = 0x08063328
local SUBMIT_POST = 0x08061126
local ACK_POST = 0x080612AA

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

local events = {}
local previous_up = 0
assert(input_mode == "explicit-single-input"
	or input_mode == "explicit-input-sequence"
	or input_mode == "zero-input-active-state",
	"invalid input mode")
for encoded in input_schedule:gmatch("([^,]+)") do
	local key_name, down_text, up_text = encoded:match("^([A-Za-z]+):(%d+):(%d+)$")
	assert(key_name and down_text and up_text, "invalid input schedule event")
	local key = assert(keys[key_name], "invalid input schedule key")
	local down_frame = assert(tonumber(down_text))
	local up_frame = assert(tonumber(up_text))
	assert(down_frame > 0 and down_frame < up_frame, "invalid input interval")
	assert(down_frame >= previous_up, "input intervals overlap")
	assert(up_frame < capture_frames, "input interval exceeds capture frame")
	events[#events + 1] = {
		key_name = key_name,
		key = key,
		down_frame = down_frame,
		up_frame = up_frame,
	}
	previous_up = up_frame
end
if input_mode == "explicit-single-input" then
	assert(#events == 1, "explicit input mode requires exactly one event")
elseif input_mode == "explicit-input-sequence" then
	assert(#events >= 1, "explicit input sequence requires at least one event")
else
	assert(#events == 0, "zero-input active state must not schedule inputs")
end
assert(capture_frames >= 0 and capture_frames == math.floor(capture_frames))
assert(timeout_frames > capture_frames and timeout_frames == math.floor(timeout_frames))
assert(expected_group_id >= 1 and expected_group_id <= 18)
write_file(output_dir .. "/startup-environment.json", '{"stage":"environment"}')

local function read_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function inputs_json()
	local rows = {}
	for _, event in ipairs(events) do
		rows[#rows + 1] = table.concat({
			'{"key":', quoted(event.key_name),
			',"down_frame":', tostring(event.down_frame),
			',"up_frame":', tostring(event.up_frame),
			',"hold_frames":', tostring(event.up_frame - event.down_frame),
			'}',
		})
	end
	return '[' .. table.concat(rows, ',') .. ']'
end

local function matching_active_task()
	for slot = 0, TASK_SLOT_COUNT - 1 do
		local address = TASK_POOL_BASE + slot * TASK_RECORD_SIZE
		local flags = emu:read32(address)
		local definition = emu:read32(address + 0x1C)
		local animation = emu:read32(address + 0x20)
		if flags & 1 ~= 0
			and definition == expected_definition
			and animation == expected_animation then
			return slot, address, flags
		end
	end
	return nil, nil, nil
end

local frame = 0
local phase_index = 0
local complete = false
local breakpoint_ids = {}
local phases = {}
local renderer_hit_count = 0
local submission_watch_hit_count = 0
local ack_hit_count = 0
local submit_breakpoint = nil

local function phase_prefix(name)
	return output_dir .. "/" .. name .. "/capture"
end

local function capture_phase(name, address, copy_route, task_slot, task_address, flags)
	local prefix = phase_prefix(name)
	local cycle = tostring(emu:currentCycle())
	write_file(prefix .. "-task-pool.bin", read_range(TASK_POOL_BASE, TASK_POOL_SIZE), "wb")
	write_file(prefix .. "-active-count.bin", read_range(ACTIVE_TASK_COUNT, 1), "wb")
	write_file(prefix .. "-active-pointers.bin", read_range(ACTIVE_TASK_POINTERS, 0x200), "wb")
	write_file(prefix .. "-runtime-offsets.bin", read_range(RUNTIME_OFFSETS, 0x20), "wb")
	write_file(prefix .. "-shadow-oam.bin", read_range(SHADOW_OAM, OAM_SIZE), "wb")
	write_file(prefix .. "-hardware-oam.bin", read_range(HARDWARE_OAM, OAM_SIZE), "wb")
	write_file(prefix .. "-submission.bin", read_range(SUBMISSION_PENDING, 2), "wb")
	write_file(prefix .. "-vram.bin", read_range(VRAM_BASE, VRAM_SIZE), "wb")
	write_file(prefix .. "-pram.bin", read_range(PRAM_BASE, PRAM_SIZE), "wb")
	write_file(prefix .. "-io.bin", read_range(IO_BASE, IO_SIZE), "wb")
	assert(emu:saveStateFile(prefix .. ".ss9"), "failed to save phase state")
	emu:screenshot(prefix .. ".png")
	local payload = table.concat({
		'{"name":', quoted(name),
		',"address":', quoted(string.format("0x%08X", address)),
		',"frame":', tostring(frame),
		',"cycle":', quoted(cycle),
		',"copy_route":', copy_route and quoted(copy_route) or "null",
		',"task_slot":', tostring(task_slot),
		',"task_address":', quoted(string.format("0x%08X", task_address)),
		',"task_flags":', quoted(string.format("0x%08X", flags)),
		',"pending":', tostring(emu:read8(SUBMISSION_PENDING)),
		'}',
	})
	write_file(prefix .. "-phase.json", payload)
	phases[#phases + 1] = payload
end

local function clear_breakpoints()
	for _, breakpoint_id in ipairs(breakpoint_ids) do
		emu:clearBreakpoint(breakpoint_id)
	end
	breakpoint_ids = {}
end

local function finish(outcome)
	if complete then
		return
	end
	complete = true
	emu:setKeys(0)
	clear_breakpoints()
	if outcome ~= "three-phase-captured" then
		write_file(output_dir .. "/timeout-task-pool.bin", read_range(TASK_POOL_BASE, TASK_POOL_SIZE), "wb")
		assert(emu:saveStateFile(output_dir .. "/timeout.ss9"), "failed to save timeout state")
		emu:screenshot(output_dir .. "/timeout.png")
	end
	local payload = table.concat({
		'{"schema":"mgba-battle-effect-phase-capture-v1"',
		',"run_id":', quoted(run_id),
		',"outcome":', quoted(outcome),
		',"group_id":', tostring(expected_group_id),
		',"definition_pointer":', quoted(string.format("0x%08X", expected_definition)),
		',"animation_pointer":', quoted(string.format("0x%08X", expected_animation)),
		',"frame":', tostring(frame),
		',"capture_frames":', tostring(capture_frames),
		',"timeout_frames":', tostring(timeout_frames),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"input_mode":', quoted(input_mode),
		',"inputs":', inputs_json(),
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"renderer_hit_count":', tostring(renderer_hit_count),
		',"submission_watch_hit_count":', tostring(submission_watch_hit_count),
		',"ack_hit_count":', tostring(ack_hit_count),
		',"phases":[', table.concat(phases, ','), ']',
		'}',
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, table.concat({
		'{"run_id":', quoted(run_id),
		',"status":', quoted(outcome),
		',"phase_count":', tostring(#phases),
		'}',
	}))
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)
write_file(output_dir .. "/startup-state.json", '{"stage":"state-loaded"}')

local renderer_breakpoint = emu:setBreakpoint(function()
	if complete then
		return
	end
	renderer_hit_count = renderer_hit_count + 1
	if phase_index ~= 0 then
		return
	end
	local slot, address, flags = matching_active_task()
	if slot == nil then
		return
	end
	capture_phase("renderer-post", RENDERER_POST, nil, slot, address, flags)
	phase_index = 1
end, RENDERER_POST)
write_file(output_dir .. "/startup-renderer-breakpoint.json",
	'{"stage":"renderer-breakpoint","id":' .. tostring(renderer_breakpoint) .. '}')
assert(renderer_breakpoint and renderer_breakpoint > 0, "failed to install renderer-post breakpoint")
breakpoint_ids[#breakpoint_ids + 1] = renderer_breakpoint

local function install_ack_breakpoint()
	local ack_breakpoint = emu:setBreakpoint(function()
		if complete then
			return
		end
		ack_hit_count = ack_hit_count + 1
		if phase_index ~= 2 or emu:read8(SUBMISSION_PENDING) ~= 0 then
			return
		end
		local slot, task_address, flags = matching_active_task()
		if slot == nil then
			return
		end
		capture_phase("ack-post", ACK_POST, nil, slot, task_address, flags)
		phase_index = 3
		finish("three-phase-captured")
	end, ACK_POST)
	assert(ack_breakpoint and ack_breakpoint > 0, "failed to install ack-post breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = ack_breakpoint
end

local function install_submit_breakpoint()
	if submit_breakpoint ~= nil then
		return
	end
	submit_breakpoint = emu:setBreakpoint(function()
		if complete or phase_index ~= 1 or emu:read8(SUBMISSION_PENDING) ~= 1 then
			return
		end
		local slot, task_address, flags = matching_active_task()
		if slot == nil then
			return
		end
		capture_phase("submit-post", SUBMIT_POST, nil, slot, task_address, flags)
		phase_index = 2
		install_ack_breakpoint()
	end, SUBMIT_POST)
	assert(submit_breakpoint and submit_breakpoint > 0,
		"failed to install submit-post breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = submit_breakpoint
end

local submission_watchpoint = emu:setRangeWatchpoint(
	function(info)
		if complete then
			return
		end
		submission_watch_hit_count = submission_watch_hit_count + 1
		if phase_index ~= 1
			or (info.address or 0) ~= SUBMISSION_PENDING
			or (info.newValue or -1) ~= 1 then
			return
		end
		install_submit_breakpoint()
	end,
	SUBMISSION_PENDING,
	SUBMISSION_PENDING + 1,
	C.WATCHPOINT_TYPE.WRITE_CHANGE
)
write_file(output_dir .. "/startup-submission-watchpoint.json",
	'{"stage":"submission-watchpoint","id":' .. tostring(submission_watchpoint) .. '}')
assert(submission_watchpoint and submission_watchpoint > 0,
	"failed to install submission range watchpoint")
breakpoint_ids[#breakpoint_ids + 1] = submission_watchpoint
write_file(output_dir .. "/startup-breakpoints.json", '{"stage":"breakpoints-installed"}')
callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	local active_keys = 0
	for _, event in ipairs(events) do
		if frame >= event.down_frame and frame < event.up_frame then
			active_keys = active_keys | (1 << event.key)
		end
	end
	emu:setKeys(active_keys)
	if frame >= timeout_frames then
		finish("capture-incomplete")
	end
end)
