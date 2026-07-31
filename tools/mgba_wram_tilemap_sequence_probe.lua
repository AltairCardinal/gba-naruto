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
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n") .. '"'
end

local function read_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function read_u16(address)
	return emu:read8(address) | (emu:read8(address + 1) << 8)
end

local function read_u32(address)
	return read_u16(address) | (read_u16(address + 2) << 16)
end

local input_state = required_env("MGBA_WRAM_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_WRAM_INPUT_STATE_SHA256")
local rom_sha256 = required_env("MGBA_WRAM_ROM_SHA256")
local binary_sha256 = required_env("MGBA_WRAM_BINARY_SHA256")
local input_provenance = required_env("MGBA_WRAM_INPUT_PROVENANCE")
local output_dir = required_env("MGBA_WRAM_OUTPUT_DIR")
local done_marker = required_env("MGBA_WRAM_DONE_MARKER")
local run_id = required_env("MGBA_WRAM_RUN_ID")
local capture_frames = assert(tonumber(required_env("MGBA_WRAM_CAPTURE_FRAMES")))
local schedule_text = required_env("MGBA_WRAM_INPUT_SCHEDULE")
local memory_patch_text = os.getenv("MGBA_WRAM_MEMORY_PATCHES") or ""

assert(input_provenance == "natural" or input_provenance == "controlled",
	"input provenance must be natural or controlled")

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
	for record in value:gmatch("[^,]+") do
		local key_name, down_text, up_text = record:match("^([A-Za-z]+):(%d+):(%d+)$")
		assert(key_name, "invalid input schedule record")
		local key = assert(keys[key_name], "unsupported input key")
		local key_mask = 1 << key
		local down_frame = assert(tonumber(down_text))
		local up_frame = assert(tonumber(up_text))
		assert(down_frame > 0 and down_frame < up_frame, "invalid input interval")
		assert(down_frame >= previous_up, "input intervals overlap")
		assert(up_frame < capture_frames, "input interval exceeds capture frame")
		result[#result + 1] = {
			key_name = key_name,
			key_mask = key_mask,
			down_frame = down_frame,
			up_frame = up_frame,
		}
		previous_up = up_frame
	end
	assert(#result > 0, "input schedule must not be empty")
	return result
end

local function parse_memory_patches(value)
	local result = {}
	if value == "" then
		return result
	end
	local seen = {}
	for record in value:gmatch("[^,]+") do
		local address_text, after_text = record:match("^(0x[%x]+):([%x][%x])$")
		assert(address_text, "invalid controlled memory patch record")
		local address = assert(tonumber(address_text))
		local after = assert(tonumber(after_text, 16))
		assert(address >= 0x02000000 and address < 0x02040000,
			"controlled patch address must be in EWRAM")
		assert(not seen[address], "duplicate controlled memory patch address")
		seen[address] = true
		result[#result + 1] = {
			address = address,
			after = after,
		}
	end
	return result
end

assert(capture_frames > 1 and capture_frames == math.floor(capture_frames), "invalid capture frame")
local inputs = parse_schedule(schedule_text)
local memory_patches = parse_memory_patches(memory_patch_text)
local evidence_mode = input_provenance
if #memory_patches > 0 then
	evidence_mode = "controlled"
end

local QUEUE_BASE = 0x03005BBC
local QUEUE_SIZE = 0x100
local QUEUE_SLOT_SIZE = 16
local VRAM_BASE = 0x06000000
local VRAM_SIZE = 0x18000
local STAGING_SOURCE = 0x0200A640
local TRANSFORMED_SOURCE = 0x0200A760
local TRANSFORMED_DESTINATION = 0x06000806
local TRANSFORMED_ROW_STRIDE_BYTES = 64

local transform_specs = {
	{
		name = "source_084634B8",
		source_pointer = 0x084634B8,
		load_target = "choice_phase_a_load",
		load_post_target = "choice_phase_a_load_post",
		submit_target = "choice_phase_a_submit",
		source_stride_halfwords = 12,
		row_count = 12,
	},
	{
		name = "source_0846356C",
		source_pointer = 0x0846356C,
		load_target = "choice_phase_b_initial_load",
		load_post_target = "choice_phase_b_initial_load_post",
		submit_target = "choice_phase_b_submit",
		source_stride_halfwords = 12,
		row_count = 12,
	},
	{
		name = "source_084635D8",
		source_pointer = 0x084635D8,
		load_target = "choice_phase_b_second_load",
		load_post_target = "choice_phase_b_second_load_post",
		submit_target = "choice_phase_b_submit",
		source_stride_halfwords = 12,
		row_count = 12,
	},
}

local specs_by_name = {}
local source_results = {}
for _, spec in ipairs(transform_specs) do
	specs_by_name[spec.name] = spec
	source_results[spec.name] = {
		load_hits = 0,
		load_post_hits = 0,
		submit_hits = 0,
		queue_pre_hits = 0,
		queue_post_hits = 0,
		load_contract = false,
		submit_contract = false,
		vram_matches_output = false,
		closed = false,
	}
end

local targets = {
	{ name = "title_controller_call", address = 0x0808F814 },
	{ name = "title_controller_result", address = 0x0808F81C },
	{ name = "title_choice_branch", address = 0x0808F83C },
	{ name = "prebattle_outer_entry", address = 0x0808F73C },
	{ name = "prebattle_menu_call", address = 0x0808F894 },
	{ name = "prebattle_menu_result", address = 0x0808F89C },
	{ name = "prebattle_mode_check", address = 0x0808F8A0 },
	{ name = "completion_choice_state", address = 0x0808F916 },
	{ name = "prebattle_choice_state", address = 0x0808F9E2 },
	{ name = "prebattle_choice_reset", address = 0x0808F9EC },
	{ name = "completion_choice_flag_write", address = 0x0808F9F8 },
	{ name = "choice_screen_entry", address = 0x080914D8 },
	{ name = "choice_action_dispatch", address = 0x0809182E },
	{ name = "choice_state_3", address = 0x08091AB0 },
	{ name = "choice_state_4", address = 0x08091B70 },
	{ name = "choice_state_5", address = 0x08091BBC },
	{ name = "choice_animation_spawn_call", address = 0x08091BF6 },
	{ name = "choice_animation_task_factory", address = 0x08091000 },
	{ name = "choice_phase_a_load", address = 0x08090B5C,
		stage = "load", source_name = "source_084634B8" },
	{ name = "choice_phase_a_load_post", address = 0x08090B60,
		stage = "load_post", source_name = "source_084634B8" },
	{ name = "choice_phase_a_submit", address = 0x08090CB0, stage = "submit" },
	{ name = "choice_phase_b_initial_load", address = 0x08090D56,
		stage = "load", source_name = "source_0846356C" },
	{ name = "choice_phase_b_initial_load_post", address = 0x08090D62,
		stage = "load_post", source_name = "source_0846356C" },
	{ name = "choice_phase_b_second_load", address = 0x08090DC4,
		stage = "load", source_name = "source_084635D8" },
	{ name = "choice_phase_b_second_load_post", address = 0x08090DD0,
		stage = "load_post", source_name = "source_084635D8" },
	{ name = "choice_phase_b_submit", address = 0x08090F3C, stage = "submit" },
	{ name = "queue_consumer", address = 0x0806365C },
	{ name = "queue_consumer_post", address = 0x080636CE },
}

local frame = 0
local complete = false
local total_hits = 0
local events = {}
local hit_counts = {}
local breakpoint_ids = {}
local correlated_queue_hits = {}
local pending_by_name = {}
local active_spec = nil

local function register_hex(name)
	return string.format("0x%08X", emu:readRegister(name) or 0)
end

local function inputs_json()
	local rows = {}
	for _, input in ipairs(inputs) do
		rows[#rows + 1] = table.concat({
			'{"key":', quoted(input.key_name),
			',"down_frame":', tostring(input.down_frame),
			',"up_frame":', tostring(input.up_frame),
			',"hold_frames":', tostring(input.up_frame - input.down_frame),
			'}',
		})
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function memory_patches_json()
	local rows = {}
	for _, patch in ipairs(memory_patches) do
		rows[#rows + 1] = table.concat({
			'{"address":', quoted(string.format("0x%08X", patch.address)),
			',"before":', tostring(patch.before),
			',"after":', tostring(patch.after),
			'}',
		})
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function counts_json()
	local rows = {}
	for _, target in ipairs(targets) do
		rows[#rows + 1] = quoted(target.name) .. ":" .. tostring(hit_counts[target.name] or 0)
	end
	return "{" .. table.concat(rows, ",") .. "}"
end

local function event_json(target, cycle)
	return table.concat({
		'{"target":', quoted(target.name),
		',"address":', quoted(string.format("0x%08X", target.address)),
		',"frame":', tostring(frame),
		',"cycle":', quoted(cycle or emu:currentCycle()),
		',"pc":', quoted(register_hex("pc")),
		',"lr":', quoted(register_hex("lr")),
		',"r0":', quoted(register_hex("r0")),
		',"r1":', quoted(register_hex("r1")),
		',"r2":', quoted(register_hex("r2")),
		',"r3":', quoted(register_hex("r3")),
		',"r4":', quoted(register_hex("r4")),
		',"r5":', quoted(register_hex("r5")),
		',"r6":', quoted(register_hex("r6")),
		',"r7":', quoted(register_hex("r7")),
		',"r8":', quoted(register_hex("r8")),
		'}',
	})
end

local function read_strided_rows(address, source_stride_halfwords, row_count)
	local rows = {}
	local row_size = source_stride_halfwords * 2
	for row = 0, row_count - 1 do
		rows[#rows + 1] = read_range(address + row * TRANSFORMED_ROW_STRIDE_BYTES, row_size)
	end
	return table.concat(rows)
end

local function bool_json(value)
	return value and "true" or "false"
end

local function missing_stages(result)
	local missing = {}
	if result.load_hits == 0 or not result.load_contract then
		missing[#missing + 1] = "load"
	end
	if result.load_post_hits == 0 then
		missing[#missing + 1] = "load_post"
	end
	if result.submit_hits == 0 or not result.submit_contract then
		missing[#missing + 1] = "submit"
	end
	if result.queue_pre_hits == 0 then
		missing[#missing + 1] = "queue_pre"
	end
	if result.queue_post_hits == 0 or not result.vram_matches_output then
		missing[#missing + 1] = "queue_post_vram"
	end
	return missing
end

local function quoted_array(values)
	local rows = {}
	for _, value in ipairs(values) do
		rows[#rows + 1] = quoted(value)
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function source_results_json()
	local rows = {}
	for _, spec in ipairs(transform_specs) do
		local result = source_results[spec.name]
		rows[#rows + 1] = table.concat({
			'{"name":', quoted(spec.name),
			',"source_pointer":', quoted(string.format("0x%08X", spec.source_pointer)),
			',"load_target":', quoted(spec.load_target),
			',"submit_target":', quoted(spec.submit_target),
			',"source_stride_halfwords":', tostring(spec.source_stride_halfwords),
			',"row_count":', tostring(spec.row_count),
			',"load_hits":', tostring(result.load_hits),
			',"load_post_hits":', tostring(result.load_post_hits),
			',"submit_hits":', tostring(result.submit_hits),
			',"queue_pre_hits":', tostring(result.queue_pre_hits),
			',"queue_post_hits":', tostring(result.queue_post_hits),
			',"load_contract":', bool_json(result.load_contract),
			',"submit_contract":', bool_json(result.submit_contract),
			',"vram_matches_output":', bool_json(result.vram_matches_output),
			',"closed":', bool_json(result.closed),
			',"slot_index":', result.slot_index and tostring(result.slot_index) or "null",
			',"pre_status":', result.pre_status and tostring(result.pre_status) or "null",
			',"post_status":', result.post_status and tostring(result.post_status) or "null",
			',"missing_stages":', quoted_array(missing_stages(result)),
			'}',
		})
	end
	return "[" .. table.concat(rows, ",") .. "]"
end

local function handle_load(target)
	local spec = assert(specs_by_name[target.source_name])
	local result = source_results[spec.name]
	result.load_hits = result.load_hits + 1
	result.load_frame = frame
	result.load_cycle = emu:currentCycle()
	result.load_contract =
		emu:readRegister("r0") == spec.source_pointer and
		emu:readRegister("r1") == STAGING_SOURCE
	active_spec = spec
end

local function handle_load_post(target)
	local spec = assert(specs_by_name[target.source_name])
	if not active_spec or active_spec.name ~= spec.name or
		active_spec.load_post_target ~= target.name then
		return
	end
	local result = source_results[spec.name]
	if result.load_post_hits > 0 then
		return
	end
	result.load_post_hits = result.load_post_hits + 1
	result.load_post_cycle = emu:currentCycle()
	write_file(
		output_dir .. "/" .. spec.name .. "-load-staging.bin",
		read_range(STAGING_SOURCE, 12 * 12 * 2),
		"wb"
	)
end

local function handle_submit(target)
	if not active_spec or active_spec.submit_target ~= target.name then
		return
	end
	local spec = active_spec
	local result = source_results[spec.name]
	result.submit_hits = result.submit_hits + 1
	result.submit_frame = frame
	result.submit_cycle = emu:currentCycle()
	result.submit_contract =
		emu:readRegister("r0") == TRANSFORMED_SOURCE and
		emu:readRegister("r1") == TRANSFORMED_DESTINATION and
		emu:readRegister("r2") == spec.source_stride_halfwords and
		emu:readRegister("r3") == spec.row_count
	if result.submit_contract and not result.closed and not pending_by_name[spec.name] then
		pending_by_name[spec.name] = {
			spec = spec,
			load_cycle = result.load_cycle,
			load_post_cycle = result.load_post_cycle,
			output_rows = read_range(
				TRANSFORMED_SOURCE,
				spec.source_stride_halfwords * spec.row_count * 2
			),
			pre_vram_rows = read_strided_rows(
				TRANSFORMED_DESTINATION,
				spec.source_stride_halfwords,
				spec.row_count
			),
			submit_frame = frame,
			submit_cycle = result.submit_cycle,
		}
	end
end

local function capture_queue_pre(target)
	for name, pending in pairs(pending_by_name) do
		if pending.slot_index == nil then
			local spec = pending.spec
			for slot_index = 0, 15 do
				local slot = QUEUE_BASE + slot_index * QUEUE_SLOT_SIZE
				if read_u32(slot) == 3 and
					read_u32(slot + 4) == TRANSFORMED_SOURCE and
					read_u32(slot + 8) == TRANSFORMED_DESTINATION and
					read_u16(slot + 12) == spec.source_stride_halfwords and
					read_u16(slot + 14) == spec.row_count then
					local result = source_results[name]
					local prefix = output_dir .. "/" .. name .. "-queue-pre"
					pending.slot_index = slot_index
					pending.pre_status = 3
					pending.queue_pre_frame = frame
					pending.queue_pre_cycle = emu:currentCycle()
					pending.queue_pre_event = event_json(target, pending.queue_pre_cycle)
					events[#events + 1] = pending.queue_pre_event
					result.queue_pre_hits = result.queue_pre_hits + 1
					result.slot_index = slot_index
					result.pre_status = 3
					write_file(prefix .. ".bin", read_range(QUEUE_BASE, QUEUE_SIZE), "wb")
					write_file(prefix .. "-vram.bin", read_range(VRAM_BASE, VRAM_SIZE), "wb")
					write_file(prefix .. "-vram-rows.bin", pending.pre_vram_rows, "wb")
					write_file(prefix .. "-output-rows.bin", pending.output_rows, "wb")
					assert(emu:saveStateFile(prefix .. ".ss9"))
					emu:screenshot(prefix .. ".png")
					break
				end
			end
		end
	end
end

local function capture_queue_post(target)
	for name, pending in pairs(pending_by_name) do
		if pending.slot_index ~= nil then
			local slot = QUEUE_BASE + pending.slot_index * QUEUE_SLOT_SIZE
			local status = read_u32(slot)
			if status == 2 then
				local spec = pending.spec
				local post_rows = read_strided_rows(
					TRANSFORMED_DESTINATION,
					spec.source_stride_halfwords,
					spec.row_count
				)
				local result = source_results[name]
				local prefix = output_dir .. "/" .. name .. "-queue-post"
				local queue_post_cycle = emu:currentCycle()
				pending.queue_post_event = event_json(target, queue_post_cycle)
				events[#events + 1] = pending.queue_post_event
				result.queue_post_hits = result.queue_post_hits + 1
				result.post_status = status
				result.vram_matches_output = post_rows == pending.output_rows
				result.closed = result.load_contract and result.load_post_hits > 0 and
					result.submit_contract and
					result.queue_pre_hits > 0 and result.vram_matches_output
				write_file(prefix .. ".bin", read_range(QUEUE_BASE, QUEUE_SIZE), "wb")
				write_file(prefix .. "-vram.bin", read_range(VRAM_BASE, VRAM_SIZE), "wb")
				write_file(prefix .. "-vram-rows.bin", post_rows, "wb")
				assert(emu:saveStateFile(prefix .. ".ss9"))
				emu:screenshot(prefix .. ".png")
				correlated_queue_hits[#correlated_queue_hits + 1] = table.concat({
					'{"source_pointer":', quoted(string.format("0x%08X", spec.source_pointer)),
					',"submit_frame":', tostring(pending.submit_frame),
					',"load_cycle":', quoted(pending.load_cycle),
					',"load_post_cycle":', quoted(pending.load_post_cycle),
					',"submit_cycle":', quoted(pending.submit_cycle),
					',"queue_pre_frame":', tostring(pending.queue_pre_frame),
					',"queue_pre_cycle":', quoted(pending.queue_pre_cycle),
					',"queue_post_frame":', tostring(frame),
					',"queue_post_cycle":', quoted(queue_post_cycle),
					',"queue_pre_event":', pending.queue_pre_event,
					',"queue_post_event":', pending.queue_post_event,
					',"slot_index":', tostring(pending.slot_index),
					',"pre_status":3',
					',"post_status":', tostring(status),
					',"vram_matches_output":', bool_json(result.vram_matches_output),
					'}',
				})
				pending_by_name[name] = nil
			end
		end
	end
end

local function finish()
	if complete then
		return
	end
	complete = true
	emu:setKeys(0)
	for _, breakpoint_id in ipairs(breakpoint_ids) do
		emu:clearBreakpoint(breakpoint_id)
	end
	assert(emu:saveStateFile(output_dir .. "/final.ss9"))
	emu:screenshot(output_dir .. "/final.png")
	write_file(output_dir .. "/final-queue.bin", read_range(QUEUE_BASE, QUEUE_SIZE), "wb")
	write_file(output_dir .. "/final-vram.bin", read_range(VRAM_BASE, VRAM_SIZE), "wb")
	local closed_source_count = 0
	for _, spec in ipairs(transform_specs) do
		if source_results[spec.name].closed then
			closed_source_count = closed_source_count + 1
		end
	end
	local outcome = "incomplete"
	if closed_source_count == #transform_specs then
		if evidence_mode == "natural" then
			outcome = "natural-sources-closed"
		else
			outcome = "controlled-sources-closed"
		end
	end
	local payload = table.concat({
		'{"schema":"mgba-wram-tilemap-sequence-probe-v2"',
		',"run_id":', quoted(run_id),
		',"outcome":', quoted(outcome),
		',"input_provenance":', quoted(input_provenance),
		',"evidence_mode":', quoted(evidence_mode),
		',"frame":', tostring(frame),
		',"capture_frames":', tostring(capture_frames),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"binary_sha256":', quoted(binary_sha256),
		',"inputs":', inputs_json(),
		',"memory_patches":', memory_patches_json(),
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"total_hits":', tostring(total_hits),
		',"hit_counts":', counts_json(),
		',"closed_source_count":', tostring(closed_source_count),
		',"source_results":', source_results_json(),
		',"correlated_queue_hits":[', table.concat(correlated_queue_hits, ","), ']',
		',"events":[', table.concat(events, ","), ']',
		'}',
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)
for _, patch in ipairs(memory_patches) do
	patch.before = emu:read8(patch.address)
	emu:write8(patch.address, patch.after)
	assert(emu:read8(patch.address) == patch.after, "controlled memory patch did not persist")
end
for _, target in ipairs(targets) do
	hit_counts[target.name] = 0
	local breakpoint_id = emu:setBreakpoint(function()
		total_hits = total_hits + 1
		hit_counts[target.name] = hit_counts[target.name] + 1
		if hit_counts[target.name] == 1 then
			write_file(output_dir .. "/" .. target.name .. "-queue.bin", read_range(QUEUE_BASE, QUEUE_SIZE), "wb")
			write_file(output_dir .. "/" .. target.name .. "-vram.bin", read_range(VRAM_BASE, VRAM_SIZE), "wb")
			assert(emu:saveStateFile(output_dir .. "/" .. target.name .. "-hit.ss9"))
			emu:screenshot(output_dir .. "/" .. target.name .. "-hit.png")
		end
		if hit_counts[target.name] <= 32 then
			events[#events + 1] = event_json(target)
		end
		if target.stage == "load" then
			handle_load(target)
		elseif target.stage == "load_post" then
			handle_load_post(target)
		elseif target.stage == "submit" then
			handle_submit(target)
		elseif target.name == "queue_consumer" then
			capture_queue_pre(target)
		elseif target.name == "queue_consumer_post" then
			capture_queue_post(target)
		end
	end, target.address)
	assert(breakpoint_id and breakpoint_id > 0, "failed to install breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = breakpoint_id
end

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	local active_keys = 0
	for _, input in ipairs(inputs) do
		if frame >= input.down_frame and frame < input.up_frame then
			active_keys = active_keys | input.key_mask
		end
	end
	emu:setKeys(active_keys)
	if frame >= capture_frames then
		finish()
	end
end)
