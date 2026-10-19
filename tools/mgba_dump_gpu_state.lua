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

local input_state = required_env("MGBA_GPU_STATE_INPUT")
local input_state_sha256 = required_env("MGBA_GPU_STATE_INPUT_SHA256")
local output_dir = required_env("MGBA_GPU_STATE_OUTPUT_DIR")
local done_marker = required_env("MGBA_GPU_STATE_DONE_MARKER")
local finished = false

assert(emu:loadStateFile(input_state), "failed to load input state")

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

local function dump_gpu_domains()
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
			output_dir .. "/" .. name .. ".bin",
			bytes,
			"wb"
		)
	end
end

callbacks:add("frame", function()
	if finished then
		return
	end
	dump_gpu_domains()
	emu:screenshot(output_dir .. "/frame.png")
	local payload = string.format(
		'{"status":"capture-complete","cycle":"%s",'
			.. '"input_state_sha256":"%s"}',
		tostring(emu:currentCycle()),
		input_state_sha256
	)
	write_file(output_dir .. "/audit.json", payload)
	write_file(done_marker, payload)
	finished = true
end)
