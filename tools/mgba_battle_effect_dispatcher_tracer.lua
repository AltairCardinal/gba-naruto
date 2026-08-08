-- Trace the inner-layer dispatcher 0x0807C93C to find R0/R1/R2/R3 sources.
-- Uses mGBA 0.10+/d8bad14b+ API: emu:setBreakpoint(cb, address, segment).
--
-- Env vars:
--   TRACER_OUTPUT_AUDIT, TRACER_OUTPUT_DONE, TRACER_OUTPUT_PNG
--   TRACER_INPUT_STATE, TRACER_INPUT_STATE_SHA256
--   TRACER_HIT_LIMIT, TRACER_FRAME_LIMIT

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local audit_path = required_env("TRACER_OUTPUT_AUDIT")
local done_marker = required_env("TRACER_OUTPUT_DONE")
local output_png = required_env("TRACER_OUTPUT_PNG")
local input_state = required_env("TRACER_INPUT_STATE")
local input_state_sha256 = required_env("TRACER_INPUT_STATE_SHA256")
local hit_limit = assert(tonumber(required_env("TRACER_HIT_LIMIT")))
local frame_limit = assert(tonumber(required_env("TRACER_FRAME_LIMIT")))
local tracer_sha = required_env("TRACER_SHA")
assert(hit_limit >= 1 and hit_limit == math.floor(hit_limit), "invalid hit limit")
assert(frame_limit >= 1 and frame_limit == math.floor(frame_limit), "invalid frame limit")

local dispatcher_addr = 0x0807C93C
local hits = {}
local breakpoint_id = nil
local complete = false
local frame = 0

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex(value)
	return string.format("0x%08X", value or 0)
end

local function write_audit()
	local f = assert(io.open(audit_path, "w"))
	local payload = '{' ..
		'"schema":"battle-effect-dispatcher-tracer-v1",' ..
		'"tracer_sha":' .. q(tracer_sha) .. ',' ..
		'"input_state":' .. q(input_state) .. ',' ..
		'"input_state_sha256":' .. q(input_state_sha256) .. ',' ..
		'"frame_limit":' .. frame_limit .. ',' ..
		'"dispatcher_addr":"0x0807C93C",' ..
		'"hit_count":' .. #hits .. ',' ..
		'"hits":['
	for i, hit in ipairs(hits) do
		payload = payload .. (i > 1 and "," or "") .. '{' ..
			'"hit_index":' .. i .. ',' ..
			'"frame":' .. hit.frame .. ',' ..
			'"r0":' .. q(hex(hit.r0)) .. ',' ..
			'"r1":' .. q(hex(hit.r1)) .. ',' ..
			'"r2":' .. q(hex(hit.r2)) .. ',' ..
			'"r3":' .. q(hex(hit.r3)) .. ',' ..
			'"sp":' .. q(hex(hit.sp)) .. ',' ..
			'"lr":' .. q(hex(hit.lr)) ..
			'}'
	end
	payload = payload .. "]}"
	f:write(payload)
	f:close()
end

local function finish()
	if complete then return end
	complete = true
	if breakpoint_id then emu:clearBreakpoint(breakpoint_id) end
	emu:setKeys(0)
	emu:screenshot(output_png)
	write_audit()
	local m = assert(io.open(done_marker, "w"))
	m:write('{"hit_count":' .. #hits .. ',"sha":' .. q(tracer_sha) .. '}')
	m:close()
end

local function on_break()
	if complete then return end
	table.insert(hits, {
		frame = frame,
		r0 = emu:readRegister("r0") or 0,
		r1 = emu:readRegister("r1") or 0,
		r2 = emu:readRegister("r2") or 0,
		r3 = emu:readRegister("r3") or 0,
		sp = emu:readRegister("sp") or 0,
		lr = emu:readRegister("lr") or 0,
	})
	if #hits >= hit_limit then finish() end
end

assert(emu:loadStateFile(input_state), "failed to load tracer input state")
emu:setKeys(0)
breakpoint_id = emu:setBreakpoint(on_break, dispatcher_addr)
assert(breakpoint_id and breakpoint_id > 0, "failed to install dispatcher breakpoint")

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	emu:setKeys(0)
	if frame >= frame_limit then finish() end
end)
