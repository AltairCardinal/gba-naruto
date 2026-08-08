-- Trace one tile-assets initializer transaction from a fixed state.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local input_state = required_env("TILE_TRACE_INPUT_STATE")
local input_state_sha256 = required_env("TILE_TRACE_INPUT_STATE_SHA256")
local output_dir = required_env("TILE_TRACE_OUTPUT_DIR")
local done_marker = required_env("TILE_TRACE_DONE_MARKER")
local run_id = required_env("TILE_TRACE_RUN_ID")
local rom_sha256 = required_env("TILE_TRACE_ROM_SHA256")
local script_sha256 = required_env("TILE_TRACE_SCRIPT_SHA256")
local frame_limit = assert(tonumber(required_env("TILE_TRACE_FRAME_LIMIT")))
local a_down_frame = assert(tonumber(os.getenv("TILE_TRACE_A_DOWN_FRAME") or "0"))
local a_up_frame = assert(tonumber(os.getenv("TILE_TRACE_A_UP_FRAME") or "0"))
assert(frame_limit >= 1 and frame_limit <= 900 and frame_limit == math.floor(frame_limit))
assert(
	(a_down_frame == 0 and a_up_frame == 0)
		or (a_down_frame > 0 and a_down_frame < a_up_frame and a_up_frame < frame_limit),
	"invalid optional A interval"
)

local TABLE_ADDRESS = 0x085A320C
local RECORD_SIZE = 0x44
local RECORD_COUNT = 79
local targets = {
	{name = "scene-panel-result", address = 0x0808BECC, required = false},
	{name = "controller-entry", address = 0x0808C214, required = false},
	{name = "presentation-selector", address = 0x0808C18C, required = false},
	{name = "presentation-call", address = 0x0808C1D8, required = false},
	{name = "initializer-entry", address = 0x080983B8, required = true},
	{name = "descriptor-selected", address = 0x08098462, required = true},
	{name = "graphics-source-load", address = 0x0809848E, required = true},
	{name = "palette-source-load", address = 0x080984A4, required = true},
	{name = "layout-source-load", address = 0x080984B6, required = true},
}
local REQUIRED_TARGET_COUNT = 5

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex32(value)
	return string.format("0x%08X", value or 0)
end

local function read_hex(address, size)
	local bytes = {}
	for index = 0, size - 1 do
		bytes[#bytes + 1] = string.format("%02x", emu:read8(address + index))
	end
	return table.concat(bytes)
end

local frame = 0
local complete = false
local events = {}
local breakpoint_ids = {}
local hit_names = {}
local required_hit_count = 0

local function inputs_json()
	if a_down_frame == 0 then return "[]" end
	return table.concat({
		'[{"key":"A","down_frame":', tostring(a_down_frame),
		',"up_frame":', tostring(a_up_frame),
		',"hold_frames":', tostring(a_up_frame - a_down_frame), '}]',
	})
end

local function descriptor_context(pointer)
	local delta = pointer - TABLE_ADDRESS
	if delta < 0 or delta % RECORD_SIZE ~= 0 then
		return -1, ""
	end
	local record_id = delta // RECORD_SIZE
	if record_id < 0 or record_id >= RECORD_COUNT then
		return -1, ""
	end
	return record_id, read_hex(pointer, RECORD_SIZE)
end

local function event_json(event)
	return table.concat({
		'{"name":', q(event.name),
		',"address":', q(hex32(event.address)),
		',"required":', tostring(event.required),
		',"frame":', tostring(event.frame),
		',"cycle":', q(event.cycle),
		',"r0":', q(hex32(event.r0)),
		',"r1":', q(hex32(event.r1)),
		',"r2":', q(hex32(event.r2)),
		',"r3":', q(hex32(event.r3)),
		',"r8":', q(hex32(event.r8)),
		',"sp":', q(hex32(event.sp)),
		',"lr":', q(hex32(event.lr)),
		',"descriptor_id":', tostring(event.descriptor_id),
		',"descriptor_hex":', q(event.descriptor_hex),
		'}',
	})
end

local function finish(outcome)
	if complete then return end
	complete = true
	emu:setKeys(0)
	for _, breakpoint_id in ipairs(breakpoint_ids) do
		pcall(function() emu:clearBreakpoint(breakpoint_id) end)
	end
	assert(emu:saveStateFile(output_dir .. "/final.ss9"), "failed to save trace state")
	emu:screenshot(output_dir .. "/final.png")
	local rows = {}
	for _, event in ipairs(events) do rows[#rows + 1] = event_json(event) end
	local audit = table.concat({
		'{"schema":"tile-asset-initializer-trace-v1"',
		',"run_id":', q(run_id),
		',"outcome":', q(outcome),
		',"frame":', tostring(frame),
		',"frame_limit":', tostring(frame_limit),
		',"input_mode":', q(a_down_frame == 0 and "zero-input-active-state" or "single-a-active-state"),
		',"inputs":', inputs_json(),
		',"recovery_inputs":[]',
		',"input_state":', q(input_state),
		',"input_state_sha256":', q(input_state_sha256),
		',"rom_sha256":', q(rom_sha256),
		',"script_sha256":', q(script_sha256),
		',"target_count":', tostring(#targets),
		',"required_target_count":', tostring(REQUIRED_TARGET_COUNT),
		',"required_hit_count":', tostring(required_hit_count),
		',"hit_count":', tostring(#events),
		',"events":[', table.concat(rows, ','), ']}',
	})
	local audit_file = assert(io.open(output_dir .. "/audit.json", "w"))
	audit_file:write(audit)
	audit_file:close()
	local done = assert(io.open(done_marker, "w"))
	done:write('{"run_id":' .. q(run_id) .. ',"status":' .. q(outcome)
		.. ',"required_hit_count":' .. tostring(required_hit_count)
		.. ',"hit_count":' .. tostring(#events) .. '}')
	done:close()
end

assert(emu:loadStateFile(input_state), "failed to load tile trace input state")
emu:setKeys(0)

for _, target in ipairs(targets) do
	local target_copy = target
	local breakpoint_id = assert(emu:setBreakpoint(function()
		if complete or hit_names[target_copy.name] then return end
		local r8 = emu:readRegister("r8") or 0
		local descriptor_id, descriptor_hex = descriptor_context(r8)
		events[#events + 1] = {
			name = target_copy.name,
			address = target_copy.address,
			required = target_copy.required,
			frame = frame,
			cycle = tostring(emu:currentCycle()),
			r0 = emu:readRegister("r0") or 0,
			r1 = emu:readRegister("r1") or 0,
			r2 = emu:readRegister("r2") or 0,
			r3 = emu:readRegister("r3") or 0,
			r8 = r8,
			sp = emu:readRegister("sp") or 0,
			lr = emu:readRegister("lr") or 0,
			descriptor_id = descriptor_id,
			descriptor_hex = descriptor_hex,
		}
		hit_names[target_copy.name] = true
		if target_copy.required then required_hit_count = required_hit_count + 1 end
		if required_hit_count == REQUIRED_TARGET_COUNT then finish("all-boundaries-hit") end
	end, target.address))
	assert(breakpoint_id > 0, "failed to install tile trace breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = breakpoint_id
end

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	if frame == a_down_frame then
		emu:addKey(C.GBA_KEY.A)
	elseif frame == a_up_frame then
		emu:clearKey(C.GBA_KEY.A)
	end
	if frame >= frame_limit then finish("frame-limit") end
end)

while not complete do emu:frameAdvance() end
