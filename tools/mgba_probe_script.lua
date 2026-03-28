local out = io.open("/Users/altair/github/naruto/notes/mgba-script-probe.txt", "w")
if not out then
	return
end

local function hex_bytes(addr, len)
	local parts = {}
	for i = 0, len - 1 do
		parts[#parts + 1] = string.format("%02X", emu:read8(addr + i))
	end
	return table.concat(parts, " ")
end

out:write("script_loaded=yes\n")
out:write(string.format("pc=%s\n", tostring(emu:readRegister("pc"))))
out:write(string.format("bytes=%s\n", hex_bytes(0x0800076C, 8)))
out:close()

callbacks:add("frame", function()
	local frame = io.open("/Users/altair/github/naruto/notes/mgba-script-frame.txt", "w")
	if frame then
		frame:write(string.format("bytes=%s\n", hex_bytes(0x0800076C, 8)))
		frame:close()
	end
end)
