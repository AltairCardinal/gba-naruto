-- Trace a controlled chapter command into the native story visual consumer.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex32(value)
	return string.format("0x%08X", value or 0)
end

local input_state = required_env("STORY_TRACE_INPUT_STATE")
local input_state_sha256 = required_env("STORY_TRACE_INPUT_STATE_SHA256")
local output_state = required_env("STORY_TRACE_OUTPUT_STATE")
local output_png = required_env("STORY_TRACE_OUTPUT_PNG")
local audit_path = required_env("STORY_TRACE_AUDIT")
local done_marker = required_env("STORY_TRACE_DONE_MARKER")
local run_id = required_env("STORY_TRACE_RUN_ID")
local rom_sha256 = required_env("STORY_TRACE_ROM_SHA256")
local script_sha256 = required_env("STORY_TRACE_SCRIPT_SHA256")
local frame_limit = assert(tonumber(required_env("STORY_TRACE_FRAME_LIMIT")))
assert(frame_limit >= 60 and frame_limit <= 1200 and frame_limit == math.floor(frame_limit))

local STORY_TABLE = 0x0854229C
local STORY_STATE = 0x020311D4
local CONTROLLED_CURSOR = 0x08049E63
local events = {}
local hit = {}
local breakpoint_ids = {}
local frame = 0
local complete = false
local overlay_vblank_count = 0

local function event(name, address, extra)
	if hit[name] then return end
	hit[name] = true
	local row = {
		name = name,
		address = address,
		frame = frame,
		cycle = tostring(emu:currentCycle()),
		pc = emu:readRegister("pc") or 0,
		lr = emu:readRegister("lr") or 0,
		r0 = emu:readRegister("r0") or 0,
		r1 = emu:readRegister("r1") or 0,
		r2 = emu:readRegister("r2") or 0,
		r3 = emu:readRegister("r3") or 0,
		r7 = emu:readRegister("r7") or 0,
		story_state = emu:read16(STORY_STATE + 0x12),
		extra = extra or "",
	}
	events[#events + 1] = row
end

local function event_json(row)
	return table.concat({
		'{"name":', q(row.name),
		',"address":', q(hex32(row.address)),
		',"frame":', tostring(row.frame),
		',"cycle":', q(row.cycle),
		',"pc":', q(hex32(row.pc)),
		',"lr":', q(hex32(row.lr)),
		',"r0":', q(hex32(row.r0)),
		',"r1":', q(hex32(row.r1)),
		',"r2":', q(hex32(row.r2)),
		',"r3":', q(hex32(row.r3)),
		',"r7":', q(hex32(row.r7)),
		',"story_state":', q(string.format("0x%04X", row.story_state)),
		',"extra":', q(row.extra), '}'
	})
end

local required_names = {
	"chapter-opcode-14",
	"story-state-dispatch",
	"story-wrapper",
	"story-loader",
	"descriptor-0-select",
	"gfx-decompress",
	"palette-decompress",
	"tilemap-decompress",
	"overlay-first-vblank",
}

local function finish(outcome)
	if complete then return end
	complete = true
	emu:setKeys(0)
	for _, id in ipairs(breakpoint_ids) do pcall(function() emu:clearBreakpoint(id) end) end
	assert(emu:saveStateFile(output_state), "failed to save story trace state")
	emu:screenshot(output_png)
	local missing = {}
	for _, name in ipairs(required_names) do
		if not hit[name] then missing[#missing + 1] = name end
	end
	local rows = {}
	for _, row in ipairs(events) do rows[#rows + 1] = event_json(row) end
	local missing_json = {}
	for _, name in ipairs(missing) do missing_json[#missing_json + 1] = q(name) end
	local audit = table.concat({
		'{"schema":"battle-encounters-story-visual-trace-v1"',
		',"run_id":', q(run_id),
		',"outcome":', q(outcome),
		',"frame":', tostring(frame),
		',"frame_limit":', tostring(frame_limit),
		',"rom_sha256":', q(rom_sha256),
		',"script_sha256":', q(script_sha256),
		',"input_state":', q(input_state),
		',"input_state_sha256":', q(input_state_sha256),
		',"inputs":[{"key":"A","down_frame":2,"up_frame":10,"hold_frames":8}]',
		',"controlled_cursor":', q(hex32(CONTROLLED_CURSOR)),
		',"story_table":', q(hex32(STORY_TABLE)),
		',"missing":[', table.concat(missing_json, ','), ']',
		',"events":[', table.concat(rows, ','), ']}'
	})
	local file = assert(io.open(audit_path, "w")); file:write(audit); file:close()
	local done = assert(io.open(done_marker, "w"))
	done:write('{"run_id":' .. q(run_id) .. ',"outcome":' .. q(outcome)
		.. ',"missing_count":' .. tostring(#missing) .. '}')
	done:close()
end

assert(emu:loadStateFile(input_state), "failed to load story trace input state")
emu:setKeys(0)

local function add_breakpoint(address, callback)
	local id = assert(emu:setBreakpoint(callback, address))
	assert(id > 0, "failed to install story trace breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = id
end

add_breakpoint(0x08097BBC, function()
	if (emu:readRegister("r7") or 0) == CONTROLLED_CURSOR then
		event("chapter-opcode-14", 0x08097BBC, "raw=146801")
	end
end)
add_breakpoint(0x0808FA2C, function()
	event("story-state-dispatch", 0x0808FA2C, "expected-state=0x8000")
end)
add_breakpoint(0x0808A69C, function()
	event("story-wrapper", 0x0808A69C, "")
end)
add_breakpoint(0x08087C9C, function()
	event("story-loader", 0x08087C9C, "")
end)
add_breakpoint(0x08087DE8, function()
	if (emu:readRegister("r7") or 0) == 0 then
		event("descriptor-0-select", 0x08087DE8, "table=0x0854229C")
	end
end)
add_breakpoint(0x0809C0E8, function()
	local lr = emu:readRegister("lr") or 0
	if lr == 0x08087E83 then
		event("gfx-decompress", 0x0809C0E8, "destination=0x0600E800")
	elseif lr == 0x08087E91 then
		event("palette-decompress", 0x0809C0E8, "destination=0x050001E0")
	elseif lr == 0x08087E9D then
		event("tilemap-decompress", 0x0809C0E8, "destination=0x06001800")
	end
end)
add_breakpoint(0x08087EC0, function()
	if hit["descriptor-0-select"] then
		overlay_vblank_count = overlay_vblank_count + 1
		if overlay_vblank_count == 1 then
			event("overlay-first-vblank", 0x08087EC0, "story-index=0")
		elseif overlay_vblank_count == 8 then
			finish("capture-complete")
		end
	end
end)

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	if frame == 2 then emu:addKey(C.GBA_KEY.A) end
	if frame == 10 then emu:clearKey(C.GBA_KEY.A) end
	if frame >= frame_limit then finish("frame-limit") end
end)
