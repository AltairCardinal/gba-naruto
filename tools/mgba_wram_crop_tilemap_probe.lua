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

local targets = {
	{ name = "crop_load", address = 0x0808BC2E },
	{ name = "crop_consumer", address = 0x0808B79C },
}
local frame = 0
local complete = false
local total_hits = 0
local events = {}
local hit_counts = {}
local breakpoint_ids = {}

local function register_hex(name)
	return string.format("0x%08X", emu:readRegister(name) or 0)
end

local function counts_json()
	local rows = {}
	for _, target in ipairs(targets) do
		rows[#rows + 1] = quoted(target.name) .. ":" .. tostring(hit_counts[target.name] or 0)
	end
	return "{" .. table.concat(rows, ",") .. "}"
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
	write_file(output_dir .. "/final-vram.bin", read_range(0x06000000, 0x18000), "wb")
	local payload = table.concat({
		'{"schema":"mgba-wram-crop-tilemap-probe-v1"',
		',"run_id":', quoted(run_id),
		',"outcome":', quoted(total_hits > 0 and "targets-observed" or "targets-not-observed"),
		',"frame":', tostring(frame),
		',"capture_frames":', tostring(capture_frames),
		',"input_state":', quoted(input_state),
		',"input_state_sha256":', quoted(input_state_sha256),
		',"rom_sha256":', quoted(rom_sha256),
		',"binary_sha256":', quoted(binary_sha256),
		',"inputs":[]',
		',"total_hits":', tostring(total_hits),
		',"hit_counts":', counts_json(),
		',"events":[', table.concat(events, ","), ']}',
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
			write_file(
				output_dir .. "/" .. target.name .. "-vram.bin",
				read_range(0x06000000, 0x18000),
				"wb"
			)
			if target.name == "crop_consumer" then
				write_file(
					output_dir .. "/crop_consumer-wram.bin",
					read_range(0x02002880, 0x320),
					"wb"
				)
			end
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
				'}',
			})
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
	if frame >= capture_frames then
		finish()
	end
end)
