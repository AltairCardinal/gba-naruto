-- Capture a screenshot after the AI action submission spawns a task.
-- Uses scenario 50 / battle 15 escort-12hp-player-turn baseline. Loads ROM,
-- advances enough frames for an AI action to spawn a task, then saves.
--
-- Env vars:
--   PALETTES_SPAWN_OUTPUT_PNG, PALETTES_SPAWN_DONE_MARKER
--   PALETTES_SPAWN_CAPTURE_FRAME  (default 600)
--   PALETTES_SPAWN_DONE_SHA       (free-form label)

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local output_png = required_env("PALETTES_SPAWN_OUTPUT_PNG")
local done_marker = required_env("PALETTES_SPAWN_DONE_MARKER")
local capture_frame = tonumber(required_env("PALETTES_SPAWN_CAPTURE_FRAME") or "600")
local done_marker_sha = required_env("PALETTES_SPAWN_DONE_SHA")

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