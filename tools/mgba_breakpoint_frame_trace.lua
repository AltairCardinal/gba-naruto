local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local target_text = required_env("MGBA_BREAKPOINT_TRACE_TARGET")
assert(
	target_text:match("^0x%x%x%x%x%x%x%x%x$"),
	"MGBA_BREAKPOINT_TRACE_TARGET must be 0x followed by 8 hex digits"
)
local target = assert(tonumber(target_text:sub(3), 16))

local output_path = required_env("MGBA_BREAKPOINT_TRACE_OUTPUT")
local max_hits_text = os.getenv("MGBA_BREAKPOINT_TRACE_MAX_HITS") or "256"
assert(
	max_hits_text:match("^[1-9][0-9]*$"),
	"MGBA_BREAKPOINT_TRACE_MAX_HITS must be a positive integer"
)
local max_hits = assert(tonumber(max_hits_text), "MGBA_BREAKPOINT_TRACE_MAX_HITS must be a positive integer")
assert(
	max_hits < math.huge,
	"MGBA_BREAKPOINT_TRACE_MAX_HITS must be a positive integer"
)

local f = assert(io.open(output_path, "a"), "cannot open breakpoint trace output")
local frame = 0
local hit_count = 0
local breakpoint_id = nil

local function clear_and_close()
	assert(emu:clearBreakpoint(breakpoint_id), "failed to clear breakpoint")
	breakpoint_id = nil
	assert(f:close(), "failed to close breakpoint trace output")
end

local function on_breakpoint()
	if hit_count >= max_hits then
		clear_and_close()
		return
	end

	hit_count = hit_count + 1
	local line = string.format(
		'{"schema_version":1,"hit":%d,"frame":%d,"cycle":%d,"target":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X"}',
		hit_count,
		frame,
		emu:currentCycle(),
		target,
		emu:readRegister("pc"),
		emu:readRegister("lr"),
		emu:readRegister("sp")
	)
	f:write(line, "\n")
	f:flush()

	if hit_count >= max_hits then
		clear_and_close()
	end
end

callbacks:add("start", function()
	local installed_id = emu:setBreakpoint(on_breakpoint, target)
	if type(installed_id) ~= "number" or installed_id < 0 or installed_id ~= math.floor(installed_id) then
		f:close()
		error("failed to set breakpoint", 0)
	end
	breakpoint_id = installed_id
end)

callbacks:add("frame", function()
	frame = frame + 1
end)
