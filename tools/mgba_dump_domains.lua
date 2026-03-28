local out = io.open("/Users/altair/github/naruto/notes/mgba-memory-domains.txt", "w")
if not out then
	return
end

local function try_read(domain, size)
	local ok, data = pcall(function()
		return domain:readRange(0, size)
	end)
	if not ok or not data then
		return nil
	end
	local bytes = {data:byte(1, #data)}
	local parts = {}
	for i = 1, #bytes do
		parts[#parts + 1] = string.format("%02X", bytes[i])
	end
	return table.concat(parts, " ")
end

local candidates = {
	"bios",
	"cart0",
	"cart1",
	"cart2",
	"ewram",
	"iwram",
	"vram",
	"oam",
	"pram",
	"rom",
	"wram",
}

out:write("memory domains\n")
for _, name in ipairs(candidates) do
	local domain = emu.memory[name]
	if domain then
		local summary = try_read(domain, 16) or "(unreadable)"
		out:write(string.format("%s\t%s\n", name, summary))
	else
		out:write(string.format("%s\t(absent)\n", name))
	end
end
out:close()

os.exit(0)
