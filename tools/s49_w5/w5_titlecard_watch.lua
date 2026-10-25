-- W5: watch the 开战 (battle start) title card run with no input at all.
--
-- Why this exists
-- ---------------
-- The two A-key walks diverge between original step 9 and step 10.  The
-- original's EWRAM diff across that gap changes exactly ONE word -- a 30 Hz
-- tick counter -- so the A press there was swallowed: the game state did not
-- move.  The title card therefore advances by *time*, not by input.
--
-- The question this script answers is the remaining one: how long does each
-- side's title card stay on screen when nobody presses anything?
--
-- It loads a captured savestate, presses nothing (unless W5_PRESS says
-- otherwise), and screenshots every W5_EVERY frames for W5_FRAMES frames.
--
-- Environment
--   W5_STATE   savestate to load                       (required)
--   W5_OUTDIR  directory for the screenshots           (required)
--   W5_FRAMES  frames to run            (default 300)
--   W5_EVERY   screenshot every N frames(default 10)
--   W5_PRESS   "none" (default) or "A" (A held frames 1..4)

local state = os.getenv("W5_STATE")
local outdir = os.getenv("W5_OUTDIR")
local frames = tonumber(os.getenv("W5_FRAMES")) or 300
local every = tonumber(os.getenv("W5_EVERY")) or 10
local press = os.getenv("W5_PRESS") or "none"

assert(state and outdir, "W5_STATE and W5_OUTDIR are required")
assert(emu:loadStateFile(state), "failed to load " .. state)

local frame = 0

callbacks:add("frame", function()
	frame = frame + 1
	if press == "A" then
		if frame == 1 then
			emu:addKey(C.GBA_KEY.A)
		elseif frame == 5 then
			emu:clearKey(C.GBA_KEY.A)
		end
	end
	if frame <= frames and frame % every == 0 then
		emu:screenshot(string.format("%s/f%04d.png", outdir, frame))
	end
end)
