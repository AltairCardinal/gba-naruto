-- Diagnostic probe for the battle roster dump.
--
-- It enumerates the memory domains the running mGBA exposes, reports whether
-- the requested savestate loads, and writes a log so a failing run can be
-- diagnosed without a debugger.  The guard terminates the emulator once the
-- done marker appears, so the probe never has to kill the process itself.

local output_dir = os.getenv("MGBA_ROSTER_OUTPUT_DIR")
assert(output_dir, "missing MGBA_ROSTER_OUTPUT_DIR")

local function log(message)
	local output = assert(io.open(output_dir .. "/log.txt", "a"))
	output:write(tostring(message) .. "\n")
	output:close()
end

log("probe start")

local names = {}
for name in pairs(emu.memory) do
	names[#names + 1] = name
end
table.sort(names)
log("domains: " .. table.concat(names, ","))

for _, name in ipairs(names) do
	local domain = emu.memory[name]
	local ok, bytes = pcall(function() return domain:readRange(0, 16) end)
	log(string.format(
		"domain %s readable=%s len=%s",
		name,
		tostring(ok),
		ok and tostring(#bytes) or "n/a"))
end

local state = os.getenv("MGBA_ROSTER_INPUT_STATE")
local ok, result = pcall(function() return emu:loadStateFile(state) end)
log("loadStateFile ok=" .. tostring(ok) .. " result=" .. tostring(result))

log("probe end")
