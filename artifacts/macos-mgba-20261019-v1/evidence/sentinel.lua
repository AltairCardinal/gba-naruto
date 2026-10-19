local marker = "/Users/altair/github/gba-naruto/artifacts/macos-mgba-20261019-v1/evidence/sentinel-result.json"
local run_id = "ab6f4894f3c91a4a813168780989f4bd"
local frame = 0
local capture_complete = false

local function write_marker(payload)
    local out = assert(io.open(marker, "w"))
    out:write(payload)
    out:close()
end

write_marker(string.format('{"script_loaded":true,"frame":0,"pc":"loaded","run_id":"%s"}', run_id))
callbacks:add("frame", function()
    if capture_complete then
        return
    end
    frame = frame + 1
    local pc = tostring(emu:readRegister("pc"))
    write_marker(string.format('{"script_loaded":true,"frame":%d,"pc":"%s","run_id":"%s"}', frame, pc, run_id))
    capture_complete = true
end)
