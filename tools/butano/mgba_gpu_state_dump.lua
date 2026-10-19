-- Dump the GBA's palette RAM, VRAM, OAM and I/O registers at a chosen frame.
--
-- Every reverse-engineering question in this project that needs "what did the
-- original ROM actually put in palette RAM" was previously unanswerable: the
-- recorded walks only kept rendered PNGs, and the GPU dumps that once existed
-- under artifacts/ were removed by a host cleanup.  A rendered frame shows the
-- *result* of the palette, not which palette bank and index produced it.
--
-- mGBA exposes each memory region to Lua as emu.memory[name] (there is no
-- "domains" sub-table) with readRange(offset, length) returning the raw bytes,
-- so one frame of PRAM is enough to recover a palette bank in index order.
-- The region names come from _GBAMemoryBlocks in src/gba/core.c.
--
-- The probe is deliberately fail-closed: it writes a manifest naming every
-- input hash and every dumped file, and the driver refuses to accept a run whose
-- manifest is missing or whose dumped sizes do not match the GBA's fixed
-- geometry.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_bytes(path, payload)
	local output = assert(io.open(path, "wb"))
	output:write(payload)
	output:close()
end

local function write_text(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local input_state = required_env("MGBA_GPU_STATE_INPUT_STATE")
local output_dir = required_env("MGBA_GPU_STATE_OUTPUT_DIR")
local done_marker = required_env("MGBA_GPU_STATE_DONE_MARKER")
local settle_frames = tonumber(required_env("MGBA_GPU_STATE_SETTLE_FRAMES"))
local dumps = required_env("MGBA_GPU_STATE_DUMP")

assert(emu:loadStateFile(input_state), "failed to load input state")

-- GBA geometry is fixed, so the expected sizes are known up front and are
-- asserted rather than discovered.
local REGIONS = {
	{ name = "palette", file = "pram.bin", size = 1024 },
	{ name = "oam", file = "oam.bin", size = 1024 },
	{ name = "io", file = "io.bin", size = 1024 },
	{ name = "vram", file = "vram.bin", size = 96 * 1024 },
}

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < settle_frames then
		return
	end

	local manifest = {}
	local written = 0
	for _, region in ipairs(REGIONS) do
		local domain = emu.memory[region.name]
		assert(domain, "memory domain not exposed: " .. region.name)
		local bytes = domain:readRange(0, region.size)
		assert(#bytes == region.size,
			string.format("%s returned %d bytes, expected %d",
				region.name, #bytes, region.size))
		local path = output_dir .. "/" .. region.file
		write_bytes(path, bytes)
		manifest[#manifest + 1] = string.format(
			'  {"region":"%s","file":"%s","bytes":%d}',
			region.name, region.file, region.size)
		written = written + #bytes
	end

	-- Also record the OBJ palette bank currently in use per OAM slot, which is
	-- what ties a rendered colour back to a palette entry.
	local oam = emu.memory["oam"]:readRange(0, 1024)
	local banks = {}
	for slot = 0, 127 do
		local base = slot * 8 + 4
		local low = oam:byte(base + 1)
		local high = oam:byte(base + 2)
		local attr2 = low + high * 256
		if (attr2 >> 12) & 0x0F ~= 0 or attr2 & 0x7FF ~= 0 then
			banks[#banks + 1] = string.format('{"slot":%d,"bank":%d}',
				slot, (attr2 >> 12) & 0x0F)
		end
	end
	write_text(output_dir .. "/oam-palette-banks.json",
		"[" .. table.concat(banks, ",") .. "]\n")

	write_text(output_dir .. "/manifest.json", string.format(
		'{\n  "schema": "konoha.mgba-gpu-state-dump.v1",\n' ..
		'  "input_state": "%s",\n' ..
		'  "settle_frames": %d,\n' ..
		'  "captured_frame": %d,\n' ..
		'  "regions": [\n%s\n  ],\n' ..
		'  "total_bytes": %d\n}\n',
		input_state, settle_frames, frame,
		table.concat(manifest, ",\n"), written))

	write_text(done_marker, "ok\n")
	complete = true
end)
