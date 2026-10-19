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

local input_state = required_env("MGBA_TARGET_CONFIRMATION_INPUT_STATE")
local output_dir = required_env("MGBA_TARGET_CONFIRMATION_OUTPUT_DIR")
local done_marker = required_env("MGBA_TARGET_CONFIRMATION_DONE_MARKER")
local trace_path = output_dir .. "/target-confirmation-trace.jsonl"
local final_state = output_dir .. "/final.ss9"
local final_png = output_dir .. "/final.png"

assert(emu:loadStateFile(input_state), "failed to load input state")
write_file(trace_path, "")

local frame = 0
local finished = false
local breakpoint_ids = {}
local hit_counts = {}

local targets = {
	{ name = "area_builder_entry", address = 0x0806A4AC },
	{ name = "area_builder_result", address = 0x0807181A },
	{ name = "confirmation_result_test", address = 0x08071922 },
	{ name = "accepted_confirmation", address = 0x08071926 },
	{ name = "rejected_confirmation", address = 0x080719A0 },
	{ name = "confirmation_commit_path", address = 0x0807165E },
}

local function register(name)
	return emu:readRegister(name)
end

local function on_target(target)
	hit_counts[target.name] = (hit_counts[target.name] or 0) + 1
	write_file(
		trace_path,
		string.format(
			'{"frame":%d,"cycle":"%s","target":"%s",'
				.. '"address":"0x%08X","hit":%d,'
				.. '"cursor_x":%d,"cursor_y":%d,'
				.. '"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X",'
				.. '"r0":"0x%08X","r1":"0x%08X",'
				.. '"r2":"0x%08X","r3":"0x%08X",'
				.. '"r4":"0x%08X","r5":"0x%08X",'
				.. '"r6":"0x%08X","r7":"0x%08X"}\n',
			frame,
			tostring(emu:currentCycle()),
			target.name,
			target.address,
			hit_counts[target.name],
			emu:read8(0x02026A78),
			emu:read8(0x02026A79),
			register("pc"),
			register("lr"),
			register("sp"),
			register("r0"),
			register("r1"),
			register("r2"),
			register("r3"),
			register("r4"),
			register("r5"),
			register("r6"),
			register("r7")
		),
		"a"
	)
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
	elseif frame == 5 then
		emu:addKey(C.GBA_KEY.A)
	elseif frame == 6 then
		emu:clearKey(C.GBA_KEY.A)
	elseif frame == 90 then
		for _, id in ipairs(breakpoint_ids) do
			emu:clearBreakpoint(id)
		end
		assert(emu:saveStateFile(final_state))
		emu:screenshot(final_png)
		local summary = string.format(
			'{"status":"capture-complete","frame":90,'
				.. '"area_builder_hits":%d,"result_hits":%d,'
				.. '"accepted_hits":%d,"rejected_hits":%d,'
				.. '"commit_path_hits":%d}',
			hit_counts.area_builder_entry or 0,
			hit_counts.area_builder_result or 0,
			hit_counts.accepted_confirmation or 0,
			hit_counts.rejected_confirmation or 0,
			hit_counts.confirmation_commit_path or 0
		)
		write_file(output_dir .. "/audit.json", summary)
		write_file(done_marker, summary)
		finished = true
	end
end)
