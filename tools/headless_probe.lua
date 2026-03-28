local path = "/Users/altair/github/naruto/notes/headless-probe.log"
local frame = 0

local function append(line)
	local f = io.open(path, frame == 0 and "w" or "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

append("loaded")

callbacks:add("start", function()
	append("start")
end)

callbacks:add("frame", function()
	frame = frame + 1
	if frame == 1 then
		append("frame1")
	end
	if frame == 30 then
		append("frame30")
		os.exit(0)
	end
end)
