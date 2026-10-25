-- Probe which memory domains the Lua API exposes and what they return.
-- Usage: set DUMP_DOMAINS_OUT to a file path.

local out_path = os.getenv("DUMP_DOMAINS_OUT")
assert(out_path and out_path ~= "", "missing DUMP_DOMAINS_OUT")

local file = assert(io.open(out_path, "w"))

file:write("emu.memory type = " .. type(emu.memory) .. "\n")
local names = {}
for name, domain in pairs(emu.memory) do
    names[#names + 1] = tostring(name) .. " (" .. type(domain) .. ")"
end
table.sort(names)
for _, name in ipairs(names) do
    file:write("  domain: " .. name .. "\n")
end

-- Try a small read from each plausible domain and report the first bytes.
for _, name in ipairs({ "vram", "io", "palette", "oam", "ewram", "iwram" }) do
    local domain = emu.memory[name]
    if domain then
        local ok, bytes = pcall(function() return domain:readRange(0, 8) end)
        if ok and type(bytes) == "string" then
            local hex = {}
            for i = 1, 8 do
                hex[#hex + 1] = string.format("%02X", string.byte(bytes, i))
            end
            file:write(string.format(
                "  %s: len=%d first8=%s\n", name, #bytes, table.concat(hex, " ")))
        else
            file:write(string.format("  %s: read failed (%s)\n", name, tostring(bytes)))
        end
    else
        file:write(string.format("  %s: ABSENT\n", name))
    end
end

-- Does a smaller read work where a big one did not?
local vram = emu.memory["vram"]
if vram then
    for _, size in ipairs({ 256, 4096, 16384, 65536, 98304 }) do
        local ok, bytes = pcall(function() return vram:readRange(0, size) end)
        if ok and type(bytes) == "string" then
            local nonzero = 0
            for i = 1, #bytes do
                if string.byte(bytes, i) ~= 0 then
                    nonzero = nonzero + 1
                end
            end
            file:write(string.format(
                "  vram readRange(0,%d): len=%d nonzero=%d\n", size, #bytes, nonzero))
        else
            file:write(string.format("  vram readRange(0,%d): FAILED\n", size))
        end
    end
end

file:close()
