-- Check whether mGBA's Lua VRAM domain can be read at all, and in what
-- granularity, once the game has actually rendered something.
--
-- Usage: set DUMP_VRAMCHK_OUT to a file path.

local out_path = os.getenv("DUMP_VRAMCHK_OUT")
assert(out_path and out_path ~= "", "missing DUMP_VRAMCHK_OUT")

local file = assert(io.open(out_path, "w"))
local vram = emu.memory["vram"]
local frame = 0

local function report(label, bytes)
    if type(bytes) ~= "string" then
        file:write(string.format("  %s: NOT A STRING (%s)\n", label, tostring(bytes)))
        return 0
    end
    local nonzero = 0
    for i = 1, #bytes do
        if string.byte(bytes, i) ~= 0 then
            nonzero = nonzero + 1
        end
    end
    file:write(string.format("  %s: len=%d nonzero=%d\n", label, #bytes, nonzero))
    return nonzero
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame ~= 300 and frame ~= 301 then
        return
    end
    file:write("=== frame " .. frame .. " ===\n")

    for _, size in ipairs({ 256, 4096, 16384, 65536, 98304 }) do
        local ok, bytes = pcall(function() return vram:readRange(0, size) end)
        if not ok then
            file:write(string.format("  readRange(0,%d): RAISED %s\n", size, tostring(bytes)))
        else
            report(string.format("readRange(0,%d)", size), bytes)
        end
    end

    -- Chunks, in case a big single read is the problem.
    local base = 0x4C00
    for _, size in ipairs({ 2048, 4096, 8192 }) do
        local ok, bytes = pcall(function() return vram:readRange(base, size) end)
        if not ok then
            file:write(string.format("  readRange(0x%X,%d): RAISED %s\n", base, size, tostring(bytes)))
        else
            report(string.format("readRange(0x%X,%d)", base, size), bytes)
        end
    end
    file:close()
end)
