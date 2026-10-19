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

local function env_number_or(name, fallback)
	local value = os.getenv(name)
	if not value or value == "" then
		return fallback
	end
	return assert(tonumber(value), "invalid number in " .. name)
end

local output_dir = required_env("MGBA_MAXMOD_ALLOCATION_OUTPUT_DIR")
local done_marker = required_env("MGBA_MAXMOD_ALLOCATION_DONE_MARKER")
local trace_path = output_dir .. "/maxmod-allocation-trace.jsonl"
local capture_frame = env_number_or(
	"MGBA_MAXMOD_ALLOCATION_CAPTURE_FRAME",
	100
)

local MAXMOD_MODULE_CHANNEL_COUNT_ADDRESS = 0x030029B0
local MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS = 0x030029AC
local MAXMOD_MODULE_CHANNELS_POINTER_ADDRESS = 0x030029B4
local MAXMOD_ACTIVE_CHANNELS_POINTER_ADDRESS = 0x030029B8
local MAXMOD_CHANNEL_MASK_ADDRESS = 0x03002870
local MAXMOD_CURRENT_LAYER_CHANNEL_COUNT_ADDRESS = 0x03002879
local MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS = env_number_or(
	"MGBA_MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS",
	0x030022E0
)
local maxmod_frame_address = env_number_or(
	"MGBA_MAXMOD_FRAME_ADDRESS",
	0x08042610
)
local MAXMOD_MODULE_CHANNEL_SIZE = 40
local MAXMOD_ACTIVE_CHANNEL_SIZE = 28
local MAXMOD_ACTIVE_CHANNEL_TYPE_OFFSET = 17

local frame = 0
local complete = false
local breakpoint_ids = {}
local hit_counts = {}
local watchpoint_id = nil
local veneer_write_hits = 0

local targets = {
	{ name = "mm-frame", address = maxmod_frame_address },
	{ name = "new-note", address = 0x03000B04 },
	{ name = "alloc-entry", address = 0x030004AC },
	{ name = "alloc-result", address = 0x03000B78 },
}

local function register(name)
	return emu:readRegister(name)
end

local function channel_state()
	local module_count =
		emu:read32(MAXMOD_MODULE_CHANNEL_COUNT_ADDRESS)
	local active_count =
		emu:read32(MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS)
	local module_channels =
		emu:read32(MAXMOD_MODULE_CHANNELS_POINTER_ADDRESS)
	local active_channels =
		emu:read32(MAXMOD_ACTIVE_CHANNELS_POINTER_ADDRESS)
	local disabled = 0
	local reserved = 0
	local background = 0
	local foreground = 0
	local custom = 0
	local active_zero_type = -1
	local active_zero_sample = 0
	local active_zero_flags = 0

	if active_channels >= 0x02000000 and
			active_channels < 0x03000000 then
		active_zero_type = emu:read8(
			active_channels + MAXMOD_ACTIVE_CHANNEL_TYPE_OFFSET
		)
		active_zero_sample = emu:read32(active_channels + 20)
		active_zero_flags = emu:read8(active_channels + 23)
		for index = 0, active_count - 1 do
			local channel_type = emu:read8(
				active_channels +
					index * MAXMOD_ACTIVE_CHANNEL_SIZE +
					MAXMOD_ACTIVE_CHANNEL_TYPE_OFFSET
			)
			if channel_type == 0 then
				disabled = disabled + 1
			elseif channel_type == 1 then
				reserved = reserved + 1
			elseif channel_type == 2 then
				background = background + 1
			elseif channel_type == 3 then
				foreground = foreground + 1
			elseif channel_type == 4 then
				custom = custom + 1
			end
		end
	end

	local module_zero_alloc = -1
	local module_zero_flags = 0
	local module_zero_instrument = 0
	local module_zero_note = 0
	if module_channels >= 0x02000000 and
			module_channels < 0x03000000 then
		module_zero_alloc = emu:read8(module_channels)
		module_zero_flags = emu:read8(module_channels + 1)
		module_zero_note = emu:read8(module_channels + 8)
		module_zero_instrument = emu:read8(module_channels + 9)
	end

	return {
		module_count = module_count,
		module_channels = module_channels,
		active_channels = active_channels,
		module_zero_alloc = module_zero_alloc,
		module_zero_flags = module_zero_flags,
		module_zero_note = module_zero_note,
		module_zero_instrument = module_zero_instrument,
		active_zero_type = active_zero_type,
		active_zero_sample = active_zero_sample,
		active_zero_flags = active_zero_flags,
		disabled = disabled,
		reserved = reserved,
		background = background,
		foreground = foreground,
		custom = custom,
	}
end

local function on_target(target, info)
	hit_counts[target.name] = (hit_counts[target.name] or 0) + 1
	local state = channel_state()
	write_file(
		trace_path,
		string.format(
			'{"event":"%s","frame":%d,"cycle":"%s",'
				.. '"address":"0x%08X","break_address":"0x%08X",'
				.. '"hit":%d,"pc":"0x%08X","lr":"0x%08X",'
				.. '"sp":"0x%08X","r0":"0x%08X",'
				.. '"r1":"0x%08X","r2":"0x%08X",'
				.. '"r3":"0x%08X","r4":"0x%08X",'
				.. '"instruction":"0x%08X",'
				.. '"new_note_veneer_target":"0x%08X",'
				.. '"channel_mask":"0x%08X","layer_channels":%d,'
				.. '"module_count":%d,'
				.. '"module_channels":"0x%08X",'
				.. '"active_channels":"0x%08X",'
				.. '"module_zero_alloc":%d,'
				.. '"module_zero_flags":%d,'
				.. '"module_zero_note":%d,'
				.. '"module_zero_instrument":%d,'
				.. '"active_zero_type":%d,'
				.. '"active_zero_sample":"0x%08X",'
				.. '"active_zero_flags":%d,'
				.. '"disabled":%d,"reserved":%d,'
				.. '"background":%d,"foreground":%d,'
				.. '"custom":%d}\n',
			target.name,
			frame,
			tostring(emu:currentCycle()),
			target.address,
			(info and info.address) or target.address,
			hit_counts[target.name],
			register("pc"),
			register("lr"),
			register("sp"),
			register("r0"),
			register("r1"),
			register("r2"),
			register("r3"),
			register("r4"),
			emu:read32(target.address),
			emu:read32(MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS),
			emu:read32(MAXMOD_CHANNEL_MASK_ADDRESS),
			emu:read8(MAXMOD_CURRENT_LAYER_CHANNEL_COUNT_ADDRESS),
			state.module_count,
			state.module_channels,
			state.active_channels,
			state.module_zero_alloc,
			state.module_zero_flags,
			state.module_zero_note,
			state.module_zero_instrument,
			state.active_zero_type,
			state.active_zero_sample,
			state.active_zero_flags,
			state.disabled,
			state.reserved,
			state.background,
			state.foreground,
			state.custom
		),
		"a"
	)
end

local function on_veneer_write(info)
	veneer_write_hits = veneer_write_hits + 1
	write_file(
		trace_path,
		string.format(
			'{"event":"veneer-write","frame":%d,"cycle":"%s",'
				.. '"hit":%d,"pc":"0x%08X","lr":"0x%08X",'
				.. '"sp":"0x%08X","r0":"0x%08X",'
				.. '"r1":"0x%08X","r2":"0x%08X",'
				.. '"r3":"0x%08X","address":"0x%08X",'
				.. '"old_value":"0x%08X","new_value":"0x%08X",'
				.. '"width":%d,"new_note_veneer_target":"0x%08X"}\n',
			frame,
			tostring(emu:currentCycle()),
			veneer_write_hits,
			register("pc"),
			register("lr"),
			register("sp"),
			register("r0"),
			register("r1"),
			register("r2"),
			register("r3"),
			info.address or 0,
			info.oldValue or 0,
			info.newValue or 0,
			info.width or 0,
			emu:read32(MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS)
		),
		"a"
	)
end

local function install_breakpoints()
	write_file(trace_path, "")
	for _, target in ipairs(targets) do
		local captured = target
		local id = emu:setBreakpoint(
			function(info)
				on_target(captured, info)
			end,
			captured.address
		)
		table.insert(breakpoint_ids, id)
	end
	watchpoint_id = emu:setRangeWatchpoint(
		on_veneer_write,
		MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS,
		MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS + 4,
		C.WATCHPOINT_TYPE.WRITE_CHANGE
	)
end

install_breakpoints()

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame >= capture_frame then
		for _, id in ipairs(breakpoint_ids) do
			emu:clearBreakpoint(id)
		end
		if watchpoint_id then
			emu:clearBreakpoint(watchpoint_id)
		end
		local summary = string.format(
			'{"status":"capture-complete","frame":%d,'
				.. '"mm_frame_hits":%d,'
				.. '"new_note_hits":%d,"alloc_entry_hits":%d,'
				.. '"alloc_result_hits":%d,'
				.. '"veneer_write_hits":%d}',
			frame,
			hit_counts["mm-frame"] or 0,
			hit_counts["new-note"] or 0,
			hit_counts["alloc-entry"] or 0,
			hit_counts["alloc-result"] or 0,
			veneer_write_hits
		)
		write_file(output_dir .. "/audit.json", summary)
		write_file(done_marker, summary)
		complete = true
	end
end)

emu:reset()
