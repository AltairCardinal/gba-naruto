-- Quick palette bank player-visible probe.
-- Loads savestate, advances N frames, saves screenshot.
-- Caller compares baseline.png vs candidate.png.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local output_png = required_env("PALETTES_PROBE_OUTPUT_PNG")
local done_marker = required_env("PALETTES_PROBE_DONE_MARKER")
local capture_frame = tonumber(required_env("PALETTES_PROBE_CAPTURE_FRAME"))
local done_marker_sha = required_env("PALETTES_PROBE_DONE_SHA")

local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then return end
	frame = frame + 1
	if frame >= capture_frame then
		complete = true
		emu:screenshot(output_png)
		local f = assert(io.open(done_marker, "w"))
		f:write('{"frame":' .. frame .. ',"sha":"' .. done_marker_sha .. '"}')
		f:close()
	end
end)

while not complete do emu:frameAdvance() end