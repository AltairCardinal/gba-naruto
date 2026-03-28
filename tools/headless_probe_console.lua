console:log("probe_loaded")

local frame = 0

callbacks:add("start", function()
	console:log("probe_start")
end)

callbacks:add("frame", function()
	frame = frame + 1
	if frame == 1 then
		console:log("probe_frame1")
	end
	if frame == 30 then
		console:log("probe_done")
		os.exit(0)
	end
end)
