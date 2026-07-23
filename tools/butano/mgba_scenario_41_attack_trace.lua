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

local input_state = required_env("MGBA_S41_INPUT_STATE")
local output_dir = required_env("MGBA_S41_OUTPUT_DIR")
local done_marker_path = required_env("MGBA_S41_DONE_MARKER")
local audio_log_path = output_dir .. "/audio-hits.jsonl"
assert(emu:loadStateFile(input_state), "failed to load input state")

local frame = 0
local audio_hits = 0
local complete = false
local audio_breakpoint = nil
local state_frames = {
	[6] = true, [7] = true, [8] = true, [9] = true,
	[56] = true, [57] = true, [58] = true, [59] = true,
	[60] = true, [61] = true, [62] = true, [63] = true,
	[64] = true, [65] = true, [66] = true, [67] = true,
	[68] = true, [69] = true,
}

local function on_audio()
	audio_hits = audio_hits + 1
	write_file(
		audio_log_path,
		string.format(
			'{"frame":%d,"cycle":"%s","sound_id":%d,"lr":"0x%08X"}\n',
			frame,
			tostring(emu:currentCycle()),
			emu:readRegister("r0"),
			emu:readRegister("lr")
		),
		"a"
	)
end

write_file(audio_log_path, "")

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame == 1 then
		audio_breakpoint = emu:setBreakpoint(on_audio, 0x08061E6C)
	end
	if frame == 5 then
		emu:addKey(C.GBA_KEY.A)
	elseif frame == 13 then
		emu:clearKey(C.GBA_KEY.A)
	end
	emu:screenshot(output_dir .. "/" .. string.format("frame-%04d.png", frame))
	if state_frames[frame] then
		assert(emu:saveStateFile(
			output_dir .. "/" .. string.format("state-%04d.ss9", frame)
		))
	end
	if frame == 360 then
		if audio_breakpoint then
			emu:clearBreakpoint(audio_breakpoint)
		end
		assert(emu:saveStateFile(output_dir .. "/final.ss9"))
		local audit = string.format(
			'{"capture_frame":360,"audio_hits":%d,"status":"capture-complete"}',
			audio_hits
		)
		write_file(output_dir .. "/audit.json", audit)
		write_file(done_marker_path, audit)
		complete = true
	end
end)
