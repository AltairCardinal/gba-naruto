-- Trace the real FIFO/DMA initializer and one controlled SoundMain invocation.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function q(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function hex8(value) return string.format("0x%02X", value or 0) end
local function hex16(value) return string.format("0x%04X", value or 0) end
local function hex32(value) return string.format("0x%08X", (value or 0) % 0x100000000) end

local output_state = required_env("SAPPY_TRACE_OUTPUT_STATE")
local output_png = required_env("SAPPY_TRACE_OUTPUT_PNG")
local input_state = required_env("SAPPY_TRACE_INPUT_STATE")
local input_state_sha256 = required_env("SAPPY_TRACE_INPUT_STATE_SHA256")
local audit_path = required_env("SAPPY_TRACE_AUDIT")
local done_marker = required_env("SAPPY_TRACE_DONE_MARKER")
local run_id = required_env("SAPPY_TRACE_RUN_ID")
local variant = required_env("SAPPY_TRACE_VARIANT")
local rom_sha256 = required_env("SAPPY_TRACE_ROM_SHA256")
local script_sha256 = required_env("SAPPY_TRACE_SCRIPT_SHA256")
local frame_limit = assert(tonumber(required_env("SAPPY_TRACE_FRAME_LIMIT")))
assert(frame_limit >= 30 and frame_limit <= 600 and frame_limit == math.floor(frame_limit))

local INITIALIZER_ENTRY = 0x0809AE3C
local INITIALIZER_EXIT = 0x0809AEF2
local SOUND_DISPATCH = 0x0809AAC0
local SOUNDMAIN_RETURN = 0x0809AABA
local SOUND_INFO = 0x03006570
local DIRECT_RIGHT = 0x030068C0
local DIRECT_LEFT = 0x03006EF0
local BUFFER_FRAMES = 264
local SOUND_ID = 101

local frame = 0
local complete = false
local entry = nil
local exit_event = nil
local dispatch = nil
local soundmain = nil
local breakpoint_ids = {}

local function bytes_hex(address, size)
	local parts = {}
	for index = 0, size - 1 do
		parts[#parts + 1] = string.format("%02x", emu:read8(address + index))
	end
	return table.concat(parts)
end

local function io_state_json()
	return table.concat({
		'{"soundcnt_l":', q(hex16(emu:read16(0x04000080))),
		',"soundcnt_h":', q(hex16(emu:read16(0x04000082))),
		',"soundcnt_x":', q(hex16(emu:read16(0x04000084))),
		',"soundbias":', q(hex16(emu:read16(0x04000088))),
		',"dma1sad":', q(hex32(emu:read32(0x040000BC))),
		',"dma1dad":', q(hex32(emu:read32(0x040000C0))),
		',"dma1cnt":', q(hex32(emu:read32(0x040000C4))),
		',"fifo_a":', q(hex32(emu:read32(0x040000A0))),
		',"dma2sad":', q(hex32(emu:read32(0x040000C8))),
		',"dma2dad":', q(hex32(emu:read32(0x040000CC))),
		',"dma2cnt":', q(hex32(emu:read32(0x040000D0))),
		',"fifo_b":', q(hex32(emu:read32(0x040000A4))), '}'
	})
end

local function register_event_json(row)
	if not row then return "null" end
	return table.concat({
		'{"frame":', tostring(row.frame),
		',"cycle":', q(row.cycle),
		',"pc":', q(hex32(row.pc)),
		',"lr":', q(hex32(row.lr)),
		',"r0":', q(hex32(row.r0)),
		',"io":', row.hardware_state, '}'
	})
end

local function capture_register_event()
	return {
		frame = frame,
		cycle = tostring(emu:currentCycle()),
		pc = emu:readRegister("pc") or 0,
		lr = emu:readRegister("lr") or 0,
		r0 = emu:readRegister("r0") or 0,
		hardware_state = io_state_json(),
	}
end

local function finish(outcome)
	if complete then return end
	complete = true
	emu:setKeys(0)
	for _, id in ipairs(breakpoint_ids) do pcall(function() emu:clearBreakpoint(id) end) end
	assert(emu:saveStateFile(output_state), "failed to save sappy trace state")
	emu:screenshot(output_png)
	local missing = {}
	if not entry then missing[#missing + 1] = "initializer-entry" end
	if not exit_event then missing[#missing + 1] = "initializer-exit" end
	if not dispatch then missing[#missing + 1] = "sound-101-dispatch" end
	if not soundmain then missing[#missing + 1] = "first-soundmain-return" end
	local missing_json = {}
	for _, name in ipairs(missing) do missing_json[#missing_json + 1] = q(name) end
	local soundmain_json = "null"
	if soundmain then
		soundmain_json = table.concat({
			'{"frame":', tostring(soundmain.frame),
			',"cycle":', q(soundmain.cycle),
			',"pc":', q(hex32(soundmain.pc)),
			',"counter":', q(hex8(soundmain.counter)),
			',"sound_info_magic":', q(hex32(soundmain.magic)),
			',"right_hex":', q(soundmain.right_hex),
			',"left_hex":', q(soundmain.left_hex),
			',"io":', soundmain.hardware_state, '}'
		})
	end
	local audit = table.concat({
		'{"schema":"sappy-engine-master-enable-trace-v1"',
		',"run_id":', q(run_id),
		',"variant":', q(variant),
		',"outcome":', q(outcome),
		',"frame":', tostring(frame),
		',"frame_limit":', tostring(frame_limit),
		',"rom_sha256":', q(rom_sha256),
		',"script_sha256":', q(script_sha256),
		',"input_state":', q(input_state),
		',"input_state_sha256":', q(input_state_sha256),
		',"sound_id":', tostring(SOUND_ID),
		',"inputs":[{"key":"A","down_frame":5,"up_frame":13,"hold_frames":8}]',
		',"initializer_entry":', register_event_json(entry),
		',"initializer_exit":', register_event_json(exit_event),
		',"dispatch":', register_event_json(dispatch),
		',"soundmain":', soundmain_json,
		',"missing":[', table.concat(missing_json, ','), ']}'
	})
	local file = assert(io.open(audit_path, "w")); file:write(audit); file:close()
	local done = assert(io.open(done_marker, "w"))
	done:write('{"run_id":' .. q(run_id) .. ',"variant":' .. q(variant)
		.. ',"outcome":' .. q(outcome) .. ',"missing_count":' .. tostring(#missing) .. '}')
	done:close()
end

local function add_breakpoint(address, callback)
	local id = assert(emu:setBreakpoint(callback, address))
	assert(id > 0, "failed to install sappy trace breakpoint")
	breakpoint_ids[#breakpoint_ids + 1] = id
end

assert(emu:loadStateFile(input_state), "failed to load sappy trace input state")
emu:setKeys(0)

add_breakpoint(INITIALIZER_ENTRY, function()
	if not entry then entry = capture_register_event() end
end)
add_breakpoint(INITIALIZER_EXIT, function()
	if entry and not exit_event then exit_event = capture_register_event() end
end)
add_breakpoint(SOUND_DISPATCH, function()
	if (emu:readRegister("r0") or 0) == SOUND_ID and not dispatch then
		dispatch = capture_register_event()
	end
end)
add_breakpoint(SOUNDMAIN_RETURN, function()
	if dispatch and not soundmain then
		soundmain = {
			frame = frame,
			cycle = tostring(emu:currentCycle()),
			pc = emu:readRegister("pc") or 0,
			counter = emu:read8(SOUND_INFO + 4),
			magic = emu:read32(SOUND_INFO),
			right_hex = bytes_hex(DIRECT_RIGHT, BUFFER_FRAMES),
			left_hex = bytes_hex(DIRECT_LEFT, BUFFER_FRAMES),
			hardware_state = io_state_json(),
		}
		finish("capture-complete")
	end
end)

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	if frame == 5 then emu:addKey(C.GBA_KEY.A) end
	if frame == 13 then emu:clearKey(C.GBA_KEY.A) end
	if frame >= frame_limit then finish("frame-limit") end
end)
