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

local input_state = required_env("MGBA_EFFECT_PHASE_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_EFFECT_PHASE_INPUT_STATE_SHA256")
local output_dir = required_env("MGBA_EFFECT_PHASE_OUTPUT_DIR")
local done_marker = required_env("MGBA_EFFECT_PHASE_DONE_MARKER")
local run_id = required_env("MGBA_EFFECT_PHASE_RUN_ID")
local rom_sha256 = required_env("MGBA_EFFECT_PHASE_ROM_SHA256")
local expected_group_id = assert(tonumber(required_env("MGBA_EFFECT_PHASE_GROUP_ID")))
local expected_sequence_id = assert(tonumber(required_env("MGBA_EFFECT_SEQUENCE_ID")))
local expected_definition = assert(tonumber(required_env("MGBA_EFFECT_PHASE_DEFINITION_POINTER")))
local expected_animation = assert(tonumber(required_env("MGBA_EFFECT_PHASE_ANIMATION_POINTER")))
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
local SUBMISSION_PENDING = 0x0300067C
local VRAM_BASE = 0x06000000
local PRAM_BASE = 0x05000000
local IO_BASE = 0x04000000
local SCRATCH = 0x0203FF40

local BINDER_RETURN = 0x0809E85A
local RENDERER_POST = 0x08063328
local SUBMIT_POST = 0x08061126
local ACK_POST = 0x080612AA

local function read_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function matching_active_task()
	for slot = 0, TASK_SLOT_COUNT - 1 do
		local address = TASK_POOL_BASE + slot * TASK_RECORD_SIZE
		local flags = emu:read32(address)
		if flags & 1 ~= 0
			and emu:read32(address + 0x1C) == expected_definition
			and emu:read32(address + 0x20) == expected_animation then
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
local scratch_before = -1
local scratch_after = -1

local function nullable_number(value)
	return value == nil and "null" or tostring(value)
end

local function nullable_address(value)
	return value == nil and "null" or quoted(string.format("0x%08X", value))
end

local function capture_phase(name, address, require_target)
	local prefix = output_dir .. "/" .. name .. "/capture"
	local slot, task_address, flags = matching_active_task()
	if require_target then
		assert(slot ~= nil, "controlled spawn did not create the expected task")
	end
	write_file(prefix .. "-task-pool.bin", read_range(TASK_POOL_BASE, TASK_POOL_SIZE), "wb")
	write_file(prefix .. "-active-count.bin", read_range(ACTIVE_TASK_COUNT, 1), "wb")
	write_file(prefix .. "-active-pointers.bin", read_range(ACTIVE_TASK_POINTERS, 0x200), "wb")
	write_file(prefix .. "-runtime-offsets.bin", read_range(RUNTIME_OFFSETS, 0x20), "wb")
	write_file(prefix .. "-shadow-oam.bin", read_range(SHADOW_OAM, 0x400), "wb")
	write_file(prefix .. "-hardware-oam.bin", read_range(HARDWARE_OAM, 0x400), "wb")
	write_file(prefix .. "-submission.bin", read_range(SUBMISSION_PENDING, 2), "wb")
	write_file(prefix .. "-vram.bin", read_range(VRAM_BASE, 0x18000), "wb")
	write_file(prefix .. "-pram.bin", read_range(PRAM_BASE, 0x400), "wb")
	write_file(prefix .. "-io.bin", read_range(IO_BASE, 0x400), "wb")
	assert(emu:saveStateFile(prefix .. ".ss9"), "failed to save controlled phase state")
	emu:screenshot(prefix .. ".png")
	local payload = table.concat({
		'{"name":', quoted(name),
		',"address":', quoted(string.format("0x%08X", address)),
		',"frame":', tostring(frame),
		',"cycle":', quoted(tostring(emu:currentCycle())),
		',"target_present":', slot == nil and "false" or "true",
		',"task_slot":', nullable_number(slot),
		',"task_address":', nullable_address(task_address),
		',"task_flags":', nullable_address(flags),
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
	if complete then return end
	complete = true
	emu:setKeys(0)
	clear_breakpoints()
	if outcome ~= "binder-plus-three-phase-captured" then
		write_file(output_dir .. "/timeout-task-pool.bin", read_range(TASK_POOL_BASE, TASK_POOL_SIZE), "wb")
		assert(emu:saveStateFile(output_dir .. "/timeout.ss9"), "failed to save timeout state")
		emu:screenshot(output_dir .. "/timeout.png")
	end
	local payload = table.concat({
		'{"schema":"mgba-controlled-battle-effect-capture-v1"',
		',"run_id":', quoted(run_id),
		',"outcome":', quoted(outcome),
		',"group_id":', tostring(expected_group_id),
		',"sequence_id":', tostring(expected_sequence_id),
		',"definition_pointer":', quoted(string.format("0x%08X", expected_definition)),
		',"animation_pointer":', quoted(string.format("0x%08X", expected_animation)),
		',"frame":', tostring(frame),
		',"timeout_frames":', tostring(timeout_frames),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"inputs":[]',
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"scratch_before":', tostring(scratch_before),
		',"scratch_after":', tostring(scratch_after),
		',"renderer_hit_count":', tostring(renderer_hit_count),
		',"submission_watch_hit_count":', tostring(submission_watch_hit_count),
		',"ack_hit_count":', tostring(ack_hit_count),
		',"phases":[', table.concat(phases, ','), ']}'
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, table.concat({
		'{"run_id":', quoted(run_id),
		',"status":', quoted(outcome),
		',"phase_count":', tostring(#phases), '}'
	}))
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)
scratch_before = emu:read32(SCRATCH)
assert(scratch_before == 0, "controlled one-shot scratch is not zero")

local binder_breakpoint = emu:setBreakpoint(function()
	if complete or phase_index ~= 0 then return end
	scratch_after = emu:read32(SCRATCH)
	assert(scratch_after == 1, "controlled one-shot scratch was not latched")
	capture_phase("binder-return", BINDER_RETURN, false)
	phase_index = 1
end, BINDER_RETURN)
assert(binder_breakpoint and binder_breakpoint > 0, "failed to install binder-return breakpoint")
breakpoint_ids[#breakpoint_ids + 1] = binder_breakpoint

local renderer_breakpoint = emu:setBreakpoint(function()
	if complete or phase_index ~= 1 then return end
	renderer_hit_count = renderer_hit_count + 1
	capture_phase("renderer-post", RENDERER_POST, false)
	phase_index = 2
end, RENDERER_POST)
assert(renderer_breakpoint and renderer_breakpoint > 0, "failed to install renderer breakpoint")
breakpoint_ids[#breakpoint_ids + 1] = renderer_breakpoint

local function install_ack_breakpoint()
	local id = emu:setBreakpoint(function()
		if complete or phase_index ~= 3 or emu:read8(SUBMISSION_PENDING) ~= 0 then return end
		ack_hit_count = ack_hit_count + 1
		capture_phase("ack-post", ACK_POST, false)
		phase_index = 4
		finish("binder-plus-three-phase-captured")
	end, ACK_POST)
	assert(id and id > 0, "failed to install ack breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = id
end

local function install_submit_breakpoint()
	if submit_breakpoint ~= nil then return end
	submit_breakpoint = emu:setBreakpoint(function()
		if complete or phase_index ~= 2 or emu:read8(SUBMISSION_PENDING) ~= 1 then return end
		capture_phase("submit-post", SUBMIT_POST, false)
		phase_index = 3
		install_ack_breakpoint()
	end, SUBMIT_POST)
	assert(submit_breakpoint and submit_breakpoint > 0, "failed to install submit breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = submit_breakpoint
end

local watchpoint = emu:setRangeWatchpoint(function(info)
	if complete then return end
	submission_watch_hit_count = submission_watch_hit_count + 1
	if phase_index == 2 and (info.address or 0) == SUBMISSION_PENDING
		and (info.newValue or -1) == 1 then
		install_submit_breakpoint()
	end
end, SUBMISSION_PENDING, SUBMISSION_PENDING + 1, C.WATCHPOINT_TYPE.WRITE_CHANGE)
assert(watchpoint and watchpoint > 0, "failed to install submission watchpoint")
breakpoint_ids[#breakpoint_ids + 1] = watchpoint

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	emu:setKeys(0)
	if frame >= timeout_frames then finish("capture-incomplete") end
end)
