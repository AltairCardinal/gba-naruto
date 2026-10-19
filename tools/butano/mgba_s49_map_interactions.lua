-- Read-only telemetry and real keypad inputs; no RAM or save writes.
local output = assert(os.getenv("KONOHA_INTERACTION_OUTPUT"))
local address = assert(tonumber(os.getenv("KONOHA_BATTLE_TELEMETRY")))
local frame, release, next_input = 0, 0, 0
local active, complete, selected, checked_boxes = nil, false, false, false
local direction_step, direction_stage, defense_down = 0, 0, false
local directions = {"Up", "Down", "Right", "Left"}
local preparation_step = 1
local preparation_keys = {"Down", "Down", "A", "A"}
local pickup_frame = nil
local traces, seen = {}, {}
local keys = {A=C.GBA_KEY.A, B=C.GBA_KEY.B, Up=C.GBA_KEY.UP, Down=C.GBA_KEY.DOWN, Right=C.GBA_KEY.RIGHT, Left=C.GBA_KEY.LEFT}
local offsets = {magic=0,battle_id=4,phase=8,round=12,current_side=16,selected_unit=20,active_unit_count=24,unit_count=28,selected_command=32,player_completed=36,enemy_completed=40,scene_frame=44,cursor_x=48,cursor_y=52,last_control_error=56,last_player_error=60,render_stage=64,presentation_busy=68,selected_character_id=72,action_count=76,action_index=80,selected_action_id=84,selected_action_error=88,last_resolved_action_id=92,background_chunk_index=96,background_chunk_count=100,selected_action_kind=104,selected_action_tool_slot=108,result_participant_count=112,result_mission_experience=116,result_battle_experience=120,result_round_bonus_experience=124,result_total_experience=128,result_level_before=132,result_level_after=136,result_experience_after=140,result_hp_growth=144,script_phase=148,script_selector=152,script_command_index=156,script_text_address=160,script_message_window_visible=164,script_portrait_0_visible=168,script_portrait_0_focused=172,script_portrait_0_id=176,script_portrait_0_expression=180,script_portrait_0_motion=184,script_portrait_1_visible=188,script_portrait_1_focused=192,script_portrait_1_id=196,script_portrait_1_expression=200,script_portrait_1_motion=204,presentation_resource_resolved=208,presentation_resource_type=212,presentation_resource_amount=216,presentation_resource_hp_delta=220,presentation_resource_chakra_delta=224,ai_secondary_planned=228,ai_defense_kind=232,ai_defense_action_id=236,ai_defense_tool_slot=240,ai_defense_score=244,presentation_passive_resolved=248,presentation_passive_id=252,presentation_passive_kind=256,presentation_passive_hp_delta=260,presentation_passive_chakra_delta=264,presentation_passive_status_code=268,presentation_passive_status_value=272,presentation_passive_status_duration_ticks=276,presentation_passive_status_applied=280,battlefield_object_count=284,presentation_battlefield_object=288,presentation_battlefield_object_kind=292,presentation_battlefield_object_slot=296,presentation_battlefield_object_damage=300,cursor_unit_id=304,cursor_unit_attack=308,cursor_unit_defense=312,cursor_unit_agility=316,cursor_unit_status_count=320,cursor_unit_active=324,cursor_unit_hp=328,selected_action_level=332,training_character_id=336,training_action_id=340,training_action_level=344,training_points=348,training_error=352,training_entry_kind=356,presentation_combat_schema_version=360,presentation_combat_stage=364,presentation_combat_stage_frame=368,presentation_combat_impact_index=372,presentation_combat_tracks=376,presentation_combat_resource=380,selected_unit_x=384,selected_unit_y=388,first_active_enemy_x=392,first_active_enemy_y=396,selected_action_effect_code=400,selected_action_target_kind=404,selected_unit_chakra=408,move_preview_x=412,move_preview_y=416,unit_character_ids=420,unit_active=468,unit_x=516,unit_y=564,selected_unit_hp=612,selected_unit_max_hp=616,unit_hp=620,unit_chakra=668,unit_side=716,unit_control=764,resource_preview_amount=812,resource_preview_maximum_amount=816,condition_outcome=820,training_detail_page=824,map_movement_active=828,map_movement_sequence=832,map_movement_elapsed=836,map_movement_offset_x=840,map_movement_offset_y=844,map_visual_facing=848,map_graphics_frame=852,pickup_sequence=856,material_3=860,material_4=864}
local function get(name) return emu:read32(address + assert(offsets[name])) end
local function write(name, text)
    local f=assert(io.open(output .. "/" .. name,"w")); f:write(text); f:close()
end
local function finish(status, message)
    complete=true
    emu:screenshot(output .. "/final.png")
    assert(emu:saveStateFile(output .. "/final.ss9"))
    write("final-state.json",string.format('{"magic":%d,"phase":%d,"busy":%d,"x":%d,"y":%d,"error":%d}',get("magic"),get("phase"),get("presentation_busy"),get("cursor_x"),get("cursor_y"),get("last_control_error")))
    write("trace.jsonl",table.concat(traces,"\n") .. "\n")
    write("done.json",string.format('{"status":"%s","frame":%d,"message":"%s"}',status,frame,message or ""))
end
local function press(key)
    emu:addKey(keys[key]); active=key; release=frame+4; next_input=frame+12
end
local function step()
    if frame > 6000 then error("input route exceeded 6000 frames") end
    if get("magic") ~= 0x4B42544C then
        if frame >= 120 and not active and frame >= next_input and preparation_keys[preparation_step] then
            press(preparation_keys[preparation_step]); preparation_step = preparation_step + 1
        end
        return
    end
    local phase=get("phase")
    if get("map_movement_active") == 1 then
        local sequence=get("map_movement_sequence")
        local elapsed=get("map_movement_elapsed")
        traces[#traces+1]=string.format('{"frame":%d,"sequence":%d,"elapsed":%d,"offset_x":%d,"offset_y":%d,"facing":%d,"graphics_frame":%d}', frame,sequence,elapsed,get("map_movement_offset_x"),get("map_movement_offset_y"),get("map_visual_facing"),get("map_graphics_frame"))
        local key=sequence .. "-" .. elapsed
        if not seen[key] and (elapsed==0 or elapsed==2 or elapsed==6) then
            emu:screenshot(output .. "/move-" .. key .. ".png"); seen[key]=true
        end
    end
    if checked_boxes and get("pickup_sequence") == 1 then
        assert(get("material_4")==1,"poison herb not added exactly once")
        assert(get("battlefield_object_count")==1,"collected chest still exists")
        -- Input-driven UI redraws can commit before telemetry publishes elapsed 0.
        for sequence = 4, 11 do
            assert(seen[sequence .. "-2"] and seen[sequence .. "-6"], "directional departure/arrival missing")
        end
        if not pickup_frame then pickup_frame = frame end
        if frame < pickup_frame + 8 then return end
        emu:screenshot(output .. "/pickup.png")
        finish("passed","S49 movement and poison herb pickup")
        return
    end
    if active or frame < next_input then return end
    -- Script confirmation must precede queued map-presentation gating.
    if phase == 18 and get("script_phase") == 1 then press("A"); return end
    if get("presentation_busy")==1 then return end
    if phase==1 then
        assert(get("battle_id")==14,"wrong battle")
        assert(get("battlefield_object_count")==2,"expected both original chests")
        if not checked_boxes then
            local checkpoint = output .. "/before-movement.ss9"
            assert(emu:saveStateFile(checkpoint), "save movement checkpoint failed")
            assert(emu:loadStateFile(checkpoint), "restore movement checkpoint failed")
            assert(get("phase") == 1 and get("battlefield_object_count") == 2, "restored checkpoint mismatch")
            emu:screenshot(output .. "/before-movement.png")
        end
        checked_boxes=true; selected=true; press("A")
    elseif selected and phase==2 then
        if direction_step < 4 then
            if direction_stage == 0 then
                press(directions[direction_step + 1]); direction_stage = 1
            else
                press("A"); direction_stage = 2
            end
        elseif get("cursor_x")<13 then press("Right")
        elseif get("cursor_x")>13 then press("Left")
        elseif get("cursor_y")<5 then press("Down")
        elseif get("cursor_y")>5 then press("Up")
        else
            assert(get("material_4")==0 and get("battlefield_object_count")==2,"preview collected a chest")
            emu:screenshot(output .. "/standing-on-chest-preview.png")
            press("A"); direction_stage = 3
        end
    elseif selected and phase==3 then
        if direction_step < 4 and direction_stage == 2 then
            press("B"); direction_step = direction_step + 1; direction_stage = 0
        elseif direction_stage ~= 3 then
            if get("selected_command")==0 then press("A") else press("Up") end
        else
            if get("selected_command")==5 then press("A") else press("Down") end
        end
    elseif selected and (phase==21 or phase==9) then press("A")
    elseif selected and phase==10 then
        if not defense_down then press("Down"); defense_down=true else press("A") end
    else press("A") end
end
callbacks:add("frame",function()
    if complete then return end
    frame=frame+1
    if active and frame>=release then emu:clearKey(keys[active]); active=nil end
    local ok,err=pcall(step)
    if not ok then finish("failed",tostring(err):gsub('["\\\n]',' ')) end
end)
