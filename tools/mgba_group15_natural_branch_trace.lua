local input_state = assert(os.getenv("NATURAL_TRACE_INPUT_STATE"))
local output_state = assert(os.getenv("NATURAL_TRACE_OUTPUT_STATE"))
local output_png = assert(os.getenv("NATURAL_TRACE_OUTPUT_PNG"))
local audit_path = assert(os.getenv("NATURAL_TRACE_AUDIT"))
local done_path = assert(os.getenv("NATURAL_TRACE_DONE"))
local run_id = assert(os.getenv("NATURAL_TRACE_RUN_ID"))
local rom_sha256 = assert(os.getenv("NATURAL_TRACE_ROM_SHA256"))
local input_state_sha256 = assert(os.getenv("NATURAL_TRACE_INPUT_STATE_SHA256"))
local script_sha256 = assert(os.getenv("NATURAL_TRACE_SCRIPT_SHA256"))

local targets = {
	{"event-action-write", 0x080755FA},
	{"runtime-copy-a", 0x0807A0CA},
	{"runtime-copy-b", 0x0807A222},
	{"presentation-entry", 0x0807F064},
	{"classification-cmp", 0x0807F09E},
	{"special-sequence-6", 0x0807F0D4},
	{"dynamic-selector", 0x0807F0FC},
	{"dynamic-binder-call", 0x0807F10C},
	{"binder-entry", 0x0807C5E8},
}

local frame = 0
local events = {}
local breakpoint_ids = {}
local complete = false

local function q(value)
	return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function write(path, payload)
	local file = assert(io.open(path, "w"))
	file:write(payload)
	file:close()
end

local function reg(name)
	return emu:readRegister(name) or 0
end

local function event_json(event)
	return table.concat({
		'{"name":', q(event.name),
		',"address":', q(string.format("0x%08X", event.address)),
		',"frame":', tostring(event.frame),
		',"cycle":', q(event.cycle),
		',"pc":', q(string.format("0x%08X", event.pc)),
		',"lr":', q(string.format("0x%08X", event.lr)),
		',"r0":', q(string.format("0x%08X", event.r0)),
		',"r1":', q(string.format("0x%08X", event.r1)),
		',"r2":', q(string.format("0x%08X", event.r2)),
		',"r3":', q(string.format("0x%08X", event.r3)),
		',"r4":', q(string.format("0x%08X", event.r4)),
		',"r5":', q(string.format("0x%08X", event.r5)),
		'}'
	})
end

local function finish()
	if complete then return end
	complete = true
	emu:setKeys(0)
	for _, id in ipairs(breakpoint_ids) do emu:clearBreakpoint(id) end
	assert(emu:saveStateFile(output_state))
	emu:screenshot(output_png)
	local rows = {}
	for _, event in ipairs(events) do rows[#rows + 1] = event_json(event) end
	write(audit_path, table.concat({
		'{"schema":"natural-battle-effect-branch-trace-experiment-v1"',
		',"run_id":', q(run_id),
		',"frame":', tostring(frame),
		',"capture_frame":1800',
		',"input_state":', q(input_state),
		',"rom_sha256":', q(rom_sha256),
		',"input_state_sha256":', q(input_state_sha256),
		',"script_sha256":', q(script_sha256),
		',"inputs":[{"key":"A","down_frame":60,"up_frame":68,"hold_frames":8}]',
		',"automatic_inputs":[]',
		',"recovery_inputs":[]',
		',"events":[', table.concat(rows, ','), ']}'
	}))
	write(done_path, '{"run_id":' .. q(run_id) .. ',"status":"trace-complete"}')
end

assert(emu:loadStateFile(input_state))
emu:setKeys(0)
for _, target in ipairs(targets) do
	local name, address = target[1], target[2]
	local id = assert(emu:setBreakpoint(function()
		events[#events + 1] = {
			name=name, address=address, frame=frame,
			cycle=tostring(emu:currentCycle()), pc=reg("pc"), lr=reg("lr"),
			r0=reg("r0"), r1=reg("r1"), r2=reg("r2"), r3=reg("r3"),
			r4=reg("r4"), r5=reg("r5"),
		}
	end, address))
	breakpoint_ids[#breakpoint_ids + 1] = id
end

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	if frame == 60 then emu:addKey(C.GBA_KEY.A) end
	if frame == 68 then emu:clearKey(C.GBA_KEY.A) end
	if frame >= 1800 then finish() end
end)
