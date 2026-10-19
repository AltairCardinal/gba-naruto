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

local input_state = required_env("MGBA_ACTION_PRESENTATION_INPUT_STATE")
local output_dir = required_env("MGBA_ACTION_PRESENTATION_OUTPUT_DIR")
local done_marker = required_env("MGBA_ACTION_PRESENTATION_DONE_MARKER")
local trace_path = output_dir .. "/presentation-trace.jsonl"

assert(emu:loadStateFile(input_state), "failed to load input state")
write_file(trace_path, "")

local frame = 0
local finished = false
local breakpoint_ids = {}
local hit_counts = {}
local keys = {
	A = C.GBA_KEY.A,
	B = C.GBA_KEY.B,
	Down = C.GBA_KEY.DOWN,
	Left = C.GBA_KEY.LEFT,
	Right = C.GBA_KEY.RIGHT,
	Up = C.GBA_KEY.UP,
}

local targets = {
	{ name = "active_action_initializer", address = 0x0806D85C },
	{ name = "ninja_tool_initializer", address = 0x0806D910 },
	{ name = "action_event_builder", address = 0x080754A8 },
	{ name = "hit_presentation", address = 0x0807B8B8 },
	{ name = "bind_effect_sequence", address = 0x0807C5E8 },
	{ name = "effect_resource_builder", address = 0x0807FDCC },
	{ name = "effect_sequence_selector", address = 0x0807FE2C },
	{ name = "visual_object_create", address = 0x08080108 },
	{ name = "sound_wrapper", address = 0x08061E6C },
	{ name = "cpu_fast_set", address = 0x0809C0DC },
	{ name = "cpu_set", address = 0x0809C0E0 },
	{ name = "lz77_vram", address = 0x0809C0E8 },
	{ name = "lz77_wram", address = 0x0809C0EC },
}

local state_frames = {
	[6] = true,
	[8] = true,
	[20] = true,
	[40] = true,
	[60] = true,
	[80] = true,
	[100] = true,
	[140] = true,
	[146] = true,
	[148] = true,
	[150] = true,
	[154] = true,
	[158] = true,
	[180] = true,
	[220] = true,
	[260] = true,
	[300] = true,
	[360] = true,
	[480] = true,
	[720] = true,
	[960] = true,
	[1200] = true,
}
local gpu_capture_start = tonumber(
	os.getenv("MGBA_ACTION_PRESENTATION_GPU_CAPTURE_START") or "146"
)
local gpu_capture_end = tonumber(
	os.getenv("MGBA_ACTION_PRESENTATION_GPU_CAPTURE_END") or "180"
)
local capture_frames = tonumber(
	os.getenv("MGBA_ACTION_PRESENTATION_CAPTURE_FRAMES") or "360"
)
local confirm_frame = tonumber(
	os.getenv("MGBA_ACTION_PRESENTATION_CONFIRM_FRAME") or "5"
)
local confirm_hold_frames = tonumber(
	os.getenv("MGBA_ACTION_PRESENTATION_CONFIRM_HOLD_FRAMES") or "8"
)
assert(gpu_capture_start and gpu_capture_start >= 1,
	"invalid MGBA_ACTION_PRESENTATION_GPU_CAPTURE_START")
assert(capture_frames and capture_frames >= 1
		and capture_frames == math.floor(capture_frames),
	"invalid MGBA_ACTION_PRESENTATION_CAPTURE_FRAMES")
assert(gpu_capture_end and gpu_capture_end <= capture_frames,
	"invalid MGBA_ACTION_PRESENTATION_GPU_CAPTURE_END")
assert(gpu_capture_start <= gpu_capture_end,
	"GPU capture start must not exceed end")
assert(confirm_frame and confirm_frame >= 1
		and confirm_frame == math.floor(confirm_frame),
	"invalid MGBA_ACTION_PRESENTATION_CONFIRM_FRAME")
assert(confirm_hold_frames and confirm_hold_frames >= 1
		and confirm_hold_frames == math.floor(confirm_hold_frames),
	"invalid MGBA_ACTION_PRESENTATION_CONFIRM_HOLD_FRAMES")
assert(confirm_frame + confirm_hold_frames <= capture_frames,
	"confirmation input must finish before capture")

local function parse_key_sequence(sequence)
	local events = {}
	for encoded_event in string.gmatch(sequence, "[^;]+") do
		local start_text, key_name, hold_text =
			string.match(
				encoded_event,
				"^(%d+):([%a]+):(%d+)$"
			)
		assert(start_text and key_name and hold_text,
			"invalid input key event")
		local start_frame = tonumber(start_text)
		local hold_frames = tonumber(hold_text)
		assert(keys[key_name], "unknown input key " .. key_name)
		assert(start_frame and start_frame >= 1,
			"invalid input key start frame")
		assert(hold_frames and hold_frames >= 1,
			"invalid input key hold frames")
		assert(start_frame + hold_frames <= capture_frames,
			"input key event must finish before capture")
		table.insert(events, {
			start_frame = start_frame,
			release_frame = start_frame + hold_frames,
			key = keys[key_name],
		})
	end
	assert(#events > 0, "input key sequence must not be empty")
	table.sort(events, function(left, right)
		return left.start_frame < right.start_frame
	end)
	local previous_release = 0
	local scheduled_presses = {}
	local scheduled_releases = {}
	for _, event in ipairs(events) do
		assert(event.start_frame >= previous_release,
			"input key intervals overlap")
		assert(not scheduled_presses[event.start_frame],
			"input key press frames overlap")
		assert(not scheduled_releases[event.release_frame],
			"input key release frames overlap")
		scheduled_presses[event.start_frame] = event.key
		scheduled_releases[event.release_frame] = event.key
		previous_release = event.release_frame
	end
	return scheduled_presses, scheduled_releases
end

local key_sequence =
	os.getenv("MGBA_ACTION_PRESENTATION_KEY_SEQUENCE") or
	string.format(
		"%d:A:%d", confirm_frame, confirm_hold_frames
	)
local scheduled_presses, scheduled_releases =
	parse_key_sequence(key_sequence)

local function register(name)
	return emu:readRegister(name)
end

local gpu_domains = {
	{ "io", 0x400, 0x04000000 },
	{ "vram", 0x18000, 0x06000000 },
	{ "oam", 0x400, 0x07000000 },
	{ "pram", 0x400, 0x05000000 },
}

local function read_absolute_range(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.char(emu:read8(address + index))
	end
	return table.concat(bytes)
end

local function dump_gpu_domains(tag)
	for _, descriptor in ipairs(gpu_domains) do
		local name = descriptor[1]
		local size = descriptor[2]
		local address = descriptor[3]
		local domain = emu.memory[name]
		local bytes = nil
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
		write_file(
			output_dir .. "/" .. tag .. "-" .. name .. ".bin",
			bytes,
			"wb"
		)
	end
end

local function on_target(target)
	hit_counts[target.name] = (hit_counts[target.name] or 0) + 1
	local hit = hit_counts[target.name]
	write_file(
		trace_path,
		string.format(
			'{"frame":%d,"cycle":"%s","target":"%s",'
				.. '"address":"0x%08X","hit":%d,'
				.. '"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X",'
				.. '"r0":"0x%08X","r1":"0x%08X",'
				.. '"r2":"0x%08X","r3":"0x%08X"}\n',
			frame,
			tostring(emu:currentCycle()),
			target.name,
			target.address,
			hit,
			register("pc"),
			register("lr"),
			register("sp"),
			register("r0"),
			register("r1"),
			register("r2"),
			register("r3")
		),
		"a"
	)
	if hit == 1 then
		emu:screenshot(
			output_dir .. "/" .. target.name .. "-first-hit.png"
		)
		dump_gpu_domains(target.name .. "-first-hit")
	end
end

callbacks:add("frame", function()
	if finished then
		return
	end
	frame = frame + 1
	if frame == 1 then
		for _, target in ipairs(targets) do
			local captured = target
			local id = emu:setBreakpoint(
				function()
					on_target(captured)
				end,
				captured.address
			)
			table.insert(breakpoint_ids, id)
		end
	end
	if scheduled_releases[frame] then
		emu:clearKey(scheduled_releases[frame])
	end
	if scheduled_presses[frame] then
		emu:addKey(scheduled_presses[frame])
	end
	if state_frames[frame] then
		local state_tag = string.format("%04d", frame)
		assert(emu:saveStateFile(
			output_dir .. "/state-" .. state_tag .. ".ss9"
		))
		emu:screenshot(output_dir .. "/state-" .. state_tag .. ".png")
		dump_gpu_domains("state-" .. state_tag)
	end
	if frame >= gpu_capture_start and frame <= gpu_capture_end then
		local gpu_tag = string.format("%04d", frame)
		emu:screenshot(output_dir .. "/gpu-frame-" .. gpu_tag .. ".png")
		dump_gpu_domains("gpu-frame-" .. gpu_tag)
	end
	if frame == capture_frames then
		for _, id in ipairs(breakpoint_ids) do
			emu:clearBreakpoint(id)
		end
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		emu:screenshot(output_dir .. "/final.png")
		local summary = string.format(
			'{"status":"capture-complete","frame":%d,'
				.. '"initializer_hits":%d,"tool_initializer_hits":%d,"event_builder_hits":%d,'
				.. '"hit_presentation_hits":%d,"sequence_hits":%d}',
			capture_frames,
			hit_counts.active_action_initializer or 0,
			hit_counts.ninja_tool_initializer or 0,
			hit_counts.action_event_builder or 0,
			hit_counts.hit_presentation or 0,
			hit_counts.effect_sequence_selector or 0
		)
		write_file(output_dir .. "/audit.json", summary)
		write_file(done_marker, summary)
		finished = true
	end
end)
