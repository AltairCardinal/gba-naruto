local out = io.open("/Users/altair/github/naruto/notes/qt-watchpoint-probe.txt", "w")
if out then
	out:write("loaded\n")
	local ok, result = pcall(function()
		return emu:setRangeWatchpoint(function(info)
			local f = io.open("/Users/altair/github/naruto/notes/qt-watchpoint-hit.txt", "w")
			if f then
				f:write(string.format("addr=%08X old=%d new=%d type=%d width=%d\n",
					info.address or 0,
					info.oldValue or -1,
					info.newValue or -1,
					info.accessType or -1,
					info.width or -1))
				f:close()
			end
			os.exit(0)
		end, 0x0200A900, 0x0200AA4C, C.WATCHPOINT_TYPE.WRITE_CHANGE)
	end)
	out:write(string.format("ok=%s\n", tostring(ok)))
	out:write(string.format("result=%s\n", tostring(result)))
	out:close()
end

local frame = 0
callbacks:add("frame", function()
	frame = frame + 1
	if frame == 30 then
		os.exit(0)
	end
end)
