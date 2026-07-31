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

local input_state = required_env("MGBA_WRAM_INPUT_STATE")
local input_state_sha256 = required_env("MGBA_WRAM_INPUT_STATE_SHA256")
local rom_sha256 = required_env("MGBA_WRAM_ROM_SHA256")
local binary_sha256 = required_env("MGBA_WRAM_BINARY_SHA256")
local output_dir = required_env("MGBA_WRAM_OUTPUT_DIR")
local done_marker = required_env("MGBA_WRAM_DONE_MARKER")
local run_id = required_env("MGBA_WRAM_RUN_ID")
local capture_frames = assert(tonumber(required_env("MGBA_WRAM_CAPTURE_FRAMES")))
local key_name = required_env("MGBA_WRAM_INPUT_KEY")
local down_frame = assert(tonumber(required_env("MGBA_WRAM_INPUT_DOWN_FRAME")))
local up_frame = assert(tonumber(required_env("MGBA_WRAM_INPUT_UP_FRAME")))
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
local key = assert(keys[key_name], "unsupported input key")

assert(down_frame > 0 and down_frame == math.floor(down_frame), "invalid down frame")
assert(up_frame == math.floor(up_frame), "invalid up frame")
assert(capture_frames == math.floor(capture_frames), "invalid capture frame")
assert(down_frame < up_frame and up_frame < capture_frames, "invalid frame order")

local targets = {
	{ name = "text_bg_loop_link", address = 0x0808B640 },
	{ name = "text_bg_setup", address = 0x0808B2C8 },
	{ name = "selection_load", address = 0x0808AD3A },
	{ name = "scene_panel_setup", address = 0x0808BAB0 },
	{ name = "scene_panel_upper_load", address = 0x0808BBD8 },
	{ name = "scene_panel_lower_load", address = 0x0808BBFC },
	{ name = "scene_panel_crop_load", address = 0x0808BC2E },
	{ name = "scene_panel_result", address = 0x0808BECC },
	{ name = "choice_screen_entry", address = 0x080914D8 },
	{ name = "choice_action_dispatch", address = 0x0809182E },
	{ name = "choice_animation_spawn_call", address = 0x08091BF6 },
	{ name = "choice_animation_task_factory", address = 0x08091000 },
	{ name = "choice_phase_a_load", address = 0x08090B5C },
	{ name = "choice_phase_a_submit", address = 0x08090CB0 },
	{ name = "choice_phase_b_initial_load", address = 0x08090D56 },
	{ name = "choice_phase_b_second_load", address = 0x08090DC4 },
	{ name = "choice_phase_b_submit", address = 0x08090F3C },
	{ name = "queue_consumer", address = 0x0806365C },
}

local frame = 0
local complete = false
local total_hits = 0
local first_hit_saved = false
local events = {}
local hit_counts = {}
local breakpoint_ids = {}

local function register_hex(name)
	return string.format("0x%08X", emu:readRegister(name) or 0)
end

local function events_json()
	return "[" .. table.concat(events, ",") .. "]"
end

local function counts_json()
	local rows = {}
	for _, target in ipairs(targets) do
		rows[#rows + 1] = quoted(target.name) .. ":" .. tostring(hit_counts[target.name] or 0)
	end
	return "{" .. table.concat(rows, ",") .. "}"
end

local function input_json()
	return table.concat({
		'{"key":', quoted(key_name),
		',"down_frame":', tostring(down_frame),
		',"up_frame":', tostring(up_frame),
		',"hold_frames":', tostring(up_frame - down_frame),
		'}',
	})
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
	write_file(output_dir .. "/final-queue.bin", read_range(0x03005BBC, 0x100), "wb")
	write_file(output_dir .. "/final-vram.bin", read_range(0x06000000, 0x18000), "wb")
	local outcome = total_hits > 0 and "targets-observed" or "targets-not-observed"
	local payload = table.concat({
		'{"schema":"mgba-wram-tilemap-single-input-probe-v1"',
		',"run_id":', quoted(run_id),
		',"outcome":', quoted(outcome),
		',"frame":', tostring(frame),
		',"capture_frames":', tostring(capture_frames),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"binary_sha256":', quoted(binary_sha256),
		',"inputs":[', input_json(), ']',
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"total_hits":', tostring(total_hits),
		',"hit_counts":', counts_json(),
		',"events":', events_json(),
		'}',
	})
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
end

assert(emu:loadStateFile(input_state), "failed to load input state")
emu:setKeys(0)
for _, target in ipairs(targets) do
	hit_counts[target.name] = 0
	local breakpoint_id = emu:setBreakpoint(function()
		total_hits = total_hits + 1
		hit_counts[target.name] = hit_counts[target.name] + 1
		if hit_counts[target.name] == 1 then
			write_file(output_dir .. "/" .. target.name .. "-queue.bin", read_range(0x03005BBC, 0x100), "wb")
			write_file(output_dir .. "/" .. target.name .. "-vram.bin", read_range(0x06000000, 0x18000), "wb")
			assert(emu:saveStateFile(output_dir .. "/" .. target.name .. "-hit.ss9"))
			emu:screenshot(output_dir .. "/" .. target.name .. "-hit.png")
		end
		if hit_counts[target.name] <= 16 then
			events[#events + 1] = table.concat({
				'{"target":', quoted(target.name),
				',"address":', quoted(string.format("0x%08X", target.address)),
				',"frame":', tostring(frame),
				',"cycle":', quoted(emu:currentCycle()),
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
		if not first_hit_saved then
			first_hit_saved = true
			write_file(output_dir .. "/queue.bin", read_range(0x03005BBC, 0x100), "wb")
			write_file(output_dir .. "/vram.bin", read_range(0x06000000, 0x18000), "wb")
			assert(emu:saveStateFile(output_dir .. "/hit.ss9"))
			emu:screenshot(output_dir .. "/hit.png")
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
	if frame == down_frame then
		emu:addKey(key)
	elseif frame == up_frame then
		emu:clearKey(key)
	end
	if frame >= capture_frames then
		finish()
	end
end)
