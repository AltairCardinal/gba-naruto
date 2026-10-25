-- Probe the shape of mGBA's Lua memory API once, and write it out.
-- Usage: set DUMP_SHAPE_OUT to a file path.

local out_path = os.getenv("DUMP_SHAPE_OUT")
assert(out_path and out_path ~= "", "missing DUMP_SHAPE_OUT")

local file = assert(io.open(out_path, "w"))
local io_domain = emu.memory["io"]
file:write("io type=" .. type(io_domain) .. "\n")
local bytes = io_domain:readRange(0, 4)
file:write("readRange type=" .. type(bytes) .. "\n")
file:write("len(#)=" .. tostring(#bytes) .. "\n")
if type(bytes) == "table" then
    for i = -1, 5 do
        file:write(string.format("  [%d] = %s\n", i, tostring(bytes[i])))
    end
    local ok, packed = pcall(function() return string.char(table.unpack(bytes)) end)
    file:write("table.unpack -> " .. tostring(ok) .. " " .. tostring(packed) .. "\n")
    file:write("string.byte(packed,1) = " .. tostring(string.byte(packed or "", 1)) .. "\n")
elseif type(bytes) == "string" then
    file:write("string.byte = " .. tostring(string.byte(bytes, 1)) .. "\n")
    file:write("string.byte 2 = " .. tostring(string.byte(bytes, 2)) .. "\n")
end
file:close()
